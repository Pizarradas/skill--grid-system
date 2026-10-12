#!/usr/bin/env python3
"""fontread — the metrics a layout grid needs, read straight from the font file.

Stdlib only. Reads TrueType/OpenType (glyf and CFF), WOFF, WOFF2 and the first
face of a collection (TTC). WOFF2 needs Brotli: the `brotli` module if it is
installed, otherwise the pure-Python decoder in `brotlidec.py`.

What it reads (OpenType spec, https://learn.microsoft.com/typography/opentype/spec/):
  head   unitsPerEm, font bbox
  hhea   ascender, descender, lineGap            (what macOS/Linux use for the line box)
  OS/2   sTypo*, usWin*, fsSelection bit 7       (USE_TYPO_METRICS), sxHeight, sCapHeight,
         xAvgCharWidth, weight/width class, panose
  post   italicAngle, isFixedPitch
  cmap   character -> glyph (formats 4 and 12)
  hmtx   advance widths
  glyf / CFF   real glyph bounding boxes (exact cubic extrema for CFF)
  GPOS / kern  pair kerning (GPOS lookup type 2 under the 'kern' feature, or legacy 'kern')
  fvar   variation axes (metrics are those of the default instance)
"""
import hashlib
import math
import os
import struct
import zlib

import cffread
import fontvar

__all__ = ["Font", "FontError", "load"]


class FontError(ValueError):
    pass


def _u8(b, o): return b[o]
def _u16(b, o): return struct.unpack_from(">H", b, o)[0]
def _i16(b, o): return struct.unpack_from(">h", b, o)[0]
def _u32(b, o): return struct.unpack_from(">I", b, o)[0]
def _i32(b, o): return struct.unpack_from(">i", b, o)[0]
def _fixed(b, o): return _i32(b, o) / 65536
def _f2(b, o): return _i16(b, o) / 16384


def _roundf(x):
    """floor(x + 0.5): how HarfBuzz (_hb_roundf) and FreeType (FT_fixedToInt) round variation deltas;
    halves go up, so -2.5 -> -2."""
    return float(math.floor(x + 0.5))


# ---------------------------------------------------------------- containers
def _sfnt(data, base=0):
    n = _u16(data, base + 4)
    tables = {}
    for i in range(n):
        r = base + 12 + 16 * i
        tag = data[r:r + 4].decode("latin-1")
        off, ln = _u32(data, r + 8), _u32(data, r + 12)
        tables[tag] = bytes(data[off:off + ln])
    return tables


def _woff1(data):
    n = _u16(data, 12)
    tables = {}
    for i in range(n):
        r = 44 + 20 * i
        tag = data[r:r + 4].decode("latin-1")
        off, clen, olen = _u32(data, r + 4), _u32(data, r + 8), _u32(data, r + 12)
        raw = data[off:off + clen]
        tables[tag] = zlib.decompress(raw) if clen < olen else bytes(raw)
    return tables


WOFF2_TAGS = ("cmap head hhea hmtx maxp name OS/2 post cvt  fpgm glyf loca prep CFF  VORG EBDT EBLC gasp hdmx kern "
              "LTSH PCLT VDMX vhea vmtx BASE GDEF GPOS GSUB EBSC JSTF MATH CBDT CBLC COLR CPAL SVG  sbix acnt avar "
              "bdat bloc bsln cvar fdsc feat fmtx fvar gvar hsty just lcar mort morx opbd prop trak Zapf Silf Glat "
              "Gloc Feat Sill")
WOFF2_TAGS = [WOFF2_TAGS[i:i + 4] for i in range(0, len(WOFF2_TAGS), 5)]


def _brotli(data):
    try:
        import brotli
        return brotli.decompress(data)
    except ImportError:
        from brotlidec import decompress
        return decompress(data)


def _base128(b, o):
    v = 0
    for i in range(5):
        c = b[o + i]
        if i == 0 and c == 0x80:
            raise FontError("WOFF2: UIntBase128 with leading zeros")
        v = (v << 7) | (c & 0x7F)
        if not c & 0x80:
            return v, o + i + 1
    raise FontError("WOFF2: UIntBase128 longer than 5 bytes")


def _woff2(data):
    """Returns (tables, glyf_bboxes or None, transformed_hmtx_bytes or None, glyph records or None)."""
    if data[4:8] == b"ttcf":
        raise FontError("WOFF2 collections are not supported")
    n, comp_len = _u16(data, 12), _u32(data, 20)
    o, entries = 48, []
    for _ in range(n):
        flags = data[o]; o += 1
        if flags & 0x3F == 0x3F:
            tag = data[o:o + 4].decode("latin-1"); o += 4
        else:
            tag = WOFF2_TAGS[flags & 0x3F]
        version = flags >> 6
        orig, o = _base128(data, o)
        transformed = (version == 0) if tag in ("glyf", "loca") else (version != 0)
        length = orig
        if transformed:
            length, o = _base128(data, o)
        entries.append((tag, length, transformed))
    blob = _brotli(bytes(data[o:o + comp_len]))
    tables, pos, special = {}, 0, {}
    for tag, length, transformed in entries:
        chunk = blob[pos:pos + length]; pos += length
        if transformed:
            special[tag] = chunk
        else:
            tables[tag] = chunk
    if pos != len(blob):
        raise FontError("WOFF2: decompressed size does not match the table directory")
    bboxes, recs = _woff2_glyf(special["glyf"]) if "glyf" in special else (None, None)
    return tables, bboxes, special.get("hmtx"), recs


def _r255(b, o):
    c = b[o]
    if c == 253:
        return _u16(b, o + 1), o + 3
    if c == 255:
        return 253 + b[o + 1], o + 2
    if c == 254:
        return 506 + b[o + 1], o + 2
    return c, o + 1


