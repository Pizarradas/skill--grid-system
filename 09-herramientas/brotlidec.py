"""brotlidec — pure-Python Brotli decoder (RFC 7932), stdlib only.

Used to read WOFF2 fonts without third-party packages: `decompress(data) -> bytes`.
Raises ValueError on malformed or truncated input.

Tables (context lookup, transforms, NDBITS) are transcribed from RFC 7932 and checked
against the CRC-32 values the RFC publishes. The static dictionary (Appendix A,
122784 bytes) ships zlib-compressed in `brotli-dict.bin.z`, from github.com/google/brotli:
  Copyright (c) 2009, 2010, 2013-2016 by the Brotli Authors. MIT License.
"""
import os
import zlib

# ---------------------------------------------------------------- RFC 7932 tables
LUT0 = bytes([
    0, 0, 0, 0, 0, 0, 0, 0, 0, 4, 4, 0, 0, 4, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    8, 12, 16, 12, 12, 20, 12, 16, 24, 28, 12, 12, 32, 12, 36, 12, 44, 44, 44, 44, 44, 44, 44, 44, 44, 44, 32, 32, 24, 40, 28, 12,
    12, 48, 52, 52, 52, 48, 52, 52, 52, 48, 52, 52, 52, 52, 52, 48, 52, 52, 52, 52, 52, 48, 52, 52, 52, 52, 52, 24, 12, 28, 12, 12,
    12, 56, 60, 60, 60, 56, 60, 60, 60, 56, 60, 60, 60, 60, 60, 56, 60, 60, 60, 60, 60, 56, 60, 60, 60, 60, 60, 24, 12, 28, 12, 0,
]) + bytes([0, 1]) * 32 + bytes([2, 3]) * 32
LUT1 = bytes([
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1, 1, 1, 1, 1, 1,
    1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1, 1, 1, 1, 1,
    1, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 1, 1, 1, 1, 0,
]) + bytes(96) + bytes([2]) * 32
LUT2 = bytes([0] + [1] * 15 + [2] * 48 + [3] * 64 + [4] * 64 + [5] * 48 + [6] * 15 + [7])

NDBITS = [0, 0, 0, 0, 10, 10, 11, 11, 10, 10, 10, 10, 10, 9, 9, 8, 7, 7, 8, 7, 7, 6, 6, 5, 5]
DOFFSET = [0] * 25
for _n in range(24):
    DOFFSET[_n + 1] = DOFFSET[_n] + (_n * (1 << NDBITS[_n]) if NDBITS[_n] else 0)

# (prefix, elementary transform, suffix); 0 Identity, 1 FermentFirst, 2 FermentAll,
# 3..11 OmitFirst1..9, 12..20 OmitLast1..9 (Appendix B, CRC-32 0x3d965f81).
TRANSFORMS = [(p.encode("latin-1"), k, s.encode("latin-1")) for p, k, s in [
    ('', 0, ''), ('', 0, ' '), (' ', 0, ' '), ('', 3, ''), ('', 1, ' '), ('', 0, ' the '),
    (' ', 0, ''), ('s ', 0, ' '), ('', 0, ' of '), ('', 1, ''), ('', 0, ' and '), ('', 4, ''),
    ('', 12, ''), (', ', 0, ' '), ('', 0, ', '), (' ', 1, ' '), ('', 0, ' in '), ('', 0, ' to '),
    ('e ', 0, ' '), ('', 0, '"'), ('', 0, '.'), ('', 0, '">'), ('', 0, '\n'), ('', 14, ''),
    ('', 0, ']'), ('', 0, ' for '), ('', 5, ''), ('', 13, ''), ('', 0, ' a '), ('', 0, ' that '),
    (' ', 1, ''), ('', 0, '. '), ('.', 0, ''), (' ', 0, ', '), ('', 6, ''), ('', 0, ' with '),
    ('', 0, "'"), ('', 0, ' from '), ('', 0, ' by '), ('', 7, ''), ('', 8, ''), (' the ', 0, ''),
    ('', 15, ''), ('', 0, '. The '), ('', 2, ''), ('', 0, ' on '), ('', 0, ' as '),
    ('', 0, ' is '), ('', 18, ''), ('', 12, 'ing '), ('', 0, '\n\t'), ('', 0, ':'), (' ', 0, '. '),
    ('', 0, 'ed '), ('', 11, ''), ('', 9, ''), ('', 17, ''), ('', 0, '('), ('', 1, ', '),
    ('', 19, ''), ('', 0, ' at '), ('', 0, 'ly '), (' the ', 0, ' of '), ('', 16, ''),
    ('', 20, ''), (' ', 1, ', '), ('', 1, '"'), ('.', 0, '('), ('', 2, ' '), ('', 1, '">'),
    ('', 0, '="'), (' ', 0, '.'), ('.com/', 0, ''), (' the ', 0, ' of the '), ('', 1, "'"),
    ('', 0, '. This '), ('', 0, ','), ('.', 0, ' '), ('', 1, '('), ('', 1, '.'), ('', 0, ' not '),
    (' ', 0, '="'), ('', 0, 'er '), (' ', 2, ' '), ('', 0, 'al '), (' ', 2, ''), ('', 0, "='"),
    ('', 2, '"'), ('', 1, '. '), (' ', 0, '('), ('', 0, 'ful '), (' ', 1, '. '), ('', 0, 'ive '),
    ('', 0, 'less '), ('', 2, "'"), ('', 0, 'est '), (' ', 1, '.'), ('', 2, '">'), (' ', 0, "='"),
    ('', 1, ','), ('', 0, 'ize '), ('', 2, '.'), ('\xc2\xa0', 0, ''), (' ', 0, ','), ('', 1, '="'),
    ('', 2, '="'), ('', 0, 'ous '), ('', 2, ', '), ('', 1, "='"), (' ', 1, ','), (' ', 2, '="'),
    (' ', 2, ', '), ('', 2, ','), ('', 2, '('), ('', 2, '. '), (' ', 2, '.'), ('', 2, "='"),
    (' ', 2, '. '), (' ', 1, '="'), (' ', 2, "='"), (' ', 1, "='"),
]]

