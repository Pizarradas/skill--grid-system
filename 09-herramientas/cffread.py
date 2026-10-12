#!/usr/bin/env python3
"""cffread — glyph bounds from CFF outlines (Type 2 charstrings). Stdlib only.

Exact bounds: cubic segments contribute their real extrema, not just their
control points. Used by fontread.py for OpenType fonts with a 'CFF ' or a
'CFF2' (variable) table. Accented glyphs built with `seac` (endchar with
4 args) are resolved through the charset and the Standard Encoding.
Specs: Adobe TN 5176 (CFF), TN 5177 (Type 2 charstrings), OpenType CFF2.
"""
import struct

import fontvar

# Standard Encoding as runs (first code, first standard-string SID, length):
# every name in it is one of the 391 CFF standard strings, so code -> SID suffices.
_STD_ENC = {}
for _c, _s, _n in ((32, 1, 95), (161, 96, 15), (177, 111, 4), (182, 115, 8), (191, 123, 1), (193, 124, 8),
                   (202, 132, 2), (205, 134, 4), (225, 138, 1), (227, 139, 1), (232, 140, 4), (241, 144, 1),
                   (245, 145, 1), (248, 146, 4)):
    for _k in range(_n):
        _STD_ENC[_c + _k] = _s + _k


class FontError(ValueError):
    pass


def _u16(b, o): return struct.unpack_from(">H", b, o)[0]


def _cff_index(b, o, cff2=False):
    w = 4 if cff2 else 2                                # CFF2 INDEX counts are u32
    count = int.from_bytes(b[o:o + w], "big")
    if count == 0:
        return [], o + w
    osz = b[o + w]
    offs = [int.from_bytes(b[o + w + 1 + i * osz:o + w + 1 + (i + 1) * osz], "big") for i in range(count + 1)]
    base = o + w + 1 + (count + 1) * osz - 1
    return [b[base + offs[i]:base + offs[i + 1]] for i in range(count)], base + offs[-1]


def _cff_dict(d, blend_k=None):
    out, ops, i = {}, [], 0
    while i < len(d):
        c = d[i]
        if c == 23 and blend_k is not None:             # CFF2 DICT blend: keep the n default values
            i += 1
            n = int(ops.pop())
            k = blend_k(int(out.get(22, [0])[0]))
            take = n * (k + 1)
            vals = ops[len(ops) - take:]
            ops = ops[:len(ops) - take] + vals[:n]
        elif c <= 24:
            if c == 12:
                key = (12, d[i + 1]); i += 2
            else:
                key = c; i += 1
            out[key] = ops; ops = []
        elif c == 28:
            ops.append(struct.unpack_from(">h", d, i + 1)[0]); i += 3
        elif c == 29:
            ops.append(struct.unpack_from(">i", d, i + 1)[0]); i += 5
        elif c == 30:
            s, i = "", i + 1
            while True:
                byte = d[i]; i += 1
                done = False
                for nib in (byte >> 4, byte & 15):
                    if nib == 0xF:
                        done = True; break
                    s += "0123456789.EE?-"[nib] + ("-" if nib == 0xC else "")
                if done:
                    break
            ops.append(float(s.replace("E-", "e-").replace("E", "e") or 0))
        elif 32 <= c <= 246:
            ops.append(c - 139); i += 1
        elif 247 <= c <= 250:
            ops.append((c - 247) * 256 + d[i + 1] + 108); i += 2
        elif 251 <= c <= 254:
            ops.append(-(c - 251) * 256 - d[i + 1] - 108); i += 2
        else:
            raise FontError(f"CFF DICT: bad byte {c}")
    return out


def _bias(n):
    return 107 if n < 1240 else 1131 if n < 33900 else 32768


def _cubic_extrema(p0, p1, p2, p3):
    """Parameter values in (0,1) where a cubic coordinate has a local extremum."""
    a = -p0 + 3 * p1 - 3 * p2 + p3
    b = 2 * (p0 - 2 * p1 + p2)
    c = p1 - p0
    ts = []
    if abs(a) < 1e-12:
        if abs(b) > 1e-12:
            ts.append(-c / b)
    else:
        disc = b * b - 4 * a * c
        if disc >= 0:
            r = disc ** 0.5
            ts += [(-b + r) / (2 * a), (-b - r) / (2 * a)]
    return [t for t in ts if 0 < t < 1]