def _triplet(flag, b, o):
    """WOFF2 5.2 point triplet: returns dx, dy, new offset."""
    def sign(f, v): return v if f & 1 else -v
    if flag < 10:
        return 0, sign(flag, ((flag & 14) << 7) + b[o]), o + 1
    if flag < 20:
        return sign(flag, (((flag - 10) & 14) << 7) + b[o]), 0, o + 1
    if flag < 84:
        b0, b1 = flag - 20, b[o]
        return sign(flag, 1 + (b0 & 0x30) + (b1 >> 4)), sign(flag >> 1, 1 + ((b0 & 0x0C) << 2) + (b1 & 0x0F)), o + 1
    if flag < 120:
        b0 = flag - 84
        return sign(flag, 1 + ((b0 // 12) << 8) + b[o]), sign(flag >> 1, 1 + (((b0 % 12) >> 2) << 8) + b[o + 1]), o + 2
    if flag < 124:
        b2 = b[o + 1]
        return sign(flag, (b[o] << 4) + (b2 >> 4)), sign(flag >> 1, ((b2 & 0x0F) << 8) + b[o + 2]), o + 3
    return sign(flag, (b[o] << 8) + b[o + 1]), sign(flag >> 1, (b[o + 2] << 8) + b[o + 3]), o + 4


def _components(b, o):
    """glyf composite records -> ([(glyph, flags, arg1, arg2, (xx, xy, yx, yy))], end offset, has instructions)."""
    comps, more, instr = [], True, False
    while more:
        flags, glyph = _u16(b, o), _u16(b, o + 2); o += 4
        if flags & 0x0001:
            a1, a2 = struct.unpack_from(">hh" if flags & 0x0002 else ">HH", b, o); o += 4
        else:
            a1, a2 = struct.unpack_from(">bb" if flags & 0x0002 else ">BB", b, o); o += 2
        m = (1.0, 0.0, 0.0, 1.0)
        if flags & 0x0008:
            s = _i16(b, o) / 16384; m = (s, 0.0, 0.0, s); o += 2
        elif flags & 0x0040:
            m = (_i16(b, o) / 16384, 0.0, 0.0, _i16(b, o + 2) / 16384); o += 4
        elif flags & 0x0080:
            m = tuple(_i16(b, o + 2 * k) / 16384 for k in range(4)); o += 8
        comps.append((glyph, flags, a1, a2, m))
        instr |= bool(flags & 0x0100)
        more = bool(flags & 0x0020)
    return comps, o, instr


def _woff2_glyf(t):
    """Walks the transformed glyf streams (WOFF2 5.1).
    Returns (bboxes, records): records[g] = None | ('s', end_points, xs, ys) | ('c', components)."""
    num = _u16(t, 4)
    sizes = struct.unpack_from(">7I", t, 8)
    starts, o = [], 36
    for s in sizes:
        starts.append(o); o += s
    nc_o, np_o, fl_o, gl_o, co_o, bb_o, _ = starts
    bitmap_len = 4 * ((num + 31) >> 5)
    bitmap, bb_o = t[bb_o:bb_o + bitmap_len], bb_o + bitmap_len
    out, recs = [], []
    for g in range(num):
        nc = _i16(t, nc_o); nc_o += 2
        explicit = bitmap[g >> 3] & (0x80 >> (g & 7))
        if explicit:
            bbox = struct.unpack_from(">4h", t, bb_o); bb_o += 8
        if nc == 0:
            out.append(None); recs.append(None)
        elif nc > 0:
            ends, npts = [], 0
            for _ in range(nc):
                k, np_o = _r255(t, np_o); npts += k; ends.append(npts - 1)
            x = y = 0
            xs, ys = [], []
            for _ in range(npts):
                f = t[fl_o] & 0x7F; fl_o += 1
                dx, dy, gl_o = _triplet(f, t, gl_o)
                x += dx; y += dy
                xs.append(x); ys.append(y)
            _, gl_o = _r255(t, gl_o)  # instruction length (instructions live in their own stream)
            out.append(tuple(bbox) if explicit else (min(xs), min(ys), max(xs), max(ys)))
            recs.append(("s", ends, xs, ys))
        else:
            comps, co_o, have_instr = _components(t, co_o)
            if have_instr:
                _, gl_o = _r255(t, gl_o)
            if not explicit:
                raise FontError("WOFF2: composite glyph without explicit bbox")
            out.append(tuple(bbox)); recs.append(("c", comps))
    return out, recs


def _glyf_record(b, o, z):
    """Plain glyf glyph at [o, z) -> same record shape as _woff2_glyf."""
    if z <= o:
        return None
    nc = _i16(b, o)
    if nc < 0:
        return ("c", _components(b, o + 10)[0])
    ends = [_u16(b, o + 10 + 2 * i) for i in range(nc)]
    n = ends[-1] + 1 if ends else 0
    p = o + 10 + 2 * nc
    p += 2 + _u16(b, p)
    flags = []
    while len(flags) < n:
        f = b[p]; p += 1
        flags.append(f)
        if f & 0x08:
            flags += [f] * b[p]; p += 1
    flags = flags[:n]
    coords = []
    for short, same in ((0x02, 0x10), (0x04, 0x20)):
        v, vals = 0, []
        for f in flags:
            if f & short:
                d = b[p]; p += 1
                v += d if f & same else -d
            elif not f & same:
                v += _i16(b, p); p += 2
            vals.append(v)
        coords.append(vals)
    return ("s", ends, coords[0], coords[1])


# ---------------------------------------------------------------- gvar (TrueType outline variations)
def _packed_points(b, o):
    n = b[o]; o += 1
    if n & 0x80:
        n = ((n & 0x7F) << 8) | b[o]; o += 1
    if n == 0:
        return None, o            # all points
    pts, v = [], 0
    while len(pts) < n:
        c = b[o]; o += 1
        run = (c & 0x7F) + 1
        for _ in range(run):
            if c & 0x80:
                v += _u16(b, o); o += 2
            else:
                v += b[o]; o += 1
            pts.append(v)
    return pts, o


def _packed_deltas(b, o, n):
    out = []
    while len(out) < n:
        c = b[o]; o += 1
        run = (c & 0x3F) + 1
        if c & 0x80:
            out += [0] * run
        elif c & 0x40:
            out += list(struct.unpack_from(f">{run}h", b, o)); o += 2 * run
        else:
            out += list(struct.unpack_from(f">{run}b", b, o)); o += run
    return out, o


def _iup(ends, xs, ys, touched, dx, dy):
    """Interpolate the deltas of untouched points, contour by contour (gvar IUP)."""
    start = 0
    for end in ends:
        idx = [i for i in range(start, end + 1) if i in touched]
        if idx and len(idx) < end - start + 1:
            if len(idx) == 1:
                for i in range(start, end + 1):
                    dx[i], dy[i] = dx[idx[0]], dy[idx[0]]
            else:
                for k, p1 in enumerate(idx):
                    p2 = idx[(k + 1) % len(idx)]
                    i = p1 + 1 if p1 < end else start
                    while i != p2:
                        for orig, d in ((xs, dx), (ys, dy)):
                            x1, x2, d1, d2 = orig[p1], orig[p2], d[p1], d[p2]
                            if x1 == x2:
                                d[i] = d1 if d1 == d2 else 0
                            else:
                                if x1 > x2:
                                    x1, x2, d1, d2 = x2, x1, d2, d1
                                x = orig[i]
                                d[i] = d1 if x <= x1 else d2 if x >= x2 else d1 + (x - x1) * (d2 - d1) / (x2 - x1)
                        i = i + 1 if i < end else start
        start = end + 1


class _Gvar:
    def __init__(self, b, coords):
        self.b, self.coords = b, coords
        self.axis_count = _u16(b, 4)
        shared_n, shared_off = _u16(b, 6), _u32(b, 8)
        self.shared = [[_f2(b, shared_off + 2 * (i * self.axis_count + a)) for a in range(self.axis_count)]
                       for i in range(shared_n)]
        n, flags, self.data = _u16(b, 12), _u16(b, 14), _u32(b, 16)
        if flags & 1:
            self.offs = [_u32(b, 20 + 4 * i) for i in range(n + 1)]
        else:
            self.offs = [2 * _u16(b, 20 + 2 * i) for i in range(n + 1)]

    def deltas(self, g, npts, rec):
        """x and y deltas for the glyph's points + 4 phantom points, at self.coords."""
        total = npts + 4
        dxs, dys = [0.0] * total, [0.0] * total
        a, z = self.offs[g], self.offs[g + 1]
        if z <= a:
            return dxs, dys
        b, base = self.b, self.data + a
        count, data_off = _u16(b, base), _u16(b, base + 2)
        shared_pts, h, d = None, base + 4, base + data_off
        if count & 0x8000:
            shared_pts, d = _packed_points(b, d)
        ac = self.axis_count
        for _ in range(count & 0x0FFF):
            size, ti = _u16(b, h), _u16(b, h + 2); h += 4
            if ti & 0x8000:
                peak = [_f2(b, h + 2 * k) for k in range(ac)]; h += 2 * ac
            else:
                peak = self.shared[ti & 0x0FFF]
            start = end = None
            if ti & 0x4000:
                start = [_f2(b, h + 2 * k) for k in range(ac)]; h += 2 * ac
                end = [_f2(b, h + 2 * k) for k in range(ac)]; h += 2 * ac
            scalar = fontvar.tuple_scalar(peak, self.coords, start, end)
            if scalar == 0:
                d += size
                continue
            p = d
            pts = shared_pts
            if ti & 0x2000:
                pts, p = _packed_points(b, p)
            idx = list(range(total)) if pts is None else pts
            xs_d, p = _packed_deltas(b, p, len(idx))
            ys_d, p = _packed_deltas(b, p, len(idx))
            d += size
            tx, ty = [0.0] * total, [0.0] * total
            for k, i in enumerate(idx):
                if i < total:
                    tx[i], ty[i] = xs_d[k], ys_d[k]
            if pts is not None and rec and rec[0] == "s":
                _iup(rec[1], rec[2], rec[3], set(i for i in idx if i < npts), tx, ty)
            for i in range(total):
                dxs[i] += tx[i] * scalar; dys[i] += ty[i] * scalar
        return dxs, dys


# ---------------------------------------------------------------- OpenType layout (kerning)
def _coverage(b, o):
    fmt = _u16(b, o)
    if fmt == 1:
        n = _u16(b, o + 2)
        return {_u16(b, o + 4 + 2 * i): i for i in range(n)}
    if fmt == 2:
        out = {}
        for r in range(_u16(b, o + 2)):
            s, e, idx = _u16(b, o + 4 + 6 * r), _u16(b, o + 6 + 6 * r), _u16(b, o + 8 + 6 * r)
            for g in range(s, e + 1):
                out[g] = idx + g - s
        return out
    raise FontError(f"Coverage format {fmt}")


def _classdef(b, o):
    fmt = _u16(b, o)
    if fmt == 1:
        start, n = _u16(b, o + 2), _u16(b, o + 4)
        return {start + i: _u16(b, o + 6 + 2 * i) for i in range(n)}
    if fmt == 2:
        out = {}
        for r in range(_u16(b, o + 2)):
            s, e, c = _u16(b, o + 4 + 6 * r), _u16(b, o + 6 + 6 * r), _u16(b, o + 8 + 6 * r)
            for g in range(s, e + 1):
                out[g] = c
        return out
    raise FontError(f"ClassDef format {fmt}")


def _vr_size(fmt):
    return 2 * bin(fmt & 0xFF).count("1")


def _vr_xadv(b, o, fmt, base=0, var=None):
    """XAdvance of a ValueRecord, plus its variation delta (VariationIndex device table) at var's location."""
    v = _i16(b, o + 2 * bin(fmt & 0x3).count("1")) if fmt & 0x0004 else 0
    if var and fmt & 0x0040:
        dev = _u16(b, o + 2 * bin(fmt & 0x3F).count("1"))
        if dev and _u16(b, base + dev + 4) == 0x8000:
            v += var[0].delta(_u16(b, base + dev), _u16(b, base + dev + 2), var[1])
    return v


class _PairPos:
    """One PairPos subtable (format 1 or 2), parsed lazily into dicts."""

    def __init__(self, b, o, var=None):
        self.b, self.o, self.var = b, o, var
        self.fmt = _u16(b, o)
        self.cov = _coverage(b, o + _u16(b, o + 2))
        self.vf1, self.vf2 = _u16(b, o + 4), _u16(b, o + 6)
        self.s1, self.s2 = _vr_size(self.vf1), _vr_size(self.vf2)
        if self.fmt == 2:
            self.cd1 = _classdef(b, o + _u16(b, o + 8))
            self.cd2 = _classdef(b, o + _u16(b, o + 10))
            self.c1n, self.c2n = _u16(b, o + 12), _u16(b, o + 14)
        self.sets = {}

    def lookup(self, g1, g2):
        """(matched, x-advance delta)."""
        if g1 not in self.cov:
            return False, 0
        b, o = self.b, self.o
        if self.fmt == 1:
            idx = self.cov[g1]
            if idx not in self.sets:
                ps = o + _u16(b, o + 10 + 2 * idx)
                rec = 2 + self.s1 + self.s2
                self.sets[idx] = {_u16(b, ps + 2 + r * rec):
                                  _vr_xadv(b, ps + 4 + r * rec, self.vf1, ps, self.var)  # device offsets: from the PairSet
                                  + _vr_xadv(b, ps + 4 + r * rec + self.s1, self.vf2, ps, self.var)
                                  for r in range(_u16(b, ps))}
            s = self.sets[idx]
            return (g2 in s), s.get(g2, 0)
        c1, c2 = self.cd1.get(g1, 0), self.cd2.get(g2, 0)
        if c1 >= self.c1n or c2 >= self.c2n:
            return False, 0
        rec = o + 16 + (c1 * self.c2n + c2) * (self.s1 + self.s2)
        return True, _vr_xadv(b, rec, self.vf1, o, self.var) + _vr_xadv(b, rec + self.s1, self.vf2, o, self.var)


def _gpos_kern(b, script_pref=("latn", "DFLT"), var=None):
    """List of lookups (each a list of PairPos subtables) reached through the 'kern' feature."""
    sl, fl, ll = _u16(b, 4), _u16(b, 6), _u16(b, 8)
    feats = [(b[fl + 2 + 6 * i:fl + 6 + 6 * i].decode("latin-1"), fl + _u16(b, fl + 6 + 6 * i)) for i in range(_u16(b, fl))]
    scripts = {b[sl + 2 + 6 * i:sl + 6 + 6 * i].decode("latin-1"): sl + _u16(b, sl + 6 + 6 * i) for i in range(_u16(b, sl))}
    allowed = None
    for tag in script_pref:
        if tag in scripts and _u16(b, scripts[tag]):
            ls = scripts[tag] + _u16(b, scripts[tag])
            allowed = {_u16(b, ls + 6 + 2 * i) for i in range(_u16(b, ls + 4))}
            break
    idxs = []
    for fi, (tag, fo) in enumerate(feats):
        if tag == "kern" and (allowed is None or fi in allowed):
            idxs += [_u16(b, fo + 4 + 2 * i) for i in range(_u16(b, fo + 2))]
    lookups = []
    for li in sorted(set(idxs)):
        lo = ll + _u16(b, ll + 2 + 2 * li)
        typ, subs = _u16(b, lo), []
        for si in range(_u16(b, lo + 4)):
            so = lo + _u16(b, lo + 6 + 2 * si)
            t = typ
            if typ == 9:
                t, so = _u16(b, so + 2), so + _u32(b, so + 4)
            if t == 2:
                subs.append(_PairPos(b, so, var))
        if subs:
            lookups.append(subs)
    return lookups


def _feature_lookups(b, script_pref, wanted):
    """Lookup indices of the features in `wanted`, in the script's default LangSys (as a shaper with
    no language set picks them), falling back through script_pref."""
    sl, fl = _u16(b, 4), _u16(b, 6)
    feats = [(b[fl + 2 + 6 * i:fl + 6 + 6 * i].decode("latin-1"), fl + _u16(b, fl + 6 + 6 * i)) for i in range(_u16(b, fl))]
    scripts = {b[sl + 2 + 6 * i:sl + 6 + 6 * i].decode("latin-1"): sl + _u16(b, sl + 6 + 6 * i) for i in range(_u16(b, sl))}
    allowed = None
    for tag in script_pref:
        if tag in scripts and _u16(b, scripts[tag]):
            ls = scripts[tag] + _u16(b, scripts[tag])
            allowed = {_u16(b, ls + 6 + 2 * i) for i in range(_u16(b, ls + 4))}
            break
    idxs = set()
    for fi, (tag, fo) in enumerate(feats):
        if tag in wanted and (allowed is None or fi in allowed):
            idxs |= {_u16(b, fo + 4 + 2 * i) for i in range(_u16(b, fo + 2))}
    return sorted(idxs)


def _gsub_singles(b, script_pref, wanted=("rvrn", "ccmp", "locl")):
    """Single substitutions (GSUB lookup type 1, also through extensions) of default-on features, composed
    in lookup order: glyph -> glyph. Multiple, ligature and contextual lookups are not applied."""
    ll, out = _u16(b, 8), {}
    for li in _feature_lookups(b, script_pref, wanted):
        lo = ll + _u16(b, ll + 2 + 2 * li)
        typ, step = _u16(b, lo), {}
        for si in range(_u16(b, lo + 4)):
            so = lo + _u16(b, lo + 6 + 2 * si)
            t = typ
            if typ == 7:
                t, so = _u16(b, so + 2), so + _u32(b, so + 4)
            if t != 1:
                continue
            fmt, cov = _u16(b, so), _coverage(b, so + _u16(b, so + 2))
            for g, idx in cov.items():
                if g in step:
                    continue  # the first subtable that covers a glyph wins
                step[g] = (g + _i16(b, so + 4)) & 0xFFFF if fmt == 1 else _u16(b, so + 6 + 2 * idx)
        if step:
            out = {g: step.get(out.get(g, g), out.get(g, g)) for g in set(out) | set(step)}
    return {g: v for g, v in out.items() if g != v}


def _coverage_offsets(b, so, gsub, typ):
    """Coverage tables of one lookup subtable (enough to know which glyphs a rule can start from or touch)."""
    fmt = _u16(b, so)
    ext = 7 if gsub else 9
    if typ == ext:
        return _coverage_offsets(b, so + _u32(b, so + 4), gsub, _u16(b, so + 2))
    ctx, chain = (5, 6) if gsub else (7, 8)
    if typ == ctx and fmt == 3:
        n = _u16(b, so + 2)
        return [so + _u16(b, so + 6 + 2 * i) for i in range(n)]
    if typ == chain and fmt == 3:
        out, o = [], so + 2
        for _ in range(3):                      # backtrack, input, lookahead coverage arrays
            n = _u16(b, o)
            out += [so + _u16(b, o + 2 + 2 * i) for i in range(n)]
            o += 2 + 2 * n
        return out
    if (gsub and typ == 8):
        out, o = [so + _u16(b, so + 2)], so + 4
        for _ in range(2):
            n = _u16(b, o)
            out += [so + _u16(b, o + 2 + 2 * i) for i in range(n)]
            o += 2 + 2 * n
        return out
    if not gsub and typ in (4, 5, 6):          # mark-to-base/ligature/mark: mark and base coverages
        return [so + _u16(b, so + 2), so + _u16(b, so + 4)]
    return [so + _u16(b, so + 2)]


DEFAULT_FEATURES = {"rvrn", "ccmp", "locl", "rlig", "rclt", "calt", "liga", "clig", "mark", "mkmk", "curs", "dist",
                    "abvm", "blwm"}


def _space_rules(b, gsub, space, script_pref):
    """Does any default-on lookup other than kerning involve the space glyph?"""
    ll = _u16(b, 8)
    for li in _feature_lookups(b, script_pref, DEFAULT_FEATURES):
        lo = ll + _u16(b, ll + 2 + 2 * li)
        typ = _u16(b, lo)
        for si in range(_u16(b, lo + 4)):
            so = lo + _u16(b, lo + 6 + 2 * si)
            try:
                if any(space in _coverage(b, c) for c in _coverage_offsets(b, so, gsub, typ)):
                    return True
            except (FontError, struct.error):
                continue
    return False


def _legacy_kern(b):
    out = {}
    if _u16(b, 0) != 0:
        return out
    o = 4
    for _ in range(_u16(b, 2)):
        length, cov = _u16(b, o + 2), _u16(b, o + 4)
        if cov >> 8 == 0 and cov & 1:
            n = _u16(b, o + 6)
            for r in range(n):
                p = o + 14 + 6 * r
                out[(_u16(b, p), _u16(b, p + 2))] = out.get((_u16(b, p), _u16(b, p + 2)), 0) + _i16(b, p + 4)
        o += length
    return out


# ---------------------------------------------------------------- the font
class Font:
    """A font file, optionally at a point of its design space.

    axes: {tag: user value}, e.g. {"wght": 700, "opsz": 24}; instance: a named
    instance from fvar ("Bold", "Condensed Light"…). Without them, the default
    instance (what the file stores as its static outlines)."""

    def __init__(self, path, index=0, axes=None, instance=None):
        self.path = path
        data = open(path, "rb").read()
        self.sha1 = hashlib.sha1(data).hexdigest()
        sig = data[:4]
        self._bboxes = self._hmtx_t = self._recs = None
        if sig == b"wOF2":
            self.container = "woff2"
            self.tables, self._bboxes, self._hmtx_t, self._recs = _woff2(data)
        elif sig == b"wOFF":
            self.container = "woff"
            self.tables = _woff1(data)
        elif sig == b"ttcf":
            self.container = "ttc"
            n = _u32(data, 8)
            if index >= n:
                raise FontError(f"collection has {n} faces")
            self.tables = _sfnt(data, _u32(data, 12 + 4 * index))
        elif sig in (b"\x00\x01\x00\x00", b"OTTO", b"true"):
            self.container = "sfnt"
            self.tables = _sfnt(data)
        else:
            raise FontError(f"not a font file (signature {sig!r})")
        t = self.tables
        for req in ("head", "hhea", "maxp", "cmap"):
            if req not in t:
                raise FontError(f"missing required table '{req}'")
        h = t["head"]
        if _u32(h, 12) != 0x5F0F3CF5:
            raise FontError("head.magicNumber is wrong: corrupt file or bad decompression")
        self.upm = _u16(h, 18)
        self.head_bbox = struct.unpack_from(">4h", h, 36)
        self.index_to_loc = _i16(h, 50)
        hh = t["hhea"]
        self.hhea = dict(asc=_i16(hh, 4), desc=_i16(hh, 6), gap=_i16(hh, 8))
        self.num_hmetrics = _u16(hh, 34)
        self.num_glyphs = _u16(t["maxp"], 4)
        self.outlines = "glyf" if ("glyf" in t or self._bboxes is not None) else "CFF" if "CFF " in t else "CFF2" if "CFF2" in t else None
        self.os2 = self._read_os2(t.get("OS/2"))
        p = t.get("post")
        self.italic_angle = _fixed(p, 4) if p else 0.0
        self.fixed_pitch = bool(_u32(p, 12)) if p else False
        self.names = self._read_names(t.get("name"))
        self.cmap = self._read_cmap(t["cmap"])
        self.axes, self.instances = self._read_fvar(t.get("fvar"), self.names)
        self.location = self._location(axes, instance)
        self.coords = fontvar.normalize(self.axes, self.location, fontvar.avar_maps(t.get("avar"))) if self.axes else []
        self.varied = any(self.coords)
        self._loca = None
        self._cff = None
        self._kern_lookups = None
        self._kern_legacy = None
        self._kern_cache = {}
        self._script = ("latn",)
        self._var_cache = {}
        self.bbox_errors = {}
        self._gvar = _Gvar(t["gvar"], self.coords) if self.varied and "gvar" in t else None
        self.advances = self._read_advances()
        if self.varied:
            self._apply_mvar()

    def _location(self, axes, instance):
        loc = {}
        if (instance or axes) and not self.axes:
            raise FontError("this font is not variable: --axes/--instance do not apply")
        if instance:
            match = [i for i in self.instances if i["name"].lower() == instance.lower()]
            if not match:
                raise FontError(f"no named instance '{instance}' (has: {', '.join(i['name'] for i in self.instances) or 'none'})")
            loc.update(match[0]["coords"])
        loc.update(axes or {})
        if loc and not self.axes:
            raise FontError("this font is not variable: --axes/--instance do not apply")
        return loc

    def _apply_mvar(self):
        """Vertical metrics at the location. MVAR's hasc/hdsc/hlgp move whichever ascender/
        descender/line gap the engine uses (HarfBuzz and FreeType apply them to hhea too)."""
        d = fontvar.mvar(self.tables.get("MVAR"), self.coords)
        if not d:
            return
        for key, tag in (("asc", "hasc"), ("desc", "hdsc"), ("gap", "hlgp")):
            self.hhea[key] += d.get(tag, 0)
        if self.os2:
            for key, tag in (("typo_asc", "hasc"), ("typo_desc", "hdsc"), ("typo_gap", "hlgp"), ("win_asc", "hcla"),
                             ("win_desc", "hcld"), ("x_height", "xhgt"), ("cap_height", "cpht")):
                if key in self.os2:
                    self.os2[key] += d.get(tag, 0)

    # -- tables
    @staticmethod
    def _read_os2(b):
        if not b:
            return None
        v = _u16(b, 0)
        d = dict(version=v, avg_width=_i16(b, 2), weight=_u16(b, 4), width=_u16(b, 6),
                 panose=list(b[32:42]), fs_selection=_u16(b, 62),
                 typo_asc=_i16(b, 68), typo_desc=_i16(b, 70), typo_gap=_i16(b, 72),
                 win_asc=_u16(b, 74), win_desc=_u16(b, 76))
        d["use_typo"] = bool(d["fs_selection"] & 0x80)
        if v >= 2 and len(b) >= 90:
            d["x_height"], d["cap_height"] = _i16(b, 86), _i16(b, 88)
        return d

    @staticmethod
    def _read_names(b):
        if not b:
            return {}
        count, so = _u16(b, 2), _u16(b, 4)
        best = {}
        for i in range(count):
            r = 6 + 12 * i
            pid, eid, lang, nid, ln, off = struct.unpack_from(">6H", b, r)
            raw = b[so + off:so + off + ln]
            if pid == 3 and eid in (0, 1, 10):
                rank, s = (0 if lang == 0x409 else 1), raw.decode("utf-16-be", "replace")
            elif pid == 1 and eid == 0:
                rank, s = 2, raw.decode("mac_roman", "replace")
            elif pid == 0:
                rank, s = 3, raw.decode("utf-16-be", "replace")
            else:
                continue
            if nid not in best or rank < best[nid][0]:
                best[nid] = (rank, s)
        return {k: v[1] for k, v in best.items()}

    @staticmethod
    def _read_fvar(b, names):
        if not b:
            return [], []
        off, count, size = _u16(b, 4), _u16(b, 8), _u16(b, 10)
        axes = [dict(tag=b[off + i * size:off + i * size + 4].decode("latin-1"),
                     min=_fixed(b, off + i * size + 4), default=_fixed(b, off + i * size + 8),
                     max=_fixed(b, off + i * size + 12)) for i in range(count)]
        n_inst, isize, o = _u16(b, 12), _u16(b, 14), off + count * size
        instances = []
        for k in range(n_inst):
            r = o + k * isize
            instances.append(dict(name=names.get(_u16(b, r), f"instance {k}"),
                                  coords={a["tag"]: _fixed(b, r + 4 + 4 * j) for j, a in enumerate(axes)}))
        return axes, instances

    def _read_advances(self):
        n = self.num_hmetrics
        if self._hmtx_t is not None:
            b = self._hmtx_t
            adv = [_u16(b, 1 + 2 * i) for i in range(n)]
        else:
            b = self.tables["hmtx"]
            adv = [_u16(b, 4 * i) for i in range(n)]
        adv = adv + [adv[-1]] * (self.num_glyphs - n)
        if not self.varied:
            return adv
        hv = self.tables.get("HVAR")
        if hv:  # HVAR first, as HarfBuzz and FreeType do
            store = fontvar.ItemVariationStore(hv, _u32(hv, 4))
            mo = _u32(hv, 8)
            amap = fontvar.delta_set_index_map(hv, mo) if mo else None
            # the delta is rounded to whole font units, as HarfBuzz and FreeType do
            return [a + _roundf(store.delta(*(amap[min(g, len(amap) - 1)] if amap else (0, g)), self.coords))
                    for g, a in enumerate(adv)]
        if self._gvar:  # otherwise the phantom points of each glyph
            out = []
            for g, a in enumerate(adv):
                rec = self._record(g)
                npts = 0 if rec is None else len(rec[2]) if rec[0] == "s" else len(rec[1])
                dx, _ = self._gvar.deltas(g, npts, rec)
                out.append(a + _roundf(dx[npts + 1] - dx[npts]))
            return out
        return adv

    @staticmethod
    def _read_cmap(b):
        subs = {}
        for i in range(_u16(b, 2)):
            pid, eid, off = _u16(b, 4 + 8 * i), _u16(b, 6 + 8 * i), _u32(b, 8 + 8 * i)
            subs[(pid, eid)] = off
        for key in ((3, 10), (0, 6), (0, 4), (3, 1), (0, 3), (0, 2), (0, 1), (0, 0)):
            if key in subs:
                o = subs[key]
                fmt = _u16(b, o)
                if fmt == 12:
                    out = {}
                    for g in range(_u32(b, o + 12)):
                        s, e, sg = struct.unpack_from(">3I", b, o + 16 + 12 * g)
                        for c in range(s, e + 1):
                            out[c] = sg + c - s
                    return out
                if fmt == 4:
                    seg = _u16(b, o + 6) // 2
                    ends, starts = o + 14, o + 16 + 2 * seg
                    deltas, ranges = starts + 2 * seg, starts + 4 * seg
                    out = {}
                    for s in range(seg):
                        e, st_ = _u16(b, ends + 2 * s), _u16(b, starts + 2 * s)
                        d, ro = _i16(b, deltas + 2 * s), _u16(b, ranges + 2 * s)
                        for c in range(st_, e + 1):
                            if c == 0xFFFF:
                                continue
                            if ro == 0:
                                g = (c + d) & 0xFFFF
                            else:
                                g = _u16(b, ranges + 2 * s + ro + 2 * (c - st_))
                                g = (g + d) & 0xFFFF if g else 0
                            if g:
                                out[c] = g
                    return out
        raise FontError("no usable Unicode cmap subtable (formats 4/12)")

    # -- glyphs
    def gid(self, ch):
        return self.cmap.get(ord(ch)) if isinstance(ch, str) else self.cmap.get(ch)

    def advance(self, ch):
        g = self.gid(ch)
        return None if g is None else self.advances[g]

    def _record(self, g):
        if self._recs is not None:
            return self._recs[g]
        if self._loca is None:
            lb = self.tables["loca"]
            if self.index_to_loc == 0:
                self._loca = [2 * _u16(lb, 2 * i) for i in range(self.num_glyphs + 1)]
            else:
                self._loca = [_u32(lb, 4 * i) for i in range(self.num_glyphs + 1)]
        return _glyf_record(self.tables["glyf"], self._loca[g], self._loca[g + 1])

    def points(self, g, depth=0):
        """Outline points (on- and off-curve) of a TrueType glyph at the font's location,
        components resolved. Returns a list of (x, y)."""
        if g in self._var_cache:
            return self._var_cache[g]
        rec = self._record(g)
        if rec is None or depth > 8:
            pts = []
        elif rec[0] == "s":
            dx, dy = self._gvar.deltas(g, len(rec[2]), rec) if self._gvar else ([0.0] * len(rec[2]),) * 2
            pts = [(x + dx[i], y + dy[i]) for i, (x, y) in enumerate(zip(rec[2], rec[3]))]
        else:
            comps = rec[1]
            dx, dy = self._gvar.deltas(g, len(comps), rec) if self._gvar else ([0.0] * len(comps),) * 2
            pts = []
            for k, (cg, flags, a1, a2, (xx, xy, yx, yy)) in enumerate(comps):
                if flags & 0x0002:      # ARGS_ARE_XY_VALUES
                    ox, oy = a1 + dx[k], a2 + dy[k]
                    if flags & 0x0800:  # SCALED_COMPONENT_OFFSET
                        ox, oy = ox * xx + oy * yx, ox * xy + oy * yy
                else:                   # point matching: offset aligns two points
                    sub = self.points(cg, depth + 1)
                    ox = pts[a1][0] - sub[a2][0] if a1 < len(pts) and a2 < len(sub) else 0
                    oy = pts[a1][1] - sub[a2][1] if a1 < len(pts) and a2 < len(sub) else 0
                pts += [(x * xx + y * yx + ox, x * xy + y * yy + oy) for x, y in self.points(cg, depth + 1)]
        self._var_cache[g] = pts
        return pts

    def bbox(self, g):
        """(xMin, yMin, xMax, yMax) in font units, or None for an empty glyph."""
        if self.varied and self.outlines == "glyf" and self._gvar:
            pts = self.points(g)
            if not pts:
                return None
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            return (min(xs), min(ys), max(xs), max(ys))
        if self._bboxes is not None:
            return self._bboxes[g]
        if self.outlines == "glyf":
            if self._loca is None:
                lb = self.tables["loca"]
                if self.index_to_loc == 0:
                    self._loca = [2 * _u16(lb, 2 * i) for i in range(self.num_glyphs + 1)]
                else:
                    self._loca = [_u32(lb, 4 * i) for i in range(self.num_glyphs + 1)]
            a, z = self._loca[g], self._loca[g + 1]
            if z <= a:
                return None
            return struct.unpack_from(">4h", self.tables["glyf"], a + 2)
        if self.outlines in ("CFF", "CFF2"):
            if self._cff is None:
                if self.outlines == "CFF2":
                    self._cff = cffread.CFF(self.tables["CFF2"], cff2=True, coords=self.coords)
                else:
                    self._cff = cffread.CFF(self.tables["CFF "])
            try:
                return self._cff.bbox(g)
            except (FontError, cffread.FontError, IndexError) as e:
                self.bbox_errors[g] = str(e)
                return None
        return None

    def char_bbox(self, ch):
        g = self.gid(ch)
        return None if g is None else self.bbox(g)

    # -- kerning
    def kern_source(self):
        self._load_kern()
        return "GPOS" if self._kern_lookups else "kern" if self._kern_legacy else None

    def set_script(self, tags):
        """OpenType script tags whose 'kern' lookups apply (the shaper falls back to DFLT, then latn)."""
        tags = tuple(tags)
        if tags != self._script:
            self._script, self._kern_lookups, self._kern_legacy, self._kern_cache = tags, None, None, {}
            self._singles = None

    def shapes_across_spaces(self):
        """Firefox shapes word by word unless a default GSUB rule, or a GPOS rule that is not kerning,
        involves the space glyph (Gecko's SpaceMayParticipateInShaping, checked in Firefox 157). Word by word,
        the pairs that touch a space are not kerned."""
        sp = self.gid(" ")
        pref = self._script + tuple(s for s in ("DFLT", "latn") if s not in self._script)
        return sp is not None and any(_space_rules(self.tables[t], t == "GSUB", sp, pref)
                                      for t in ("GSUB", "GPOS") if t in self.tables)

    def substitutions(self):
        """glyph -> glyph from the default-on single substitutions (rvrn, ccmp, locl) of the current script."""
        if getattr(self, "_singles", None) is None:
            pref = self._script + tuple(s for s in ("DFLT", "latn") if s not in self._script)
            self._singles = _gsub_singles(self.tables["GSUB"], pref) if "GSUB" in self.tables else {}
        return self._singles

    def _load_kern(self):
        if self._kern_lookups is None:
            var = None
            gdef = self.tables.get("GDEF")
            if self.varied and gdef and _u16(gdef, 2) >= 3 and _u32(gdef, 14):
                var = (fontvar.ItemVariationStore(gdef, _u32(gdef, 14)), self.coords)
            pref = self._script + tuple(s for s in ("DFLT", "latn") if s not in self._script)
            self._kern_lookups = _gpos_kern(self.tables["GPOS"], pref, var) if "GPOS" in self.tables else []
            if not self._kern_lookups and "kern" in self.tables:
                self._kern_legacy = _legacy_kern(self.tables["kern"])

    def kern(self, g1, g2):
        """Total x-advance change for the glyph pair, in font units."""
        key = (g1, g2)
        if key in self._kern_cache:
            return self._kern_cache[key]
        self._load_kern()
        v = 0
        if self._kern_lookups:
            for subs in self._kern_lookups:
                for sub in subs:
                    hit, dv = sub.lookup(g1, g2)
                    if hit:
                        v += dv
                        break
        elif self._kern_legacy:
            v = self._kern_legacy.get(key, 0)
        self._kern_cache[key] = v
        return v

    def sfnt_bytes(self):
        """The font as a plain sfnt (for an external shaper). WOFF2's transformed glyf/loca are left
        out (shaping needs advances, not outlines) and hmtx is rebuilt with the default advances."""
        tables = dict(self.tables)
        if self._hmtx_t is not None or "hmtx" not in tables:
            default = Font(self.path) if self.varied else self
            hm = bytearray()
            for g in range(self.num_glyphs):
                b = default.bbox(g) if default.outlines == "glyf" else None
                lsb = int(b[0]) if b else 0
                hm += struct.pack(">Hh", int(default.advances[g]), lsb)
            tables["hmtx"] = bytes(hm)
            hh = bytearray(tables["hhea"]); struct.pack_into(">H", hh, 34, self.num_glyphs); tables["hhea"] = bytes(hh)
        tags = sorted(tables)
        out = bytearray(struct.pack(">IHHHH", 0x00010000 if self.outlines != "CFF" else 0x4F54544F, len(tags), 0, 0, 0))
        off = 12 + 16 * len(tags)
        data = bytearray()
        for tag in tags:
            blob = tables[tag]
            out += struct.pack(">4sIII", tag.encode("latin-1"), 0, off + len(data), len(blob))
            data += blob + b"\0" * (-len(blob) % 4)
        return bytes(out + data)

    @property
    def name(self):
        fam = self.names.get(16) or self.names.get(1) or os.path.basename(self.path)
        sub = self.names.get(17) or self.names.get(2) or ""
        if self.location:
            inst = [i["name"] for i in self.instances
                    if all(abs(i["coords"][a["tag"]] - self.location.get(a["tag"], a["default"])) < 1e-6 for a in self.axes)]
            sub = inst[0] if inst else " ".join(f"{k}={v:g}" for k, v in sorted(self.location.items()))
        return f"{fam} {sub}".strip()


def load(path, index=0, axes=None, instance=None):
    return Font(path, index, axes, instance)