BLOCK_COUNT = [(1, 2), (5, 2), (9, 2), (13, 2), (17, 3), (25, 3), (33, 3), (41, 3), (49, 4), (65, 4),
               (81, 4), (97, 4), (113, 5), (145, 5), (177, 5), (209, 5), (241, 6), (305, 6), (369, 7),
               (497, 8), (753, 9), (1265, 10), (2289, 11), (4337, 12), (8433, 13), (16625, 24)]
INSERT_LEN = [(0, 0), (1, 0), (2, 0), (3, 0), (4, 0), (5, 0), (6, 1), (8, 1), (10, 2), (14, 2), (18, 3),
              (26, 3), (34, 4), (50, 4), (66, 5), (98, 5), (130, 6), (194, 7), (322, 8), (578, 9),
              (1090, 10), (2114, 12), (6210, 14), (22594, 24)]
COPY_LEN = [(2, 0), (3, 0), (4, 0), (5, 0), (6, 0), (7, 0), (8, 0), (9, 0), (10, 1), (12, 1), (14, 2),
            (18, 2), (22, 3), (30, 3), (38, 4), (54, 4), (70, 5), (102, 5), (134, 6), (198, 7), (326, 8),
            (582, 9), (1094, 10), (2118, 24)]
# insert-and-copy symbol >> 6 -> (insert code base, copy code base); symbols < 128 imply distance code 0
CMD_RANGES = [(0, 0), (0, 8), (0, 0), (0, 8), (8, 0), (8, 8), (0, 16), (16, 0), (8, 16), (16, 8), (16, 16)]
CL_ORDER = [1, 2, 3, 4, 0, 5, 17, 6, 16, 7, 8, 9, 10, 11, 12, 13, 14, 15]
# fixed code for the code-length-code lengths, indexed by the next 4 bits (Section 3.5)
CL_PEEK_LEN = [2, 2, 2, 3, 2, 2, 2, 4, 2, 2, 2, 3, 2, 2, 2, 4]
CL_PEEK_VAL = [0, 4, 3, 2, 0, 4, 3, 1, 0, 4, 3, 2, 0, 4, 3, 5]
ROOT_BITS = 8

_DICT = None


def _dictionary():
    global _DICT
    if _DICT is None:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "brotli-dict.bin.z"), "rb") as f:
            _DICT = zlib.decompress(f.read())
        if len(_DICT) != 122784:
            raise ValueError("brotli static dictionary is corrupt")
    return _DICT


def _ferment(w, pos):
    c = w[pos]
    if c < 192:
        if 97 <= c <= 122:
            w[pos] = c ^ 32
        return 1
    if c < 224:
        if pos + 1 < len(w):
            w[pos + 1] ^= 32
        return 2
    if pos + 2 < len(w):
        w[pos + 2] ^= 5
    return 3


def _transform(word, tid):
    prefix, t, suffix = TRANSFORMS[tid]
    w = bytearray(word)
    if t == 1:
        if w:
            _ferment(w, 0)
    elif t == 2:
        i = 0
        while i < len(w):
            i += _ferment(w, i)
    elif 3 <= t <= 11:
        w = w[t - 2:]
    elif t >= 12:
        w = w[:max(len(w) - (t - 11), 0)]
    return prefix + w + suffix