class CFF:
    def __init__(self, b, cff2=False, coords=None):
        self.b, self.cff2 = b, cff2
        self.coords = list(coords or [])
        self.store, self._scalars, self._cache = None, {}, {}
        if cff2:
            hdr, tlen = b[2], _u16(b, 3)
            td = _cff_dict(b[hdr:hdr + tlen])
            self.gsubrs, _ = _cff_index(b, hdr + tlen, True)
            if 24 in td:
                self.store = fontvar.ItemVariationStore(b, int(td[24][0]) + 2)   # u16 length precedes the store
            k = lambda vs: len(self.store._subtable(vs)[0]) if self.store else 0
            self.charstrings, _ = _cff_index(b, int(td[17][0]), True)
            fds, _ = _cff_index(b, int(td[(12, 36)][0]), True)
            privs = [self._private(b, _cff_dict(fd), k) for fd in fds]
        else:
            hdr = b[2]
            _, o = _cff_index(b, hdr)                      # Name INDEX
            top, o = _cff_index(b, o)
            self.strings, o = _cff_index(b, o)
            self.gsubrs, _ = _cff_index(b, o)
            td = _cff_dict(top[0])
            self.top = td
            self.charstrings, _ = _cff_index(b, int(td[17][0]))
            if (12, 36) in td:                              # CID-keyed: one Private DICT per font dict
                fds, _ = _cff_index(b, int(td[(12, 36)][0]))
                privs = [self._private(b, _cff_dict(fd)) for fd in fds]
            else:
                privs = [self._private(b, td)]
        self.lsubrs = [p[0] for p in privs]
        self.vsindex = [p[1] for p in privs]
        self.fdsel = self._fdselect(b, int(td[(12, 37)][0])) if (12, 37) in td else None
        self._sids = None

    def _fdselect(self, b, o):
        fmt, n = b[o], len(self.charstrings)
        if fmt == 0:
            return list(b[o + 1:o + 1 + n])
        sel = [0] * n
        if fmt == 3:
            for r in range(_u16(b, o + 1)):
                first, fd, last = _u16(b, o + 3 + 3 * r), b[o + 5 + 3 * r], _u16(b, o + 6 + 3 * r)
                sel[first:min(last, n)] = [fd] * (min(last, n) - first)
        elif fmt == 4:
            nr = struct.unpack_from(">I", b, o + 1)[0]
            for r in range(nr):
                first, fd = struct.unpack_from(">IH", b, o + 5 + 6 * r)
                last = struct.unpack_from(">I", b, o + 11 + 6 * r)[0]
                sel[first:min(last, n)] = [fd] * (min(last, n) - first)
        else:
            raise FontError(f"CFF: FDSelect format {fmt}")
        return sel

    def _private(self, b, d, blend_k=None):
        if 18 not in d:
            return [], 0
        size, off = (int(x) for x in d[18])
        pd = _cff_dict(b[off:off + size], blend_k)
        subrs = _cff_index(b, off + int(pd[19][0]), self.cff2)[0] if 19 in pd else []
        return subrs, int(pd.get(22, [0])[0])

    def _gid_of_code(self, code):
        """seac: Standard Encoding code -> glyph id, through the charset's SIDs."""
        if self._sids is None:
            b, n, o = self.b, len(self.charstrings), int(self.top.get(15, [0])[0])
            if o == 0:                                  # ISOAdobe: glyph i has SID i
                sids = list(range(n))
            elif o in (1, 2):
                raise FontError("CFF: seac with an Expert charset is not supported")
            else:
                fmt, p, sids = b[o], o + 1, [0]
                if fmt == 0:
                    sids += [_u16(b, p + 2 * i) for i in range(n - 1)]
                else:
                    while len(sids) < n:
                        first = _u16(b, p)
                        left = b[p + 2] if fmt == 1 else _u16(b, p + 2)
                        p += 3 if fmt == 1 else 4
                        sids += range(first, first + left + 1)
                    sids = sids[:n]
            self._sids = {s: g for g, s in enumerate(sids)}
        sid = _STD_ENC.get(int(code))
        if sid is None or sid not in self._sids:
            raise FontError(f"CFF: seac code {code} not in the font")
        return self._sids[sid]

    def _region_scalars(self, vs):
        if vs not in self._scalars:
            self._scalars[vs] = self.store.region_scalars(vs, self.coords) if self.store else []
        return self._scalars[vs]

    def bbox(self, gid):
        if gid not in self._cache:
            self._cache[gid] = self._bbox(gid)
        return self._cache[gid]

    def _bbox(self, gid):
        fd = self.fdsel[gid] if self.fdsel else 0
        lsubrs = self.lsubrs[fd]
        st = dict(x=0.0, y=0.0, stems=0, width=self.cff2, box=None, open=False, vs=self.vsindex[fd])
        stack = []

        def add(x, y):
            bx = st["box"]
            st["box"] = (x, y, x, y) if bx is None else (min(bx[0], x), min(bx[1], y), max(bx[2], x), max(bx[3], y))

        def move(dx, dy):
            st["x"] += dx; st["y"] += dy
            st["start"] = (st["x"], st["y"])

        def line(dx, dy):
            if "start" in st:
                add(*st.pop("start"))
            st["x"] += dx; st["y"] += dy
            add(st["x"], st["y"])

        def curve(d1x, d1y, d2x, d2y, d3x, d3y):
            if "start" in st:
                add(*st.pop("start"))
            x0, y0 = st["x"], st["y"]
            x1, y1 = x0 + d1x, y0 + d1y
            x2, y2 = x1 + d2x, y1 + d2y
            x3, y3 = x2 + d3x, y2 + d3y
            add(x3, y3)
            for p0, p1, p2, p3, axis in ((x0, x1, x2, x3, 0), (y0, y1, y2, y3, 1)):
                for t in _cubic_extrema(p0, p1, p2, p3):
                    mt = 1 - t
                    v = mt ** 3 * p0 + 3 * mt * mt * t * p1 + 3 * mt * t * t * p2 + t ** 3 * p3
                    if axis == 0:
                        bx = st["box"]; st["box"] = (min(bx[0], v), bx[1], max(bx[2], v), bx[3])
                    else:
                        bx = st["box"]; st["box"] = (bx[0], min(bx[1], v), bx[2], max(bx[3], v))
            st["x"], st["y"] = x3, y3

        def take_width(nargs_ok):
            if not st["width"]:
                st["width"] = True
                if len(stack) > nargs_ok if nargs_ok is not None else len(stack) % 2:
                    stack.pop(0)

        def run(code, depth=0):
            if depth > 10:
                raise FontError("CFF: subroutine nesting too deep")
            i = 0
            while i < len(code):
                c = code[i]
                if c >= 32 or c == 28:                  # operands
                    if c <= 246 and c != 28:
                        stack.append(c - 139); i += 1
                    elif c <= 250 and c != 28:
                        stack.append((c - 247) * 256 + code[i + 1] + 108); i += 2
                    elif c <= 254 and c != 28:
                        stack.append(-(c - 251) * 256 - code[i + 1] - 108); i += 2
                    elif c == 28:
                        stack.append(struct.unpack_from(">h", code, i + 1)[0]); i += 3
                    else:
                        stack.append(struct.unpack_from(">i", code, i + 1)[0] / 65536); i += 5
                    continue
                i += 1
                if c in (1, 3, 18, 23):                 # stems
                    take_width(None)
                    st["stems"] += len(stack) // 2; stack.clear()
                elif c in (19, 20):                     # hintmask / cntrmask
                    take_width(None)
                    st["stems"] += len(stack) // 2; stack.clear()
                    i += (st["stems"] + 7) // 8
                elif c == 21:
                    take_width(2); move(stack[-2], stack[-1]); stack.clear()
                elif c == 22:
                    take_width(1); move(stack[-1], 0); stack.clear()
                elif c == 4:
                    take_width(1); move(0, stack[-1]); stack.clear()
                elif c == 5:
                    for k in range(0, len(stack) - 1, 2):
                        line(stack[k], stack[k + 1])
                    stack.clear()
                elif c in (6, 7):
                    horiz = c == 6
                    for v in stack:
                        line(v, 0) if horiz else line(0, v)
                        horiz = not horiz
                    stack.clear()
                elif c == 8:
                    for k in range(0, len(stack) - 5, 6):
                        curve(*stack[k:k + 6])
                    stack.clear()
                elif c == 24:
                    k = 0
                    while len(stack) - k >= 8:
                        curve(*stack[k:k + 6]); k += 6
                    line(stack[k], stack[k + 1]); stack.clear()
                elif c == 25:
                    k = 0
                    while len(stack) - k >= 8:
                        line(stack[k], stack[k + 1]); k += 2
                    curve(*stack[k:k + 6]); stack.clear()
                elif c == 26:
                    k, dx1 = 0, 0
                    if len(stack) % 2:
                        dx1, k = stack[0], 1
                    while k + 4 <= len(stack):
                        curve(dx1, stack[k], stack[k + 1], stack[k + 2], 0, stack[k + 3]); dx1 = 0; k += 4
                    stack.clear()
                elif c == 27:
                    k, dy1 = 0, 0
                    if len(stack) % 2:
                        dy1, k = stack[0], 1
                    while k + 4 <= len(stack):
                        curve(stack[k], dy1, stack[k + 1], stack[k + 2], stack[k + 3], 0); dy1 = 0; k += 4
                    stack.clear()
                elif c in (30, 31):
                    vert, k = c == 30, 0
                    while k + 4 <= len(stack):
                        last = len(stack) - k == 5
                        a, b_, c_, d = stack[k:k + 4]
                        e = stack[k + 4] if last else 0
                        if vert:
                            curve(0, a, b_, c_, d, e)
                        else:
                            curve(a, 0, b_, c_, e, d)
                        vert = not vert; k += 5 if last else 4
                    stack.clear()
                elif c == 10:
                    idx = int(stack.pop()) + _bias(len(lsubrs)); run(lsubrs[idx], depth + 1)
                elif c == 29:
                    idx = int(stack.pop()) + _bias(len(self.gsubrs)); run(self.gsubrs[idx], depth + 1)
                elif c == 11:
                    return
                elif c == 15 and self.cff2:             # vsindex
                    st["vs"] = int(stack.pop())
                elif c == 16 and self.cff2:             # blend: n defaults + n·k deltas -> n values
                    n = int(stack.pop())
                    sc = self._region_scalars(st["vs"])
                    k = len(sc)
                    args = stack[len(stack) - n * (k + 1):]
                    del stack[len(stack) - n * (k + 1):]
                    for j in range(n):
                        stack.append(args[j] + sum(d * s for d, s in zip(args[n + j * k:n + (j + 1) * k], sc)))
                elif c == 14:
                    if not st["width"]:
                        st["width"] = True
                        if len(stack) in (1, 5):
                            stack.pop(0)
                    if len(stack) >= 4:                 # seac: base + accent moved by (adx, ady)
                        adx, ady, bchar, achar = stack[-4:]
                        for g, dx, dy in ((self._gid_of_code(bchar), 0, 0), (self._gid_of_code(achar), adx, ady)):
                            cb = self.bbox(g)
                            if cb:
                                add(cb[0] + dx, cb[1] + dy); add(cb[2] + dx, cb[3] + dy)
                    stack.clear(); st["end"] = True
                    return
                elif c == 12:
                    e = code[i]; i += 1
                    s = stack
                    if e == 35:
                        curve(*s[0:6]); curve(*s[6:12])
                    elif e == 34:
                        curve(s[0], 0, s[1], s[2], s[3], 0); curve(s[4], 0, s[5], -s[2], s[6], 0)
                    elif e == 36:
                        curve(s[0], s[1], s[2], s[3], s[4], 0); curve(s[5], 0, s[6], s[7], s[8], -(s[1] + s[3] + s[7]))
                    elif e == 37:
                        dx = s[0] + s[2] + s[4] + s[6] + s[8]
                        dy = s[1] + s[3] + s[5] + s[7] + s[9]
                        curve(*s[0:6])
                        if abs(dx) > abs(dy):
                            curve(s[6], s[7], s[8], s[9], s[10], -dy)
                        else:
                            curve(s[6], s[7], s[8], s[9], -dx, s[10])
                    elif e in (9, 10, 11, 12, 14, 18, 24, 27, 28):   # abs add sub div neg drop mul dup exch
                        if e == 9: s.append(abs(s.pop()))
                        elif e == 10: s.append(s.pop() + s.pop())
                        elif e == 11: b2 = s.pop(); s.append(s.pop() - b2)
                        elif e == 12: b2 = s.pop(); s.append(s.pop() / b2)
                        elif e == 14: s.append(-s.pop())
                        elif e == 18: s.pop()
                        elif e == 24: s.append(s.pop() * s.pop())
                        elif e == 27: s.append(s[-1])
                        elif e == 28: s[-1], s[-2] = s[-2], s[-1]
                        continue
                    else:
                        raise FontError(f"CFF: escape operator 12 {e} not supported")
                    stack.clear()
                else:
                    raise FontError(f"CFF: operator {c} not supported")

        run(self.charstrings[gid])
        return st["box"]
