#!/usr/bin/env python3
"""fontvar — OpenType font variations: from axis values to deltas. Stdlib only.

  normalize()        user axis values -> normalized coordinates (fvar defaults, then avar),
                     rounded to F2Dot14 like HarfBuzz and FreeType do
  ItemVariationStore deltas for HVAR (advances), MVAR (vertical metrics),
                     GDEF (variable kerning) and CFF2 (blend)
  DeltaSetIndexMap   glyph -> (outer, inner) mapping used by HVAR
  tuple_scalar()     weight of one gvar tuple at a location
  mvar()             MVAR tag -> delta

Spec: https://learn.microsoft.com/typography/opentype/spec/otvaroverview
"""
import struct


def _u16(b, o): return struct.unpack_from(">H", b, o)[0]
def _i16(b, o): return struct.unpack_from(">h", b, o)[0]
def _u32(b, o): return struct.unpack_from(">I", b, o)[0]
def _f2(b, o): return _i16(b, o) / 16384


def _round_f2(v):
    return round(v * 16384) / 16384


def avar_maps(b):
    """avar v1: one list of (from, to) pairs per axis."""
    if not b:
        return None
    if _u16(b, 0) != 1:
        raise ValueError("avar version 2 is not supported")
    n, o, maps = _u16(b, 6), 8, []
    for _ in range(n):
        k = _u16(b, o); o += 2
        maps.append([(_f2(b, o + 4 * i), _f2(b, o + 4 * i + 2)) for i in range(k)])
        o += 4 * k
    return maps


def _piecewise(v, pairs):
    if not pairs:
        return v
    if v <= pairs[0][0]:
        return pairs[0][1] + (v - pairs[0][0])
    for (a0, b0), (a1, b1) in zip(pairs, pairs[1:]):
        if v <= a1:
            return b0 + (b1 - b0) * (v - a0) / (a1 - a0) if a1 != a0 else b1
    return pairs[-1][1] + (v - pairs[-1][0])


def normalize(axes, user, avar=None):
    """axes: fvar list of dicts (tag/min/default/max); user: {tag: value}.
    Returns the normalized coordinate per axis, in fvar order."""
    unknown = set(user) - {a["tag"] for a in axes}
    if unknown:
        raise ValueError(f"axes not in this font: {', '.join(sorted(unknown))} "
                         f"(it has {', '.join(a['tag'] for a in axes) or 'none'})")
    out = []
    for i, a in enumerate(axes):
        v = min(max(user.get(a["tag"], a["default"]), a["min"]), a["max"])
        if v < a["default"]:
            n = (v - a["default"]) / (a["default"] - a["min"]) if a["default"] != a["min"] else 0.0
        elif v > a["default"]:
            n = (v - a["default"]) / (a["max"] - a["default"]) if a["max"] != a["default"] else 0.0
        else:
            n = 0.0
        n = _round_f2(n)
        if avar and i < len(avar):
            n = _round_f2(_piecewise(n, avar[i]))
        out.append(n)
    return out


def region_scalar(region, coords):
    """region: list of (start, peak, end) per axis (ItemVariationStore rules)."""
    s = 1.0
    for (start, peak, end), v in zip(region, coords):
        if peak == 0 or start > peak or peak > end or (start < 0 < end):
            continue
        if v < start or v > end:
            return 0.0
        if v == peak:
            continue
        s *= (v - start) / (peak - start) if v < peak else (end - v) / (end - peak)
    return s


def tuple_scalar(peak, coords, start=None, end=None):
    """gvar tuple: peak per axis; without an intermediate region the region runs from 0 to the peak."""
    if start is None:
        start, end = [min(0.0, p) for p in peak], [max(0.0, p) for p in peak]
    return region_scalar(list(zip(start, peak, end)), coords)


class ItemVariationStore:
    def __init__(self, b, off):
        self.b = b
        rl = off + _u32(b, off + 2)
        axis_count, region_count = _u16(b, rl), _u16(b, rl + 2)
        self.regions = []
        for r in range(region_count):
            base = rl + 4 + r * axis_count * 6
            self.regions.append([(_f2(b, base + 6 * a), _f2(b, base + 6 * a + 2), _f2(b, base + 6 * a + 4))
                                 for a in range(axis_count)])
        n = _u16(b, off + 6)
        self.data = [off + _u32(b, off + 8 + 4 * i) if _u32(b, off + 8 + 4 * i) else None for i in range(n)]
        self._parsed = {}

    def _subtable(self, outer):
        if outer not in self._parsed:
            b, o = self.b, self.data[outer]
            items, wc, nreg = _u16(b, o), _u16(b, o + 2), _u16(b, o + 4)
            longs, words = bool(wc & 0x8000), wc & 0x7FFF
            regs = [_u16(b, o + 6 + 2 * i) for i in range(nreg)]
            big, small = (">i", ">h") if longs else (">h", ">b")
            bs, ss = (4, 2) if longs else (2, 1)
            row = words * bs + (nreg - words) * ss
            start = o + 6 + 2 * nreg
            rows = []
            for it in range(items):
                p, vals = start + it * row, []
                for k in range(nreg):
                    if k < words:
                        vals.append(struct.unpack_from(big, b, p)[0]); p += bs
                    else:
                        vals.append(struct.unpack_from(small, b, p)[0]); p += ss
                rows.append(vals)
            self._parsed[outer] = (regs, rows)
        return self._parsed[outer]

    def region_scalars(self, outer, coords):
        regs, _ = self._subtable(outer)
        return [region_scalar(self.regions[r], coords) for r in regs]

    def delta(self, outer, inner, coords):
        if outer >= len(self.data) or self.data[outer] is None:  # NO_VARIATION_INDEX, or a reference
            return 0.0                                            # the font does not hold: 0, as HarfBuzz
        regs, rows = self._subtable(outer)
        if inner >= len(rows):
            return 0.0
        return sum(d * region_scalar(self.regions[r], coords) for r, d in zip(regs, rows[inner]) if d)


def delta_set_index_map(b, o):
    fmt, entry = b[o], b[o + 1]
    if fmt == 0:
        count, p = _u16(b, o + 2), o + 4
    else:
        count, p = _u32(b, o + 2), o + 6
    size, inner_bits = ((entry & 0x30) >> 4) + 1, (entry & 0x0F) + 1
    out = []
    for i in range(count):
        e = int.from_bytes(b[p + i * size:p + (i + 1) * size], "big")
        out.append((e >> inner_bits, e & ((1 << inner_bits) - 1)))
    return out


def mvar(b, coords):
    """{tag: delta} for the MVAR value records at a location."""
    if not b:
        return {}
    rec_size, count, store_off = _u16(b, 6), _u16(b, 8), _u16(b, 10)
    if not store_off:
        return {}
    store = ItemVariationStore(b, store_off)
    out = {}
    for i in range(count):
        r = 12 + i * rec_size
        tag = b[r:r + 4].decode("latin-1")
        out[tag] = store.delta(_u16(b, r + 4), _u16(b, r + 6), coords)
    return out