# ---------------------------------------------------------------- bit reader
class _Bits:
    __slots__ = ("data", "pos", "acc", "nb")

    def __init__(self, data):
        self.data, self.pos, self.acc, self.nb = data, 0, 0, 0

    def fill(self):
        data, pos, acc, nb = self.data, self.pos, self.acc, self.nb
        n = len(data)
        while nb < 32:
            if pos < n:
                acc |= data[pos] << nb
            pos += 1  # past the end we shift in zeros; check() reports the overrun
            nb += 8
        self.pos, self.acc, self.nb = pos, acc, nb

    def read(self, n):
        if self.nb < n:
            self.fill()
        v = self.acc & ((1 << n) - 1)
        self.acc >>= n
        self.nb -= n
        return v

    def check(self):
        if self.pos * 8 - self.nb > len(self.data) * 8:
            raise ValueError("brotli stream is truncated")

    def align(self):
        if self.read(self.nb & 7):
            raise ValueError("non-zero padding bits")

    def raw(self, n):
        out = bytearray()
        while self.nb and n:
            out.append(self.acc & 255)
            self.acc >>= 8
            self.nb -= 8
            n -= 1
        if self.pos + n > len(self.data):
            raise ValueError("brotli stream is truncated")
        out += self.data[self.pos:self.pos + n]
        self.pos += n
        return out


# ---------------------------------------------------------------- prefix codes
def _build(lengths):
    """Canonical code -> lookup table read LSB-first: root table of ROOT_BITS, plus subtables.

    Entry >= 0: symbol << 5 | code length. Entry < 0: ~index of a subtable for longer codes.
    """
    syms = [(l, s) for s, l in enumerate(lengths) if l]
    if not syms:
        raise ValueError("empty prefix code")
    maxlen = max(l for l, _ in syms)
    if len(syms) == 1:
        return (0, [syms[0][1] << 5], [], 0)
    root = min(maxlen, ROOT_BITS)
    sub_bits = maxlen - root
    table = [None] * (1 << root)
    subs = []
    code, prev = 0, 0
    for l, s in sorted(syms):
        code <<= l - prev
        prev = l
        rev = int(format(code, f"0{l}b")[::-1], 2)
        code += 1
        entry = s << 5 | l
        if l <= root:
            for j in range(rev, 1 << root, 1 << l):
                table[j] = entry
        else:
            low = rev & ((1 << root) - 1)
            if table[low] is None:
                subs.append([None] * (1 << sub_bits))
                table[low] = ~(len(subs) - 1)
            st = subs[~table[low]]
            for j in range(rev >> root, 1 << sub_bits, 1 << (l - root)):
                st[j] = entry
    if code != 1 << maxlen or None in table or any(None in st for st in subs):
        raise ValueError("incomplete prefix code")
    return (root, table, subs, sub_bits)


def _sym(br, h):
    root, table, subs, sub_bits = h
    if br.nb < 15:
        br.fill()
    acc = br.acc
    e = table[acc & ((1 << root) - 1)]
    if e < 0:
        e = subs[~e][(acc >> root) & ((1 << sub_bits) - 1)]
    l = e & 31
    br.acc = acc >> l
    br.nb -= l
    return e >> 5


def _read_code(br, alphabet):
    hskip = br.read(2)
    lengths = [0] * alphabet
    if hskip == 1:  # simple prefix code
        nsym = br.read(2) + 1
        bits = (alphabet - 1).bit_length()
        syms = [br.read(bits) for _ in range(nsym)]
        if any(s >= alphabet for s in syms) or len(set(syms)) != nsym:
            raise ValueError("invalid simple prefix code")
        if nsym == 1:
            return (0, [syms[0] << 5], [], 0)
        if nsym == 2:
            ls = [1, 1]
        elif nsym == 3:
            ls = [1, 2, 2]
        else:
            ls = [1, 2, 3, 3] if br.read(1) else [2, 2, 2, 2]
        for s, l in zip(syms, ls):
            lengths[s] = l
        return _build(lengths)
    # complex prefix code: first the code-length code, then the symbol lengths
    cl_lengths = [0] * 18
    space, num = 32, 0
    for i in range(hskip, 18):
        if br.nb < 4:
            br.fill()
        p = br.acc & 15
        br.acc >>= CL_PEEK_LEN[p]
        br.nb -= CL_PEEK_LEN[p]
        v = CL_PEEK_VAL[p]
        cl_lengths[CL_ORDER[i]] = v
        if v:
            space -= 32 >> v
            num += 1
            if space <= 0:
                break
    if not (num == 1 or space == 0):
        raise ValueError("invalid code-length code")
    clh = _build(cl_lengths)
    sym, prev_len, repeat, repeat_len, space = 0, 8, 0, 0, 32768
    while sym < alphabet and space > 0:
        cl = _sym(br, clh)
        if cl < 16:
            repeat = 0
            lengths[sym] = cl
            sym += 1
            if cl:
                prev_len = cl
                space -= 32768 >> cl
        else:
            extra = 2 if cl == 16 else 3
            new_len = prev_len if cl == 16 else 0
            if repeat_len != new_len:
                repeat, repeat_len = 0, new_len
            old = repeat
            if repeat > 0:
                repeat = (repeat - 2) << extra
            repeat += br.read(extra) + 3
            delta = repeat - old
            if sym + delta > alphabet:
                raise ValueError("code length repeat overflows the alphabet")
            for _ in range(delta):
                lengths[sym] = repeat_len
                sym += 1
            if repeat_len:
                space -= delta * (32768 >> repeat_len)
    if space != 0:
        raise ValueError("invalid prefix code lengths")
    return _build(lengths)


def _var256(br):
    """NBLTYPES / NTREES: 1..256 in a variable-length code."""
    if not br.read(1):
        return 1
    n = br.read(3)
    return 2 if n == 0 else (1 << n) + br.read(n) + 1


def _block_count(br, h):
    base, extra = BLOCK_COUNT[_sym(br, h)]
    return base + br.read(extra)


def _context_map(br, size, ntrees):
    rlemax = br.read(4) + 1 if br.read(1) else 0
    h = _read_code(br, ntrees + rlemax)
    cmap, i = bytearray(size), 0
    while i < size:
        s = _sym(br, h)
        if s == 0:
            i += 1
        elif s <= rlemax:
            i += (1 << s) + br.read(s)
            if i > size:
                raise ValueError("context map run overflows")
        else:
            cmap[i] = s - rlemax
            i += 1
    if br.read(1):  # inverse move-to-front
        mtf = list(range(256))
        for k in range(size):
            idx = cmap[k]
            v = mtf[idx]
            cmap[k] = v
            if idx:
                del mtf[idx]
                mtf.insert(0, v)
    return cmap


class _BlockState:
    __slots__ = ("n", "types", "counts", "last", "second", "left")

    def __init__(self, br):
        self.n = _var256(br)
        self.last, self.second, self.left = 0, 1, 1 << 30
        if self.n >= 2:
            self.types = _read_code(br, self.n + 2)
            self.counts = _read_code(br, 26)
            self.left = _block_count(br, self.counts)

    def switch(self, br):
        s = _sym(br, self.types)
        t = self.second if s == 0 else self.last + 1 if s == 1 else s - 2
        if t >= self.n:
            t -= self.n
        self.second, self.last = self.last, t
        self.left = _block_count(br, self.counts)
        return t


# ---------------------------------------------------------------- stream
def decompress(data):
    data = bytes(data)
    br = _Bits(data)
    if not br.read(1):
        wbits = 16
    else:
        n = br.read(3)
        if n:
            wbits = 17 + n
        else:
            n = br.read(3)
            if n == 1:
                raise ValueError("large-window brotli is not RFC 7932")
            wbits = 8 + n if n else 17
    window = (1 << wbits) - 16
    out = bytearray()
    dist_rb = [16, 15, 11, 4]  # dist_rb[-1] is the last distance
    while True:
        is_last = br.read(1)
        if is_last and br.read(1):
            break
        nibbles = br.read(2)
        if nibbles == 3:  # metadata block
            if br.read(1):
                raise ValueError("reserved bit set")
            nbytes = br.read(2)
            skip = 0
            for k in range(nbytes):
                b = br.read(8)
                if k == nbytes - 1 and nbytes > 1 and b == 0:
                    raise ValueError("non-minimal metadata length")
                skip |= b << (8 * k)
            if nbytes:
                skip += 1
            br.align()
            br.raw(skip)
            if is_last:
                break
            continue
        nibbles += 4
        mlen = 0
        for k in range(nibbles):
            v = br.read(4)
            if k == nibbles - 1 and nibbles > 4 and v == 0:
                raise ValueError("non-minimal meta-block length")
            mlen |= v << (4 * k)
        mlen += 1
        if not is_last and br.read(1):  # uncompressed meta-block
            br.align()
            out += br.raw(mlen)
            continue
        _metablock(br, out, mlen, window, dist_rb)
        br.check()
        if is_last:
            break
    br.align()  # fill bits of the last byte must be zero
    br.check()
    if br.pos * 8 - br.nb != len(data) * 8:
        raise ValueError("trailing data after the brotli stream")
    return bytes(out)


def _metablock(br, out, mlen, window, dist_rb):
    L, I, D = _BlockState(br), _BlockState(br), _BlockState(br)
    npostfix = br.read(2)
    ndirect = br.read(4) << npostfix
    modes = [br.read(2) for _ in range(L.n)]
    ntl = _var256(br)
    cmap_l = _context_map(br, 64 * L.n, ntl) if ntl >= 2 else bytes(64 * L.n)
    ntd = _var256(br)
    cmap_d = _context_map(br, 4 * D.n, ntd) if ntd >= 2 else bytes(4 * D.n)
    trees_l = [_read_code(br, 256) for _ in range(ntl)]
    trees_i = [_read_code(br, 704) for _ in range(I.n)]
    trees_d = [_read_code(br, 16 + ndirect + (48 << npostfix)) for _ in range(ntd)]
    pmask = (1 << npostfix) - 1
    bt_l, bt_i, bt_d = 0, 0, 0
    mode, coff = modes[0], 0
    end = len(out) + mlen
    sym, read = _sym, br.read
    while len(out) < end:
        if I.left == 0:
            bt_i = I.switch(br)
        I.left -= 1
        cmd = sym(br, trees_i[bt_i])
        r = cmd >> 6
        if r >= 11:
            raise ValueError("invalid insert-and-copy symbol")
        ib, cb = CMD_RANGES[r]
        base, extra = INSERT_LEN[ib + ((cmd >> 3) & 7)]
        ilen = base + (read(extra) if extra else 0)
        base, extra = COPY_LEN[cb + (cmd & 7)]
        clen = base + (read(extra) if extra else 0)
        if len(out) + ilen > end:
            raise ValueError("insert length exceeds the meta-block")
        for _ in range(ilen):
            if L.left == 0:
                bt_l = L.switch(br)
                mode, coff = modes[bt_l], bt_l * 64
            L.left -= 1
            p1 = out[-1] if out else 0
            p2 = out[-2] if len(out) > 1 else 0
            if mode == 2:
                ctx = LUT0[p1] | LUT1[p2]
            elif mode == 0:
                ctx = p1 & 63
            elif mode == 1:
                ctx = p1 >> 2
            else:
                ctx = LUT2[p1] << 3 | LUT2[p2]
            out.append(sym(br, trees_l[cmap_l[coff + ctx]]))
        if len(out) >= end:
            break
        if r < 2:
            dcode = 0
        else:
            if D.left == 0:
                bt_d = D.switch(br)
            D.left -= 1
            dcode = sym(br, trees_d[cmap_d[bt_d * 4 + (clen - 2 if clen < 5 else 3)]])
        if dcode < 16:
            if dcode < 4:
                dist = dist_rb[-1 - dcode]
            else:
                # 4..9 adjust the last distance, 10..15 the second-to-last: -1 +1 -2 +2 -3 +3
                k = dcode - 4 if dcode < 10 else dcode - 10
                dist = dist_rb[-1 if dcode < 10 else -2] + ((k >> 1) + 1) * (1 if k & 1 else -1)
                if dist <= 0:
                    raise ValueError("invalid distance")
        elif dcode < 16 + ndirect:
            dist = dcode - 15
        else:
            c = dcode - ndirect - 16
            nbits = 1 + (c >> (npostfix + 1))
            offset = ((2 + ((c >> npostfix) & 1)) << nbits) - 4
            dist = ((offset + read(nbits)) << npostfix) + (c & pmask) + ndirect + 1
        max_dist = min(window, len(out))
        if dist > max_dist:
            if not 4 <= clen <= 24:
                raise ValueError("invalid static dictionary reference")
            word_id = dist - max_dist - 1
            nb = NDBITS[clen]
            tid = word_id >> nb
            if tid > 120:
                raise ValueError("invalid dictionary transform")
            off = DOFFSET[clen] + (word_id & ((1 << nb) - 1)) * clen
            word = _transform(_dictionary()[off:off + clen], tid)
            if len(out) + len(word) > end:
                raise ValueError("dictionary word exceeds the meta-block")
            out += word
            continue
        if dcode:
            dist_rb.append(dist)
            del dist_rb[0]
        if len(out) + clen > end:
            raise ValueError("copy length exceeds the meta-block")
        start = len(out) - dist
        if dist >= clen:
            out += out[start:start + clen]
        else:
            pat = out[start:]
            out += (pat * (clen // dist + 1))[:clen]
