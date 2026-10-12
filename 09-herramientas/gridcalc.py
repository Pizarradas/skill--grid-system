#!/usr/bin/env python3
"""gridcalc — exact arithmetic for layout grids (web and print).

Every number a grid proposal states should come out of this script, not out of
intuition. Stdlib only. Run `gridcalc.py <command> -h` for each command.

Commands
  web       column tracks at given viewports, with warnings (measure, gutter>column, reflow)
  clamp     fluid value between two viewports  -> CSS clamp() (Utopia derivation)
  scale     modular / geometric scale (type or space), optional snapping to a unit
  ratio     best integer split of N columns for a target ratio (golden, 2:1, sqrt2...)
  compound  overlay of several column divisions (e.g. 3+4 -> 12-unit lattice)
  print     Müller-Brockmann modular grid: page, margins, leading -> fields that fit whole lines
  canon     classical page canons (Van de Graaf / ninths, ratio margins 2:3:4:6, ...)
  paper     ISO 216 A/B series and common formats
  rhythm    Euclidean rhythm E(k,n): spread k accents over n items (featured cards, breaks)
  tracks    progressive track sizes: fibonacci, geometric, arithmetic, harmonic (+ mirror)
  font      read a font file: vertical metrics per platform, measured ink, spacing, kerned text width, CSS
  lines     set real text into a measure: characters per line, rag, longest line; solve the measure for an average
  compose   multidisciplinary solver: font + use + density -> leading, measure, padding, gutter, margin, columns
  svg       draw the grid (columns, fields, baseline) as an SVG diagram
"""
import argparse
import json
import math
import os
import sys
from fractions import Fraction
from functools import reduce

PHI = (1 + 5 ** 0.5) / 2
NAMED_RATIOS = {
    "minor-second": 16 / 15, "major-second": 9 / 8, "minor-third": 6 / 5,
    "major-third": 5 / 4, "perfect-fourth": 4 / 3, "augmented-fourth": 2 ** 0.5,
    "perfect-fifth": 3 / 2, "minor-sixth": 8 / 5, "golden": PHI, "phi": PHI,
    "major-sixth": 5 / 3, "minor-seventh": 16 / 9, "major-seventh": 15 / 8,
    "octave": 2.0, "sqrt2": 2 ** 0.5, "sqrt3": 3 ** 0.5, "sqrt5": 5 ** 0.5,
}
MM_PER_PT = 25.4 / 72


def parse_ratio(s):
    s = str(s).strip().lower()
    if s in NAMED_RATIOS:
        return NAMED_RATIOS[s]
    if ":" in s:
        a, b = s.split(":")
        return float(a) / float(b)
    if "/" in s:
        a, b = s.split("/")
        return float(a) / float(b)
    return float(s)


def nums(s, typ=float):
    return [typ(x) for x in str(s).replace(" ", "").split(",") if x != ""]


def fmt(x, nd=2):
    if isinstance(x, float):
        r = round(x, nd)
        return str(int(r)) if r == int(r) else f"{r:.{nd}f}".rstrip("0").rstrip(".")
    return str(x)


def table(rows, headers, nd=2):
    cols = [headers] + [[fmt(c, nd) for c in r] for r in rows]
    w = [max(len(str(r[i])) for r in cols) for i in range(len(headers))]
    out = ["  ".join(str(h).rjust(w[i]) for i, h in enumerate(headers)),
           "  ".join("-" * w[i] for i in range(len(headers)))]
    for r in cols[1:]:
        out.append("  ".join(str(c).rjust(w[i]) for i, c in enumerate(r)))
    return "\n".join(out)


def emit(args, data, text):
    if getattr(args, "json", False):
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(text)


# ---------------------------------------------------------------- clamp
def clamp_css(vmin_val, vmax_val, vmin, vmax, root=16.0, unit="vw"):
    """Linear interpolation y = intercept + slope*viewport, clamped.

    slope = (max - min) / (vmax - vmin); intercept = min - slope * vmin.
    Expressed as clamp(min, intercept_rem + slope*100 unit, max).
    """
    slope = (vmax_val - vmin_val) / (vmax - vmin)
    intercept = vmin_val - slope * vmin
    lo, hi = sorted((vmin_val, vmax_val))
    pref = f"{fmt(intercept / root, 4)}rem + {fmt(slope * 100, 4)}{unit}"
    if slope == 0:
        return f"{fmt(vmin_val / root, 4)}rem", slope, intercept
    return f"clamp({fmt(lo / root, 4)}rem, {pref}, {fmt(hi / root, 4)}rem)", slope, intercept


def value_at(vw, vmin_val, vmax_val, vmin, vmax):
    if vw <= vmin:
        return vmin_val
    if vw >= vmax:
        return vmax_val
    return vmin_val + (vmax_val - vmin_val) * (vw - vmin) / (vmax - vmin)


def cmd_clamp(a):
    css, slope, intercept = clamp_css(a.min, a.max, a.vmin, a.vmax, a.root, a.unit)
    check = [[v, value_at(v, a.min, a.max, a.vmin, a.vmax)] for v in nums(a.check)] if a.check else []
    data = {"css": css, "slope": slope, "intercept_px": intercept}
    txt = f"{css}\n  slope={fmt(slope, 5)} ({fmt(slope*100, 4)}{a.unit}), intercept={fmt(intercept, 3)}px"
    if check:
        txt += "\n" + table(check, ["viewport", "value_px"])
        data["check"] = check
    # WCAG 1.4.4: with zoom the vw part does not grow; warn if max/min > 2.5
    if a.max / a.min > 2.5:
        txt += "\n  ! ratio max/min > 2.5: on text this can defeat 200% zoom (WCAG 1.4.4). Keep a rem term or narrow the range."
    emit(a, data, txt)


# ---------------------------------------------------------------- scale
def cmd_scale(a):
    r = parse_ratio(a.ratio)
    lo, hi = (int(x) for x in a.steps.split(".."))
    rows = []
    for n in range(lo, hi + 1):
        v = a.base * r ** n
        snapped = round(v / a.snap) * a.snap if a.snap else v
        rows.append([n, v, snapped, snapped / a.root])
    data = {"ratio": r, "rows": [dict(zip(["step", "exact", "snapped", "rem"], x)) for x in rows]}
    txt = f"ratio {fmt(r, 4)}  base {fmt(a.base)}\n" + table(rows, ["step", "exact", "snapped", "rem"])
    if a.snap:
        dupes = len(rows) - len({x[2] for x in rows})
        if dupes:
            txt += f"\n  ! snapping to {fmt(a.snap)} collapses {dupes} step(s) into the same value: use a smaller unit or fewer steps."
    emit(a, data, txt)


# ---------------------------------------------------------------- ratio
def cmd_ratio(a):
    r = parse_ratio(a.ratio)
    results = []
    for n in nums(a.columns, int):
        best = min(((k, n - k) for k in range(1, n)), key=lambda p: abs(p[0] / p[1] - r))
        results.append([n, f"{best[0]}+{best[1]}", best[0] / best[1], 100 * (best[0] / best[1] - r) / r])
    txt = f"target {fmt(r, 4)}\n" + table(results, ["columns", "split", "achieved", "error_%"])
    txt += f"\n  exact in CSS, no column grid needed: grid-template-columns: {fmt(r, 4)}fr 1fr;"
    # Fibonacci note
    fib = [1, 1]
    while fib[-1] < 200:
        fib.append(fib[-1] + fib[-2])
    if abs(r - PHI) < 1e-3:
        txt += f"\n  golden: Fibonacci totals {fib[3:12]} give splits F(n-1)+F(n-2) (e.g. 13 = 8+5, 21 = 13+8)."
    emit(a, {"target": r, "splits": results}, txt)


# ---------------------------------------------------------------- compound
def cmd_compound(a):
    divs = nums(a.divisions, int)
    lcm = reduce(lambda x, y: x * y // math.gcd(x, y), divs)
    lines = {}
    for d in divs:
        for i in range(d + 1):
            f = Fraction(i, d)
            lines.setdefault(f, []).append(d)
    ordered = sorted(lines)
    rows = [[str(f), float(f) * 100, int(f * lcm), "+".join(map(str, lines[f]))] for f in ordered]
    names = [f"[{' '.join(f'd{d}-{int(f*d)}' for d in lines[f])}]" for f in ordered]
    widths = [int((b - a_) * lcm) for a_, b in zip(ordered, ordered[1:])]
    template = names[0] + "".join(f" {w}fr {n}" for w, n in zip(widths, names[1:]))
    txt = (f"divisions {divs} -> lattice of {lcm} units, {len(ordered)} distinct lines\n"
           + table(rows, ["fraction", "%", "unit", "shared by"])
           + "\n\nCSS, exact with zero gap (gutters as padding inside items):"
           + f"\n  grid-template-columns: {template};"
           + f"\nCSS with gap: use repeat({lcm}, minmax(0, 1fr)) and place by unit lines"
           + f" (division d, part i starts at line 1 + i*{lcm}/d); the gap then stays uniform.")
    shared = [str(f) for f in ordered if len(lines[f]) > 1 and 0 < f < 1]
    txt += f"\n  coincident interior lines (strong axes): {shared or 'none'}"
    emit(a, {"lcm": lcm, "lines": [{"fraction": str(f), "divisions": lines[f]} for f in ordered]}, txt)


# ---------------------------------------------------------------- web
def cmd_web(a):
    vps = nums(a.viewports)
    rng = nums(a.range) if a.range else None

    def resolve(spec, vw):
        v = nums(spec)
        if len(v) == 1:
            return v[0]
        if not rng:
            sys.exit("--range vmin,vmax is required for fluid min,max values")
        return value_at(vw, v[0], v[1], rng[0], rng[1])

    rows, warns = [], []
    if a.typeface:
        a.char_em = Typeface(a, a.typeface).at(a.font)["cw"]   # at the body size: opsz auto
    char_w = a.font * a.char_em
    for vw in vps:
        g, m = resolve(a.gutter, vw), resolve(a.margin, vw)
        inner = min(vw - 2 * m, a.max) if a.max else vw - 2 * m
        col = (inner - (a.columns - 1) * g) / a.columns
        span = lambda k: k * col + (k - 1) * g
        measure = span(a.columns) / char_w
        rows.append([vw, m, g, inner, col, col / g if g else float("inf"), span(a.columns // 2), measure])
        if col < g:
            warns.append(f"{fmt(vw)}px: column {fmt(col)} < gutter {fmt(g)} -> single-column spans are meaningless; use fewer columns at this size.")
        if col < 24 and a.columns > 4:
            warns.append(f"{fmt(vw)}px: column {fmt(col)}px < 24px (WCAG 2.5.8 target) -> a 1-col span cannot hold a control.")
        if measure > 80:
            warns.append(f"{fmt(vw)}px: full-width text ≈ {fmt(measure,0)} chars > 75 -> constrain prose to a span or max-inline-size: {fmt(66 * a.char_em, 3)}em (66 real chars).")
        if vw <= 320 and inner < 256:
            warns.append(f"{fmt(vw)}px: content width {fmt(inner)} is very tight at 320 (WCAG 1.4.10 reflow); reduce margins.")
    headers = ["viewport", "margin", "gutter", "content", "column", "col/gut", f"span{a.columns//2}", "chars_full"]
    txt = (f"{a.columns} columns · max {fmt(a.max) if a.max else 'none'} · text {fmt(a.font)}px ≈ {fmt(char_w)}px/char\n"
           + table(rows, headers))
    if warns:
        txt += "\n\nwarnings:\n  " + "\n  ".join(dict.fromkeys(warns))
    if a.emit == "css":
        txt += "\n\n" + web_css(a, rng)
    emit(a, {"rows": [dict(zip(headers, r)) for r in rows], "warnings": warns}, txt)


def web_css(a, rng):
    def val(spec):
        v = nums(spec)
        if len(v) == 1:
            return f"{fmt(v[0] / a.root, 4)}rem"
        return clamp_css(v[0], v[1], rng[0], rng[1], a.root)[0]
    mx = f"{fmt(a.max / a.root, 4)}rem" if a.max else "100%"
    return f"""/* generated by gridcalc web — breakout page grid (full / feature / content) + column grid */
.page-grid {{
  --grid-cols: {a.columns};
  --grid-gutter: {val(a.gutter)};
  --grid-margin: {val(a.margin)};
  --grid-max: {mx};
  --grid-feature: calc(var(--grid-gutter) * 3);
  display: grid;
  /* no gap here: the tracks ARE the margins, so the sums stay exact */
  grid-template-columns:
    [full-start] minmax(var(--grid-margin), 1fr)
    [feature-start] minmax(0, var(--grid-feature))
    [content-start] min(var(--grid-max), 100% - 2 * var(--grid-margin)) [content-end]
    minmax(0, var(--grid-feature)) [feature-end]
    minmax(var(--grid-margin), 1fr) [full-end];
}}
.page-grid > * {{ grid-column: content; min-inline-size: 0; }}
.page-grid > .is-feature {{ grid-column: feature; }}
.page-grid > .is-full {{ grid-column: full; }}

.cols {{
  display: grid;
  grid-template-columns: repeat(var(--grid-cols), [col] minmax(0, 1fr));
  column-gap: var(--grid-gutter);
}}
/* a nested .cols inside a span keeps the parent lines with: grid-template-columns: subgrid; */"""


# ---------------------------------------------------------------- print
def to_pt(v, unit):
    return v / MM_PER_PT if unit == "mm" else v


def from_pt(v, unit):
    return v * MM_PER_PT if unit == "mm" else v


def cmd_print(a):
    u = a.unit
    W, H = (to_pt(x, u) for x in nums(a.page))
    top, bottom, inner, outer = (to_pt(x, u) for x in nums(a.margins))
    L = a.leading
    g_h = to_pt(a.gutter, u) if a.gutter is not None else L  # Müller-Brockmann: gutter = 1 line
    area_w = W - inner - outer
    area_h_avail = H - top - bottom
    total_lines = int(area_h_avail // L)
    gl = a.row_gutter_lines
    rows_out = []
    for R in nums(a.rows, int):
        f = (total_lines - (R - 1) * gl) // R  # lines per field
        if f < 1:
            continue
        used = R * f + (R - 1) * gl
        area_h = used * L
        slack = area_h_avail - area_h
        rows_out.append([R, f, used, from_pt(f * L, u), from_pt(area_h, u), from_pt(slack, u)])
    col_w = (area_w - (a.columns - 1) * g_h) / a.columns
    head = (f"page {fmt(from_pt(W,u))}×{fmt(from_pt(H,u))}{u} · type area width {fmt(from_pt(area_w,u))}{u}"
            f" · {a.columns} cols of {fmt(from_pt(col_w,u))}{u} · gutter {fmt(from_pt(g_h,u))}{u}"
            f"\nleading {fmt(L)}pt -> {total_lines} lines fit in {fmt(from_pt(area_h_avail,u))}{u}; row gutter = {gl} line(s)\n")
    txt = head + table(rows_out, ["rows", "lines/field", "lines_used", f"field_h_{u}", f"area_h_{u}", f"slack_{u}"])
    txt += ("\n\n  Rule: field height = whole lines; the slack goes to the bottom margin (or adjust leading)"
            "\n  so the first baseline of every field sits on the baseline grid. Cap-height alignment of the"
            "\n  field top needs the first baseline offset = cap height (InDesign: First Baseline = Cap Height).")
    data = {"total_lines": total_lines, "column_width": from_pt(col_w, u), "rows": rows_out}
    if a.typeface:
        if not a.size:
            sys.exit("--typeface needs --size (body size in pt)")
        T = Typeface(a, a.typeface)
        m = T.at(a.size)                         # print: opsz = size in pt (see metricas-de-fuente.md §7)
        prof = T.base if m["opsz"] is None else fontprofile.build(a.typeface, langs=(a.lang,), axes={**T.axes, "opsz": m["opsz"]})
        g = prof["glyphs"]
        offs = [["Ascent ('d')", (g["d_height"] or g["ascender"]) * a.size], ["Cap Height ('H')", m["cap"] * a.size],
                ["x Height ('x')", m["xh"] * a.size], ["Leading", L]]
        txt += (f"\n\n{prof['name']} {fmt(a.size)}/{fmt(L)}pt · first-baseline offset from the top of the frame (pt, measured on the glyphs)"
                + (f" · opsz {fmt(m['opsz'])}" if m["opsz"] is not None else "") + "\n"
                + table([[n, v, v / L] for n, v in offs], ["InDesign option", "offset_pt", "in_lines"], 3)
                + f"\n  Cap Height puts the ink of capitals on the field's top edge; the white then left above the first baseline"
                  f"\n  of the next field is {fmt(L - m['cap'] * a.size)}pt. Measure per line: {fmt(prof['text'].get(a.lang, {}).get('cw', m['cw']) * a.size * 66 / 72 * 25.4)}mm for 66 chars.")
        data["first_baseline"] = dict(offs)
    emit(a, data, txt)


# ---------------------------------------------------------------- canon
def cmd_canon(a):
    W, H = nums(a.page)
    out = []
    if a.method in ("vandegraaf", "ninths", "all"):
        # Van de Graaf / Villard / Rosarivo: margins in ninths of the page, block = 2/3 of page.
        out.append(["Van de Graaf (ninths)", H / 9, 2 * H / 9, W / 9, 2 * W / 9, 2 * W / 3, 2 * H / 3])
    if a.method in ("twelfths", "all"):
        out.append(["twelfths (denser)", H / 12, 2 * H / 12, W / 12, 2 * W / 12, 9 * W / 12, 9 * H / 12])
    if a.method in ("ratio", "all"):
        # inner:top:outer:bottom = 2:3:4:6 (classic), scaled so the block keeps page proportion.
        i, t, o, b = nums(a.ratios)
        # choose k so that (W - k(i+o)) / (H - k(t+b)) == W/H  -> works when (i+o)/(t+b) == W/H; else use area target
        k = (W * (1 - a.block)) / (i + o)
        out.append([f"ratio {a.ratios} @ block {fmt(a.block*100)}% width", k * t, k * b, k * i, k * o, W - k * (i + o), H - k * (t + b)])
    headers = ["method", "top", "bottom", "inner", "outer", "block_w", "block_h"]
    txt = f"page {fmt(W)}×{fmt(H)} (ratio {fmt(H/W,4)})\n" + table(out, headers)
    if abs(H / W - 1.5) < 0.01 and a.method in ("vandegraaf", "ninths", "all"):
        txt += "\n  2:3 page: block height == page width (Tschichold's golden canon)."
    txt += "\n  Facing pages: 'inner' is the spine side; single-sheet/web: use inner == outer."
    emit(a, {"rows": [dict(zip(headers, r)) for r in out]}, txt)


# ---------------------------------------------------------------- paper
def cmd_paper(a):
    rows = []
    for series, (w0, h0) in {"A": (841, 1189), "B": (1000, 1414), "C": (917, 1297)}.items():
        w, h = w0, h0
        for n in range(0, 9):
            rows.append([f"{series}{n}", w, h])
            w, h = h // 2, w
    if a.series:
        rows = [r for r in rows if r[0].startswith(a.series.upper())]
    rows += [["US Letter", 215.9, 279.4], ["Tabloid", 279.4, 431.8], ["16:9 slide", 338.67, 190.5]] if not a.series else []
    emit(a, rows, "ISO 216 (√2, mm; each size = previous halved, floored)\n" + table(rows, ["size", "w_mm", "h_mm"]))


# ---------------------------------------------------------------- rhythm
def bjorklund(k, n):
    """Euclidean rhythm: k accents spread as evenly as possible over n slots."""
    if k <= 0:
        return [0] * n
    if k >= n:
        return [1] * n
    return [1 if (i * k) % n < k else 0 for i in range(n)]


def cmd_rhythm(a):
    pat = bjorklund(a.k, a.n)
    if a.rotate:
        r = a.rotate % a.n
        pat = pat[r:] + pat[:r]
    s = "".join("x" if p else "." for p in pat)
    idx = [i + 1 for i, p in enumerate(pat) if p]
    txt = (f"E({a.k},{a.n}) = {s}\n  accented items (1-based): {idx}"
           f"\n  use: which cards/rows get the large span, where full-bleed breaks fall, which columns carry an image."
           f"\n  CSS for a repeating cycle of {a.n}: " + ", ".join(f":nth-child({a.n}n + {i})" for i in idx))
    emit(a, {"pattern": pat, "accents": idx}, txt)


# ---------------------------------------------------------------- tracks
def cmd_tracks(a):
    n = a.count
    if a.series == "fibonacci":
        v = [1, 1]
        while len(v) < n:
            v.append(v[-1] + v[-2])
        v = v[:n]
    elif a.series == "geometric":
        r = parse_ratio(a.ratio)
        v = [r ** i for i in range(n)]
    elif a.series == "arithmetic":
        v = [1 + i * a.step for i in range(n)]
    else:  # harmonic: 1, 1/2, 1/3 ...
        v = [1 / (i + 1) for i in range(n)]
    if a.mirror:
        v = v + v[-2::-1] if a.mirror == "odd" else v + v[::-1]
    tot = sum(v)
    rows = [[i + 1, x, 100 * x / tot] for i, x in enumerate(v)]
    css = " ".join(f"{fmt(x, 4)}fr" for x in v)
    txt = table(rows, ["track", "fr", "%"]) + f"\n  grid-template-columns: {css};"
    txt += "\n  note: with gap, fr shares the space AFTER gaps, so the percentages hold for the tracks only."
    emit(a, {"fr": v, "css": css}, txt)


# ---------------------------------------------------------------- svg
def cmd_svg(a):
    W, H = nums(a.size)
    t, b, i, o = nums(a.margins)
    x0, x1, y0, y1 = i, W - o, t, H - b
    aw, ah = x1 - x0, y1 - y0
    c = (aw - (a.columns - 1) * a.gutter) / a.columns
    sw = max(W, H) / 600
    el = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {fmt(W,3)} {fmt(H,3)}" width="{fmt(W,3)}" height="{fmt(H,3)}">',
          f'<rect width="{fmt(W,3)}" height="{fmt(H,3)}" fill="#fafaf7" stroke="#222" stroke-width="{fmt(sw,3)}"/>']
    if a.baseline:
        y = y0 + a.baseline
        while y <= y1 + 1e-6:
            el.append(f'<line x1="{fmt(x0,3)}" x2="{fmt(x1,3)}" y1="{fmt(y,3)}" y2="{fmt(y,3)}" stroke="#4aa3df" stroke-opacity=".35" stroke-width="{fmt(sw/2,3)}"/>')
            y += a.baseline
    rows = a.rows or 1
    rh = (ah - (rows - 1) * a.row_gutter) / rows
    for k in range(a.columns):
        x = x0 + k * (c + a.gutter)
        for r in range(rows):
            y = y0 + r * (rh + a.row_gutter)
            el.append(f'<rect x="{fmt(x,3)}" y="{fmt(y,3)}" width="{fmt(c,3)}" height="{fmt(rh,3)}" fill="#e4572e" fill-opacity=".12" stroke="#e4572e" stroke-opacity=".6" stroke-width="{fmt(sw/2,3)}"/>')
    el.append(f'<rect x="{fmt(x0,3)}" y="{fmt(y0,3)}" width="{fmt(aw,3)}" height="{fmt(ah,3)}" fill="none" stroke="#222" stroke-dasharray="{fmt(sw*4,3)}" stroke-width="{fmt(sw,3)}"/>')
    el.append(f'<text x="{fmt(x0,3)}" y="{fmt(y0 - sw*4,3)}" font-family="monospace" font-size="{fmt(sw*10,3)}" fill="#222">{a.columns} col · c {fmt(c)} · g {fmt(a.gutter)} · {rows} rows</text>')
    el.append("</svg>")
    out = "\n".join(el)
    if a.out:
        open(a.out, "w").write(out)
        print(f"wrote {a.out}")
    else:
        print(out)


# ---------------------------------------------------------------- font metrics
# Read from the font files themselves (fontread.py + fontprofile.py) and stored
# as JSON profiles in perfiles/. `gridcalc.py font <file>` measures any font;
# `--font` in compose/web/print takes a profile name or a font file.
try:
    import fontprofile
except ImportError:  # running without the sibling modules: no measured fonts
    fontprofile = None


def load_profile(name, lang="es", sample=None, axes=None, instance=None):
    if fontprofile is None:
        sys.exit("fontprofile.py is missing next to gridcalc.py")
    axes = fontprofile.parse_axes(axes) if isinstance(axes, str) else axes
    if (axes or instance) and not os.path.isfile(name):
        sys.exit("--axes/--instance need a variable font FILE, not a stored profile")
    try:
        prof = fontprofile.resolve(name, sample=sample, axes=axes, instance=instance)
    except ValueError as e:
        sys.exit(f"{name}: {e}")
    if prof is None:
        known = ", ".join(sorted(fontprofile.available()))
        sys.exit(f"unknown font '{name}'. Measure it: gridcalc.py font <file> --save\n  known: {known}")
    return prof


def profile_metrics(prof, lang="es", strict=True):
    """Flatten a profile into the metrics the solvers use (em)."""
    key = "sample" if "sample" in prof["text"] else lang
    if not prof["text"]:
        sys.exit(f"{prof['name']}: the font covers none of the corpus languages — measure your own text with --sample <file>")
    if key not in prof["text"]:
        if strict:
            have = ", ".join(prof["text"])
            sys.exit(f"{prof['name']}: no measurement for '{lang}' — the font does not cover it, or there is no corpus"
                     f" for it (measured: {have}). Use another --lang, or --sample <file> with your text")
        return None
    tx, g, v, h = prof["text"][key], prof["glyphs"], prof["vertical"], prof["horizontal"]
    if strict and tx.get("reliable") is False:
        sys.exit(f"{prof['name']} · {key}: {tx.get('script')} needs complex shaping and HarfBuzz is not installed —"
                 f" the width would be wrong (+21–25 % measured on Arabic). Install it: pip install uharfbuzz")
    gs = prof.get("glyphs_by_script", {}).get(tx.get("script"))  # x-height/cap of the text's own alphabet
    if gs and gs.get("x_height"):
        g = dict(g, x_height=gs["x_height"], cap_height=gs["cap_height"])
    return dict(
        xh=g["x_height"] or g["x_height_os2"], cap=g["cap_height"] or g["cap_height_os2"],
        asc=v["web"]["asc"], desc=v["web"]["desc"], cw=tx["cw"], zero=h["zero_ch"],
        lh_lower=tx.get("lh_no_collision_lower"), lh_letters=tx.get("lh_no_collision_letters"),
        lh_all=tx.get("lh_no_collision_all"), start_white=tx.get("line_start_white"),
        o_over=g.get("o_overshoot"), divergence=v.get("platform_divergence"),
        cap_declared=g.get("cap_height_os2"), cw_firefox=tx.get("cw_firefox"),
        opsz=prof.get("location", {}).get("opsz") if any(x["tag"] == "opsz" for x in prof.get("axes", [])) else None,
        lang=key, script=tx.get("script", "latn"), shaping=tx.get("shaping", "simple"),
        name=prof["name"], sha1=prof["sha1"][:10], kern_pct=tx.get("kern_pct"),
        model_gap=tx.get("model_gap_pct"))


# Use profiles: what the reader does decides measure, spacing ratio and density.
USES = {
    #            measure  card_chars  chain_ratio  occupancy (target band)
    #            mu = page margin as a fraction of the viewport width
    "reading":   dict(measure=66, card=34, ratio=2.0,   mu=1 / 12, occ=(0.35, 0.55)),
    "scanning":  dict(measure=60, card=30, ratio=1.618, mu=1 / 20, occ=(0.45, 0.65)),
    "operating": dict(measure=50, card=24, ratio=1.5,   mu=1 / 40, occ=(0.60, 0.80)),
}
DENSITY = {"compact": -1, "default": 0, "spacious": 1}
LEADING = dict(a=0.95, b=1.0, lam=0.2)   # lh = a + b·xh + λ(N/66 − 1); confirmed by calibrar.py (best leave-one-out)
LONGEST = 80                              # WCAG 1.4.8: no line over 80 characters (evidence, not calibrated)
CALIBRATION = {}


def apply_calibration(path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "calibracion.json")):
    """Model coefficients fitted by calibrar.py to measured references (see 08-composicion/calibracion.md)."""
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8") as fh:
        cal = json.load(fh)
    for uso, d in cal.get("uses", {}).items():
        USES[uso]["measure"] = d["measure"]
    for uso, px in cal.get("margin_375", {}).items():
        USES[uso]["mu_lo"] = px / 375          # phones only: desktop references centre a max-width column
    ld = cal.get("leading", {})
    LEADING.update({k: ld[k] for k in ("a", "b", "lam") if k in ld})
    CALIBRATION.update(cal)


def font_metrics(a):
    m = profile_metrics(load_profile(a.font, a.lang, getattr(a, "sample", None), a.axes, a.instance), a.lang)
    for k in ("xh", "cap", "asc", "desc", "cw", "zero"):
        v = getattr(a, k, None)
        if v:
            m[k] = v
    return m


class Typeface:
    """The font's metrics at the size it is used.

    A variable font with an 'opsz' axis is measured with opsz = font-size in CSS px, which is what
    browsers do by default (font-optical-sizing: auto, CSS Fonts 4 §8.1). An explicit opsz in --axes
    or --optical-sizing none turns it off, like font-variation-settings / font-optical-sizing: none."""

    def __init__(self, a, name, size_unit="px"):
        self.a, self.name, self.unit = a, name, size_unit
        self.lang, self.sample = a.lang, getattr(a, "sample", None)
        self.axes = fontprofile.parse_axes(a.axes) if getattr(a, "axes", None) else {}
        self.instance = getattr(a, "instance", None)
        self.base = load_profile(name, self.lang, self.sample, self.axes, self.instance)
        opsz = next((x for x in self.base["axes"] if x["tag"] == "opsz"), None)
        is_file = os.path.isfile(name) and not name.endswith(".json")
        auto = getattr(a, "optical_sizing", "auto") == "auto"
        self.opsz = opsz if (opsz and is_file and auto and "opsz" not in self.axes) else None
        self.frozen_opsz = bool(opsz and not is_file and auto)  # stored profile: opsz fixed when it was saved
        if self.opsz and self.instance:  # a named instance sets the other axes; opsz stays automatic
            import fontread
            inst = next(i for i in fontread.load(name).instances if i["name"].lower() == self.instance.lower())
            self.axes = {**{k: v for k, v in inst["coords"].items() if k != "opsz"}, **self.axes}
            self.instance = None
        self._cache, self._setters, self._measures = {}, {}, {}
        # the font file, to set real lines (a stored profile remembers the file it was measured from)
        self.path, self.file_axes = None, {}
        if is_file:
            self.path, self.file_axes = name, dict(self.axes)
        else:
            found = fontprofile.locate(self.base)      # the file a stored profile was measured from
            if found:
                self.path, self.file_axes = found, dict(self.base.get("location", {}))

    def opsz_at(self, size):
        return None if not self.opsz else round(min(max(size, self.opsz["min"]), self.opsz["max"]), 2)

    def at(self, size):
        """Metrics (profile_metrics + overrides) of the font as drawn at `size` (px, or pt for print)."""
        v = self.opsz_at(size)
        if v not in self._cache:
            if v is None:
                prof = self.base
            else:
                langs = (self.lang,) if self.lang in fontprofile.LANGS else ()
                prof = fontprofile.build(self.name, langs=langs, sample=self.sample, axes={**self.axes, "opsz": v})
            m = profile_metrics(prof, self.lang)
            for k in ("xh", "cap", "asc", "desc", "cw", "zero"):
                if getattr(self.a, k, None):
                    m[k] = getattr(self.a, k)
            m["opsz"] = v
            self._cache[v] = m
        return self._cache[v]

    def setter(self, size, firefox=False):
        """A linebreak.Setter for the copy at this size (None without the font file or a text)."""
        if not self.path:
            return None
        v = self.opsz_at(size)
        key = (v, firefox, size if firefox else None)   # Firefox rounds to 1/60 px: the exact size matters
        if key not in self._setters:
            import fontread
            import linebreak
            if self.sample:
                with open(self.sample, encoding="utf-8") as fh:
                    text = fh.read()
            elif self.lang in fontprofile.LANGS:
                text = fontprofile.corpus_text(self.lang)
            else:
                return None
            axes = {**self.file_axes, **({"opsz": v} if v is not None else {})} or None
            font = fontread.load(self.path, axes=axes, instance=self.instance)
            self._setters[key] = linebreak.Setter(font, text, firefox, size)
        return self._setters[key]

    def fit(self, size, chars, longest=None):
        """The largest average ≤ chars whose longest set line stays ≤ longest (WCAG 1.4.8)."""
        longest = longest or LONGEST
        n = chars
        while n > 30:
            ms = self.measure(size, n)
            if ms is None or ms[1]["chars_max"] <= longest:
                return n
            n -= 1
        return n

    def measure(self, size, chars):
        """(width in em whose lines average `chars` real characters, line stats) — or None."""
        v = self.opsz_at(size)
        if (v, chars) not in self._measures:
            import linebreak
            s = self.setter(size)
            if s is None:
                self._measures[(v, chars)] = None
            else:
                w = linebreak.solve(s, chars)
                self._measures[(v, chars)] = (w, linebreak.stats(s.set(w), w))
        return self._measures[(v, chars)]


def leading(m, measure, floor):
    """Constant interline white: lh = xh + W0 + λ(N/66 − 1), floored.

    W0 = 0.95em is the white between the x-height band of one line and the next
    that classic settings share (Times 10/14 → 0.95; Inter 16/24 → 0.95).
    λ = 0.2: longer lines need more leading to find the next line.
    Heuristic, calibrated on common practice; floor = 1.5 (WCAG 1.4.8 AAA).
    """
    return max(floor, LEADING["a"] + LEADING["b"] * m["xh"] + LEADING["lam"] * (measure / 66 - 1))


def snap(v, q, up=True):
    return math.ceil(v / q - 1e-9) * q if up else round(v / q) * q


def pct(v):
    return f"{fmt(100 * v, 2)}%"


# Fonts drawn with the same advances by design (metric-compatible clones), so one size-adjust serves all:
# the fallback works where the original is not installed (Linux has no Arial; measured).
METRIC_CLONES = {"Arial": ["Liberation Sans", "Arimo"], "Times New Roman": ["Liberation Serif", "Tinos"],
                 "Courier New": ["Liberation Mono", "Cousine"], "Calibri": ["Carlito"], "Cambria": ["Caladea"],
                 "Georgia": ["Gelasio"]}


def font_css(prof, m, fallback=None):
    v = prof["vertical"]["web"]
    out = [f"/* gridcalc font — {prof['name']} · {prof['file']} (sha1 {prof['sha1'][:10]}) · text: {m['lang']} */",
           "@font-face {",
           f"  font-family: \"{prof['family']}\";",
           f"  src: url(\"{prof['file']}\") format(\"{ {'woff2': 'woff2', 'woff': 'woff'}.get(prof['container'], 'opentype') }\");",
           f"  font-weight: {prof['weight'] or 400};",
           f"  /* same line box on every platform (web metrics: {prof['vertical']['web_source']}) */",
           f"  ascent-override: {pct(v['asc'])};",
           f"  descent-override: {pct(v['desc'])};",
           f"  line-gap-override: {pct(v['gap'])};",
           "}",
           ":root {",
           f"  --font-x-height: {fmt(m['xh'], 4)};   /* font-size-adjust: ex-height {fmt(m['xh'], 4)} */",
           f"  --font-cap-height: {fmt(m['cap'], 4)}; /* font-size-adjust: cap-height {fmt(m['cap'], 4)} */",
           f"  --font-char-em: {fmt(m['cw'], 4)};     /* average advance of running text, kerned ({m['lang']}) */",
           f"  --font-measure-66: {fmt(66 * m['cw'], 3)}em;",
           "}"]
    if fallback:
        fb = profile_metrics(fallback, m["lang"], strict=False)
        if fb is None:
            return "\n".join(out) + f"\n/* no fallback rule: {fallback['name']} has no measurement for '{m['lang']}' */"
        fv = fallback["vertical"]["web"]
        k = m["cw"] / fb["cw"]
        names = [x for x in (fallback.get("full_name"), fallback.get("postscript")) if x]
        names += METRIC_CLONES.get(fallback.get("family"), [])
        locals_ = ", ".join(f'local("{n}")' for n in dict.fromkeys(names))
        # size-adjust matches one language exactly; the others keep a residual (measured in browsers)
        resid = []
        for lang, t_ in prof["text"].items():
            ft = fallback["text"].get(lang)
            if ft and lang != m["lang"] and t_.get("reliable", True):
                resid.append(f"{lang} {fmt(100 * (k * ft['cw'] / t_['cw'] - 1), 2)}%")
        out += ["",
                f"/* fallback that occupies the same space as {prof['family']} while it loads (CLS ≈ 0):",
                f"   size-adjust = char_em {fmt(m['cw'], 4)} / {fmt(fb['cw'], 4)} ({fallback['name']}, {m['lang']});",
                "   overrides = the web font's metrics divided by size-adjust */",
                "@font-face {",
                f"  font-family: \"{prof['family']} Fallback\";",
                f"  src: {locals_};",
                f"  size-adjust: {pct(k)};",
                f"  ascent-override: {pct(v['asc'] / k)};",
                f"  descent-override: {pct(v['desc'] / k)};",
                f"  line-gap-override: {pct(v['gap'] / k)};",
                "}",
                f"/* font-family: \"{prof['family']}\", \"{prof['family']} Fallback\", sans-serif;"
                f" x-height after size-adjust: {fmt(fb['xh'] * k, 3)} vs {fmt(m['xh'], 3)}"
                + (f"\n   exact for {m['lang']}; width left over in other languages: {', '.join(resid)}" if resid else "")
                + (f"\n   computed at opsz {fmt(m['opsz'])}: a font with an opsz axis changes width with size,"
                   f" so the fallback matches the size it was computed for (font --size <body px>)" if m.get("opsz") else "")
                + " */"]
    return "\n".join(out)


def font_report(prof, a):
    m = profile_metrics(prof, a.lang, strict=False)
    if m is None and prof["text"]:  # the summary language is not covered: summarise the first measured one
        m = profile_metrics(prof, next(iter(prof["text"])), strict=False)
    v, g, h = prof["vertical"], prof["glyphs"], prof["horizontal"]
    L = []
    L.append(f"{prof['name']} · {prof['file']} ({prof['container']}, {prof['outlines']}, {prof['glyph_count']} glyphs,"
             f" upm {prof['upm']}, sha1 {prof['sha1'][:10]}) · weight {prof['weight']} · kerning {prof['kerning'] or 'none'}")
    if prof["axes"]:
        L.append("  variable: " + ", ".join(f"{x['tag']} {fmt(x['min'])}–{fmt(x['max'])} (default {fmt(x['default'])})" for x in prof["axes"]))
        L.append("  measured at: " + " ".join(f"{k}={fmt(v)}" for k, v in prof["location"].items())
                 + (f" · named instances: {', '.join(prof['instances'])}" if prof["instances"] else ""))
    rows = [[n, x["asc"], x["desc"], x["gap"], x["content"], x["normal"]] for n, x in
            (("hhea", v["hhea"]), ("OS/2 typo", v["typo"]), ("OS/2 win", v["win"])) if x]
    L.append("\nvertical metrics (em)\n" + table(rows, ["table", "ascent", "descent", "lineGap", "content", "normal"], 4))
    L.append(f"  USE_TYPO_METRICS {'on' if v['use_typo_metrics'] else 'off'} → line box: web {v['web_source']}"
             f" (asc {fmt(v['web']['asc'], 3)} · desc {fmt(v['web']['desc'], 3)}),"
             f" Windows {'same' if v['platform_divergence'] is None else 'win (asc ' + fmt(v['windows']['asc'], 3) + ' · desc ' + fmt(v['windows']['desc'], 3) + ')'}")
    L.append("\nink (em, measured on the glyphs)")
    L.append(f"  x-height {fmt(g['x_height'], 3)} (OS/2 {fmt(g['x_height_os2'], 3) if g['x_height_os2'] is not None else '—'})"
             f" · cap height {fmt(g['cap_height'], 3)} (OS/2 {fmt(g['cap_height_os2'], 3) if g['cap_height_os2'] is not None else '—'})"
             f" · x/cap {fmt(g['xh_cap'], 3)}")
    L.append(f"  overshoot o +{fmt(g['o_overshoot'], 3)} / −{fmt(g['o_undershoot'], 3)} · O +{fmt(g['O_overshoot'], 3)}"
             f" · ascender {fmt(g['ascender'], 3)} · descender {fmt(g['descender'], 3)}"
             f" · digits {fmt(g['digit_height'], 3)} ({'lining' if g['lining_digits'] else 'oldstyle/other'})")
    other = {s: x for s, x in prof.get("glyphs_by_script", {}).items() if s != g.get("script")}
    if other:
        L.append("  other alphabets: " + " · ".join(f"{s} x-height {fmt(x['x_height'], 3)} cap {fmt(x['cap_height'], 3)}"
                                                       for s, x in other.items()))
    sbs = " · ".join(f"{c} {fmt(x[0], 3)}|{fmt(x[1], 3)}" for c, x in h["sidebearings"].items())
    L.append("\nhorizontal (em)")
    L.append(f"  space {fmt(h['space'], 3)} · ch (\"0\") {fmt(h['zero_ch'], 3)} · – {fmt(h['en_dash'], 3)} · — {fmt(h['em_dash'], 3)}"
             f" · digits {fmt(h['digit_avg'], 3)} ({'tabular' if h['tabular_digits'] else 'proportional'})"
             f" · OS/2 xAvgCharWidth {fmt(h['os2_avg_width'], 3)}")
    L.append(f"  sidebearings left|right: {sbs}")
    rows = []
    for lang, t in prof["text"].items():
        cw_txt = t["cw"] if t.get("reliable", True) else f"≈{fmt(t['cw'], 4)} (unreliable)"
        rows.append([lang, f"{t.get('script', 'latn')}{'*' if t.get('shaping') == 'complex' else ''}", t["chars"], cw_txt, t["cw_no_kern"], t["kern_pct"], t.get("cw_freq_model", "—"),
                     t.get("model_gap_pct", "—"), h["zero_ch"] / t["cw"], 66 * t["cw"],
                     f"{fmt(t.get('lh_no_collision_lower'), 3)}/{fmt(t.get('lh_no_collision_letters'), 3)}/{fmt(t.get('lh_no_collision_all'), 3)}",
                     t.get("line_start_white", "—"), t["missing"] or "—"])
    L.append("\nrunning text (corpus, advances + kerning, as a browser lays it out)\n"
             + table(rows, ["lang", "script", "chars", "char_em", "no_kern", "kern_%", "freq_model", "gap_%", "ch/char",
                            "66chars_em", "lh_min low/let/all", "start_white", "missing"], 4))
    L.append("  script: OpenType script of the text (its kerning lookups are the ones applied); * = needs complex shaping."
             "\n  char_em: average advance per character, kerned — use it for every measure (N × char_em em)."
             "\n  freq_model / gap_%: same value from a letter-frequency table — the gap is the model's uncertainty."
             "\n  lh_min: smallest unitless line-height with no ink contact between lines (lowercase / all letters incl."
             "\n  accented capitals / plus punctuation). start_white: average white before the first ink of a word.")
    warns = list(prof.get("notes", []))
    if v["platform_divergence"] is not None:
        warns.append(f"Windows builds the line box from usWin* (asc {fmt(v['windows']['asc'], 3)}) and the web from {v['web_source']}"
                     f" (asc {fmt(v['web']['asc'], 3)}): the baseline moves {fmt(abs(v['platform_divergence']), 3)}em"
                     f" between platforms. Pin it with ascent-override/descent-override/line-gap-override (--css).")
    for k, lab in (("x_height", "sxHeight"), ("cap_height", "sCapHeight")):
        if g[k] is not None and g[k + "_os2"] is not None and abs(g[k] - g[k + "_os2"]) > 0.005:
            warns.append(f"OS/2.{lab} {fmt(g[k + '_os2'], 3)} ≠ measured {fmt(g[k], 3)}: the profile uses the measured glyph.")
    for lang, t in prof["text"].items():
        if t["missing"]:
            warns.append(f"{lang}: the font lacks {t['missing']!r} — those characters fall back to another font.")
        if isinstance(t.get("model_gap_pct"), float) and abs(t["model_gap_pct"]) > 2:
            warns.append(f"{lang}: corpus and frequency model differ {fmt(t['model_gap_pct'])}%: measure your real copy with --sample.")
    if warns:
        L.append("\nwarnings:\n  " + "\n  ".join(warns))
    return "\n".join(L), m


def instances_table(path, a):
    """Every named instance of a variable font, measured: how the grid inputs move along the axes."""
    import fontread
    names = [i["name"] for i in fontread.load(path).instances]
    if not names:
        sys.exit(f"{path}: no named instances (not a variable font, or fvar without instances)")
    rows = []
    for n in names:
        prof = fontprofile.build(path, langs=(a.lang,), instance=n)
        m = profile_metrics(prof, a.lang)
        rows.append([n, " ".join(f"{k}={fmt(v)}" for k, v in prof["location"].items()), m["xh"], m["cap"], m["cw"],
                     m["zero"] / m["cw"], 66 * m["cw"], m["lh_letters"], m["asc"], m["desc"]])
    return (f"{os.path.basename(path)} · named instances · text {a.lang}\n"
            + table(rows, ["instance", "location", "x-height", "cap", "char_em", "ch/char", "66chars_em", "lh_min",
                           "asc", "desc"], 4)
            + "\n  every value is measured at that point of the design space (gvar/CFF2 outlines, HVAR advances,"
              "\n  MVAR metrics, variable kerning). Save one with: font <file> --instance <name> --save")


def cmd_font(a):
    if fontprofile is None:
        sys.exit("fontprofile.py is missing next to gridcalc.py")
    if not a.files:
        rows, seen = [], set()
        for key, path in fontprofile.available().items():
            if path in seen:
                continue
            seen.add(path)
            with open(path, encoding="utf-8") as fh:
                prof = json.load(fh)
            m = profile_metrics(prof, a.lang, strict=False)
            if m is None:
                rows.append([key] + ["—"] * 7 + [prof["vertical"]["web_source"], "-", "not covered"])
                continue
            rows.append([key, m["xh"], m["cap"], m["cw"], m["zero"], m["zero"] / m["cw"], 66 * m["cw"],
                         m["lh_letters"], prof["vertical"]["web_source"],
                         "!" if m["divergence"] is not None else "-", m["kern_pct"]])
        txt = (f"stored profiles (perfiles/) · text {a.lang}\n"
               + table(rows, ["profile", "x-height", "cap", "char_em", "ch_em", "ch/char", "66chars_em", "lh_min",
                              "line box", "win≠web", "kern_%"], 4)
               + "\n  ch/char > 1: `Nch` holds MORE than N real characters. Write measures in em: N × char_em."
                 "\n  lh_min: line-height under which accented capitals touch the descenders of the line above."
                 "\n  win≠web '!': the line box differs between Windows and the other platforms (see `font <file> --css`)."
                 "\n  measure a new font: gridcalc.py font <file.woff2|ttf|otf> [--save] [--css] [--sample text.txt]")
        emit(a, {"profiles": rows}, txt)
        return
    outs, data = [], []
    fb = load_profile(a.fallback) if a.fallback else None
    axes = fontprofile.parse_axes(a.axes)
    for path in a.files:
        if a.size and a.optical_sizing == "auto" and "opsz" not in axes:
            import fontread
            ax = next((x for x in fontread.load(path).axes if x["tag"] == "opsz"), None)
            if ax:  # measured as the browser draws it at that size
                axes = {**axes, "opsz": round(min(max(a.size, ax["min"]), ax["max"]), 2)}
        if not os.path.isfile(path):
            sys.exit(f"no such file: {path}")
        try:
            if a.instances:
                outs.append(instances_table(path, a))
                continue
            prof = fontprofile.build(path, sample=a.sample, axes=axes, instance=a.instance)
        except ValueError as e:  # fontread.FontError and malformed WOFF2/Brotli data
            sys.exit(f"{path}: {e}")
        txt, m = font_report(prof, a)
        if a.save:
            txt += f"\n\nsaved: {fontprofile.save(prof)}"
        if a.css or fb:
            txt += "\n\n" + font_css(prof, m, fb)
        outs.append(txt)
        data.append(prof)
    emit(a, data if len(data) > 1 else (data[0] if data else outs), "\n\n".join(outs))


def cmd_lines(a):
    """What a measure gives once the text is really set: lines, characters, rag."""
    import linebreak
    a.font = a.typeface
    T = Typeface(a, a.typeface)
    s = T.setter(a.size, firefox=a.engine == "firefox")
    if s is None:
        sys.exit("lines needs the font file (or a stored profile whose file still exists) and a corpus language or --sample")
    m = T.at(a.size)
    widths = [(f"{c} cap", c * m["cw"]) for c in nums(a.capacities, int)]
    if a.width:
        widths.append(("given", a.width))
    target = linebreak.solve(s, a.measure)
    widths.append((f"avg {a.measure}", target))
    rows = []
    for label, w in widths:
        st = linebreak.stats(s.set(w), w)
        rows.append([label, w, w * a.size, st["lines"], st["chars_mean"], f"{fmt(st['chars_p5'], 0)}–{fmt(st['chars_p95'], 0)}",
                     st["chars_max"], st["over_limit"], 100 * st["fill_mean"], 100 * st["rag"], 100 * st["short"],
                     100 * st["runts"], st["overflow"]])
    txt = (f"{m['name']} · {m['lang']} · {fmt(a.size)}px{' · opsz ' + fmt(m['opsz']) if m.get('opsz') else ''}"
           f" · engine {a.engine} · first-fit line breaking, no hyphenation (CSS text-wrap: wrap, hyphens: manual)\n"
           + table(rows, ["measure", "em", "px", "lines", "chars_avg", "chars_90%", "longest", ">80", "fill_%", "rag_%",
                          "short_%", "runts_%", "overflow"], 2)
           + f"\n\n  for lines that AVERAGE {a.measure} characters: max-inline-size: {fmt(target, 3)}em"
             f" ({fmt(target / m['cw'], 1)} chars of capacity; {fmt(target / m['zero'], 1)}ch)"
             "\n  chars_90%: 90 % of lines fall in that range · longest: WCAG 1.4.8 asks ≤ 80 · fill: line length / measure"
             "\n  rag: spread of line ends (sd of fill) · short: lines under 85 % of the measure (not counting paragraph ends)"
             "\n  runts: paragraphs ending in a single word · measured against Chrome: identical breaks (metricas-de-fuente.md §9)")
    emit(a, {"rows": rows, "target_width_em": target}, txt)


def measure_line(T, N, Nc, fs_lo, fs_hi, m, m_hi):
    lo, hi = T.measure(fs_lo, N), T.measure(fs_hi, N)
    if not lo:
        return (f"\nmeasure {N} chars = {fmt(N * m['cw'], 2)}em (= {fmt(N * m['cw'] / m['zero'], 1)}ch) — CAPACITY: real lines"
                f" average ~6 % fewer characters; pass the font file to set them · card text ≥ {Nc} chars")
    st = lo[1]
    txt = (f"\nmeasure {N} chars = average of the lines actually set → {fmt(lo[0], 3)}em"
           f" (= {fmt(lo[0] / m['zero'], 1)}ch, capacity {fmt(lo[0] / m['cw'], 1)} chars)")
    if abs(hi[0] - lo[0]) > 0.005:
        txt += f" @ {fmt(fs_lo)}px … {fmt(hi[0], 3)}em @ {fmt(fs_hi)}px"
    return (txt + f"\n  lines: 90 % between {fmt(st['chars_p5'], 0)} and {fmt(st['chars_p95'], 0)} chars, longest {st['chars_max']}"
            f" · rag ±{fmt(100 * st['rag'], 1)}% of the measure · one-word last lines {fmt(100 * st['runts'], 0)}%"
            f" · card text ≥ {Nc} chars")


def cmd_compose(a):
    T = Typeface(a, a.font)
    use = USES[a.use]
    N_asked = a.measure or use["measure"]
    N = T.fit(fs_lo_ := (nums(a.body) + nums(a.body))[0], N_asked)   # no line over 80, for this font
    Nc = a.card_chars or use["card"]
    r = parse_ratio(a.ratio) if a.ratio else use["ratio"]
    d = DENSITY[a.density]
    dens_f = parse_ratio(a.type_ratio) ** d          # density steps along the TYPE scale ratio
    fs_lo, fs_hi = (nums(a.body) + nums(a.body))[:2]
    v_lo, v_hi = nums(a.range)
    q = a.unit_step
    m, m_hi = T.at(fs_lo), T.at(fs_hi)
    out, warns = {}, []

    def body_leading(mm):
        lh_ = leading(mm, N, a.lh_floor)
        return max(lh_, mm.get("lh_lower") or 0)  # never let lowercase ink of consecutive lines touch

    def block(fs):
        mm = T.at(fs)
        u_raw = fs * body_leading(mm)
        u = snap(u_raw, q) if a.snap_baseline else u_raw
        lh_eff = u / fs
        # optical vertical padding: half-leading + (ascent − cap) above, half-leading + descent below
        half = (lh_eff - (mm["asc"] + mm["desc"])) / 2
        opt_top = (half + mm["asc"] - mm["cap"]) * fs
        opt_bot = (half + mm["desc"]) * fs
        # proximity chain anchored at gutter = one line (print practice), each level r × the inner one
        g = u * dens_f
        chain = dict(micro=g / r ** 3, inner=g / r ** 2, padding=g / r, gutter=g, section=g * r ** 2)
        chain = {k: max(snap(v, q / 2, up=False), q / 2) for k, v in chain.items()}
        return dict(fs=fs, lh=lh_eff, u=u, opt_top=opt_top, opt_bot=opt_bot, **chain)

    lo, hi = block(fs_lo), block(fs_hi)
    css = {}
    mu = use["mu"]
    # small screens: margin = μ·v but never < 16 (reflow) nor > one gutter; the gutter follows it down
    lo["margin"] = max(16, min(lo["gutter"], snap(use.get("mu_lo", mu) * v_lo, q / 2, up=False)))
    lo["gutter"] = min(lo["gutter"], lo["margin"])
    hi["margin"] = max(hi["gutter"], 16, snap(mu * v_hi, q / 2, up=False))
    for k in ("u", "micro", "inner", "padding", "gutter", "margin", "section"):
        css[k] = clamp_css(lo[k], hi[k], v_lo, v_hi, a.root)[0]
    pad_block = {x: max(b["padding"] - (b["opt_top"] + b["opt_bot"]) / 2, b["micro"]) for x, b in (("lo", lo), ("hi", hi))}

    # per-viewport composition
    rows = []
    divisors = [d_ for d_ in range(1, a.columns + 1) if a.columns % d_ == 0]
    for vw in nums(a.viewports):
        t = 0 if vw <= v_lo else 1 if vw >= v_hi else (vw - v_lo) / (v_hi - v_lo)
        B = {k: lo[k] + (hi[k] - lo[k]) * t for k in lo}
        g, mg = B["gutter"], B["margin"]
        W = min(vw - 2 * mg, a.max) if a.max else vw - 2 * mg
        # columns in use: the largest divisor of the grid whose column is still ≥ 1.5 × gutter
        cands = [n for n in divisors if n >= min(4, a.columns) and (W - (n - 1) * g) / n >= 1.5 * g]
        n_use = max(cands) if cands else 1
        col = (W - (n_use - 1) * g) / n_use
        span = lambda k: k * col + (k - 1) * g
        cw_px = T.at(B["fs"])["cw"] * B["fs"]   # the font as drawn at this body size (opsz auto)
        ms, mc = T.measure(B["fs"], N), T.measure(B["fs"], Nc)
        prose_px = ms[0] * B["fs"] if ms else N * cw_px   # lines that AVERAGE N characters (set, not capacity)
        prose_cols = next((k for k in range(1, n_use + 1) if span(k) >= prose_px), n_use)
        card_min = (mc[0] * B["fs"] if mc else Nc * cw_px) + 2 * B["padding"]
        per_row = max([dv for dv in range(1, n_use + 1) if n_use % dv == 0 and span(n_use // dv) >= card_min] or [1])
        chars_full = W / cw_px
        rows.append([vw, B["fs"], B["u"], mg, g, W, n_use, col, col / g, f"{prose_cols}/{n_use}", chars_full, card_min, per_row])
        if chars_full < N and vw > 600:
            pass
        if W / cw_px < 30:
            warns.append(f"{fmt(vw)}px: only {fmt(W / cw_px, 0)} chars fit across — reduce margin or body size.")
        if card_min > W:
            warns.append(f"{fmt(vw)}px: a card ({Nc} chars + padding = {fmt(card_min)}px) does not fit — lower --card-chars or padding.")
    # text density
    dens = 1000 / (m["cw"] * fs_lo * lo["lh"] * fs_lo)
    cal_use = a.use in CALIBRATION.get("uses", {})
    head = ((f"calibrated: {len(CALIBRATION.get('referencias', []))} references measured {CALIBRATION.get('fecha')}"
             f" (use {a.use}{'' if cal_use else ' NOT calibrated — no references of this kind'}: target {N_asked} real chars/line"
             f"{'' if N == N_asked else f', lowered to {N} so no line exceeds {LONGEST}'})\n"
             if CALIBRATION else f"uncalibrated defaults{'' if N == N_asked else f' · measure lowered to {N}: no line over {LONGEST}'}\n")
            + f"font {m['name']} (sha1 {m['sha1']}) · text {m['lang']} · x-height {fmt(m['xh'],3)} · cap {fmt(m['cap'],3)}"
            f" · line box asc {fmt(m['asc'],3)} desc {fmt(m['desc'],3)}"
            f"\nchar {fmt(m['cw'],4)}em (kerned, {fmt(m['kern_pct'],2)}% kerning) · ch/char {fmt(m['zero']/m['cw'],2)} · use {a.use} · density {a.density}"
            + measure_line(T, N, Nc, fs_lo, fs_hi, m, m_hi)
            + f"\nleading {fmt(lo['lh'],3)} → baseline u {fmt(lo['u'])}px @ {fmt(fs_lo)}px … {fmt(hi['u'])}px @ {fmt(fs_hi)}px"
            f" · text density {fmt(dens,2)} chars/1000px²"
            + (f"\noptical size: auto (opsz = font-size px, as browsers do) → body opsz {fmt(m['opsz'])}…{fmt(m_hi['opsz'])}:"
               f" char {fmt(m['cw'],4)}→{fmt(m_hi['cw'],4)}em · x-height {fmt(m['xh'],3)}→{fmt(m_hi['xh'],3)}"
               if T.opsz else "") + "\n")
    chain_rows = [[k, lo[k], hi[k], css[k]] for k in ("micro", "inner", "padding", "gutter", "margin", "section")]
    txt = head + "\nspatial chain (ratio " + fmt(r, 3) + f", density ×{fmt(dens_f,3)} on padding→section)\n"
    txt += table(chain_rows, ["level", f"@{fmt(v_lo)}", f"@{fmt(v_hi)}", "clamp()"])
    txt += (f"\n  padding-block (optical, no text-box-trim): {fmt(pad_block['lo'])} → {fmt(pad_block['hi'])}px"
            f"  [inline padding minus the white the line box already adds: ≈{fmt((lo['opt_top']+lo['opt_bot'])/2)}px]"
            f"\n  with text-box: trim-both cap alphabetic → padding-block = padding-inline"
            + (f"\n  ! text-box trims at the DECLARED cap height (OS/2 {fmt(m['cap_declared'], 4)}em), not the drawn one"
               f" ({fmt(m['cap'], 4)}em): the capitals' ink {'overflows' if m['cap'] > m['cap_declared'] else 'falls short of'}"
               f" the trimmed edge by {fmt(abs(m['cap'] - m['cap_declared']) * fs_hi, 2)}px @ {fmt(fs_hi)}px (measured in Chrome, Edge and Firefox)"
               if m.get("cap_declared") and abs(m["cap"] - m["cap_declared"]) > 0.002 else ""))
    if CALIBRATION.get("paragraph_gap_lines"):
        pg = CALIBRATION["paragraph_gap_lines"]
        q4 = [snap(pg * b["u"], b["u"] / 4, up=False) / b["u"] for b in (lo, hi)]
        txt += (f"\n  paragraph spacing: {fmt(q4[0], 2)} line ({fmt(q4[0] * lo['u'])}px → {fmt(q4[1] * hi['u'])}px) ="
                f" margin-block: {fmt(q4[0], 2)}lh — references median {fmt(pg, 2)} lines, on the u/4 grid")
    if m.get("start_white"):
        txt += (f"\n  padding-inline (optical): the first letter already brings ≈{fmt(m['start_white'] * fs_lo, 2)}px"
                f" → {fmt(m['start_white'] * fs_hi, 2)}px of white ({fmt(m['start_white'], 4)}em);"
                f" subtract it to align ink, not boxes: calc(var(--padding) - {fmt(m['start_white'], 4)}em)")
    # headings on the baseline grid: the type scale's line-heights are the smallest multiple of u/k
    # that keeps the ink of accented capitals clear of the descenders of the line above
    tr, lh_min = parse_ratio(a.type_ratio), (m.get("lh_letters") or 1.0)
    hrows = []
    for step in range(1, a.heading_steps + 1):
        row = [f"+{step}"]
        for B_ in (lo, hi):
            size = B_["fs"] * tr ** step
            mh = T.at(size)                       # each heading size is its own optical size
            lhp = snap(size * (mh.get("lh_letters") or lh_min), B_["u"] / a.heading_division)
            row += [size] + ([mh["opsz"], mh["cw"]] if T.opsz else []) + [lhp, lhp / size]
        hrows.append(row)
    oh = ["opsz", "char_em"] if T.opsz else []
    txt += (f"\n\nheadings on the baseline grid (scale {fmt(tr, 3)}; line-height = smallest multiple of u/{a.heading_division} ≥ lh_min × size,"
            f" the no-collision minimum of this font + language{' at each optical size' if T.opsz else f' ({fmt(lh_min, 3)})'})\n"
            + table(hrows, ["step", f"size@{fmt(v_lo)}"] + oh + ["lh_px", "lh", f"size@{fmt(v_hi)}"] + oh + ["lh_px", "lh"], 3))
    txt += "\n\ncomposition per viewport\n" + table(rows, ["vw", "body", "u", "margin", "gutter", "content", "cols", "col", "col/g",
                                                     "prose_cols", "chars_full", "card_min", "cards/row"])
    txt += ("\n\n  cols: columns in use (largest divisor of the grid with column ≥ 1.5 × gutter) — the grid keeps its lines, the layout uses fewer."
            "\n  prose_cols: columns a text block needs to reach the measure (stop there, never full width)."
            "\n  cards/row: largest divisor of the grid whose span still fits a card's text measure + padding.")
    # chain checks
    for B_, tag in ((lo, "min"), (hi, "max")):
        order = [B_[k] for k in ("micro", "inner", "padding", "gutter")] + [B_["margin"]]
        if any(b >= c for b, c in zip(order, order[1:-1])) or B_["margin"] < B_["gutter"]:
            warns.append(f"{tag}: proximity order broken (micro < inner < padding < gutter ≤ margin).")
        if B_["gutter"] < B_["u"]:
            warns.append(f"{tag}: gutter {fmt(B_['gutter'])} < one line ({fmt(B_['u'])}): fine between boxed cards, too tight between adjacent text columns.")
    if m.get("cw_firefox") and abs(m["cw_firefox"] - m["cw"]) / m["cw"] > 0.001:
        warns.append(f"Firefox does not kern across spaces (it shapes word by word): text is {fmt(100 * (m['cw_firefox'] / m['cw'] - 1), 2)}%"
                     f" {'wider' if m['cw_firefox'] > m['cw'] else 'narrower'} there (char {fmt(m['cw_firefox'], 4)}em) — measured")
    for fs_, tag in ((fs_lo, "min"), (fs_hi, "max")):
        mm_ = T.measure(fs_, N)
        if mm_ and mm_[1]["over_limit"]:
            warns.append(f"{tag}: {mm_[1]['over_limit']} line(s) over 80 characters at that measure (WCAG 1.4.8): lower --measure")
    if T.frozen_opsz:
        warns.append(f"{m['name']} has an opsz axis, but a stored profile is frozen at one optical size: pass the font FILE"
                     f" so each size is measured at its own opsz, as the browser draws it")
    if m.get("divergence") is not None:
        warns.append(f"line box differs on Windows ({fmt(m['divergence'], 3)}em of ascent): pin it with the @font-face overrides"
                     f" from `gridcalc.py font <file> --css`, or baselines will not match across platforms.")
    if m.get("lh_letters") and lo["lh"] < m["lh_letters"]:
        warns.append(f"body leading {fmt(lo['lh'], 3)} < {fmt(m['lh_letters'], 3)}: accented capitals can touch descenders above.")
    if warns:
        txt += "\n\nwarnings:\n  " + "\n  ".join(dict.fromkeys(warns))
    emit(a, {"metrics": m, "metrics_max": m_hi, "optical_sizing": "auto" if T.opsz else "off", "leading": lo["lh"], "headings": hrows, "min": lo, "max": hi, "css": css, "rows": rows, "warnings": warns}, txt)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("clamp", help="fluid value between two viewports")
    s.add_argument("--min", type=float, required=True, help="value (px) at --vmin")
    s.add_argument("--max", type=float, required=True, help="value (px) at --vmax")
    s.add_argument("--vmin", type=float, default=360)
    s.add_argument("--vmax", type=float, default=1440)
    s.add_argument("--root", type=float, default=16)
    s.add_argument("--unit", default="vw", help="vw for page, cqi for container-relative")
    s.add_argument("--check", help="viewports to evaluate, e.g. 320,768,1440")
    s.set_defaults(fn=cmd_clamp)

    s = sub.add_parser("scale", help="modular scale")
    s.add_argument("--base", type=float, default=16)
    s.add_argument("--ratio", default="major-third", help=f"number, a:b, or {', '.join(NAMED_RATIOS)}")
    s.add_argument("--steps", default="-2..6")
    s.add_argument("--snap", type=float, default=0, help="round to multiples of this (e.g. 4)")
    s.add_argument("--root", type=float, default=16)
    s.set_defaults(fn=cmd_scale)

    s = sub.add_parser("ratio", help="integer column split for a ratio")
    s.add_argument("--ratio", required=True)
    s.add_argument("--columns", default="5,6,8,10,12,13,16,24")
    s.set_defaults(fn=cmd_ratio)

    s = sub.add_parser("compound", help="overlay column divisions")
    s.add_argument("--divisions", required=True, help="e.g. 3,4 or 2,3,5")
    s.set_defaults(fn=cmd_compound)

    s = sub.add_parser("web", help="column grid at viewports")
    s.add_argument("--columns", type=int, default=12)
    s.add_argument("--gutter", default="24", help="px, or min,max for fluid (needs --range)")
    s.add_argument("--margin", default="16", help="px, or min,max for fluid (needs --range)")
    s.add_argument("--max", type=float, default=0, help="max content width px (0 = none)")
    s.add_argument("--range", help="vmin,vmax for fluid values, e.g. 360,1440")
    s.add_argument("--viewports", default="320,375,600,768,1024,1280,1440,1920")
    s.add_argument("--font", type=float, default=16, help="body px for measure")
    s.add_argument("--char-em", type=float, default=0.5, help="avg char width in em (overridden by --font)")
    s.add_argument("--typeface", help="profile name or font file: takes char-em from the measured font")
    s.add_argument("--lang", default="es")
    s.add_argument("--axes", help="variable fonts: point of the design space, e.g. wght=700,opsz=24")
    s.add_argument("--instance", help="variable fonts: a named instance from fvar, e.g. Bold")
    s.add_argument("--optical-sizing", choices=["auto", "none"], default="auto",
                   help="variable fonts with opsz: auto = opsz follows the size (browser default)")
    s.add_argument("--root", type=float, default=16)
    s.add_argument("--emit", choices=["none", "css"], default="none")
    s.set_defaults(fn=cmd_web)

    s = sub.add_parser("print", help="Müller-Brockmann modular grid")
    s.add_argument("--page", required=True, help="w,h")
    s.add_argument("--margins", required=True, help="top,bottom,inner,outer")
    s.add_argument("--unit", choices=["mm", "pt"], default="mm")
    s.add_argument("--leading", type=float, required=True, help="pt")
    s.add_argument("--columns", type=int, default=6)
    s.add_argument("--gutter", type=float, help="column gutter in --unit (default = 1 leading)")
    s.add_argument("--rows", default="2,3,4,5,6,8")
    s.add_argument("--row-gutter-lines", type=int, default=1)
    s.add_argument("--typeface", help="profile name or font file -> first-baseline offsets measured on the glyphs")
    s.add_argument("--axes", help="variable fonts: point of the design space, e.g. wght=700,opsz=24")
    s.add_argument("--instance", help="variable fonts: a named instance from fvar, e.g. Bold")
    s.add_argument("--optical-sizing", choices=["auto", "none"], default="auto",
                   help="variable fonts with opsz: auto = opsz follows the size (browser default)")
    s.add_argument("--size", type=float, help="body size in pt (with --typeface)")
    s.add_argument("--lang", default="es")
    s.set_defaults(fn=cmd_print)

    s = sub.add_parser("canon", help="classical page canons")
    s.add_argument("--page", required=True, help="w,h (any unit)")
    s.add_argument("--method", choices=["vandegraaf", "ninths", "twelfths", "ratio", "all"], default="all")
    s.add_argument("--ratios", default="2,3,4,6", help="inner,top,outer,bottom for --method ratio")
    s.add_argument("--block", type=float, default=0.70, help="text block width as fraction of page (ratio method)")
    s.set_defaults(fn=cmd_canon)

    s = sub.add_parser("paper", help="ISO 216 sizes")
    s.add_argument("--series", help="A, B or C")
    s.set_defaults(fn=cmd_paper)

    s = sub.add_parser("rhythm", help="Euclidean rhythm E(k,n) to place accents")
    s.add_argument("--k", type=int, required=True)
    s.add_argument("--n", type=int, required=True)
    s.add_argument("--rotate", type=int, default=0)
    s.set_defaults(fn=cmd_rhythm)

    s = sub.add_parser("tracks", help="progressive track sizes (fibonacci, geometric...)")
    s.add_argument("--series", choices=["fibonacci", "geometric", "arithmetic", "harmonic"], default="fibonacci")
    s.add_argument("--count", type=int, default=5)
    s.add_argument("--ratio", default="golden")
    s.add_argument("--step", type=float, default=0.5)
    s.add_argument("--mirror", choices=["odd", "even"], help="symmetric sequence around the centre")
    s.set_defaults(fn=cmd_tracks)

    s = sub.add_parser("svg", help="draw a grid diagram (page or viewport) as SVG")
    s.add_argument("--size", required=True, help="w,h in any unit (px for screens, mm for print)")
    s.add_argument("--margins", required=True, help="top,bottom,inner(left),outer(right)")
    s.add_argument("--columns", type=int, default=12)
    s.add_argument("--gutter", type=float, default=0)
    s.add_argument("--rows", type=int, default=0)
    s.add_argument("--row-gutter", type=float, default=0)
    s.add_argument("--baseline", type=float, default=0, help="baseline increment in same unit")
    s.add_argument("--out")
    s.set_defaults(fn=cmd_svg)

    s = sub.add_parser("font", help="read a font file: vertical metrics, measured ink, spacing, kerned text width")
    s.add_argument("files", nargs="*", help="font files (ttf, otf, woff, woff2, ttc); none = list stored profiles")
    s.add_argument("--lang", default="es", help="language of the summary: es, en, fr, de, it, pt")
    s.add_argument("--sample", help="text file with your real copy: measured with this font's advances + kerning")
    s.add_argument("--save", action="store_true", help="store the profile in perfiles/")
    s.add_argument("--css", action="store_true", help="emit @font-face overrides and custom properties")
    s.add_argument("--fallback", help="profile of a local fallback (e.g. arial) -> size-adjust + overrides")
    s.add_argument("--instances", action="store_true", help="variable fonts: measure every named instance")
    s.add_argument("--size", type=float, help="text size in px: a font with an opsz axis is measured at that optical size")
    s.add_argument("--axes", help="variable fonts: point of the design space, e.g. wght=700,opsz=24")
    s.add_argument("--instance", help="variable fonts: a named instance from fvar, e.g. Bold")
    s.add_argument("--optical-sizing", choices=["auto", "none"], default="auto",
                   help="variable fonts with opsz: auto = opsz follows the size (browser default)")
    s.set_defaults(fn=cmd_font)

    s = sub.add_parser("lines", help="set the text into measures and report the real lines (chars, rag, longest)")
    s.add_argument("--typeface", default="inter", help="profile name or font file")
    s.add_argument("--lang", default="es")
    s.add_argument("--sample", help="text file with your copy (paragraphs separated by line breaks)")
    s.add_argument("--size", type=float, default=16, help="body px (a font with opsz is set at that optical size)")
    s.add_argument("--measure", type=int, default=66, help="target AVERAGE characters per line")
    s.add_argument("--capacities", default="45,55,66,75", help="capacities (chars × char_em) to compare")
    s.add_argument("--width", type=float, help="also report this measure, in em")
    s.add_argument("--engine", choices=["chrome", "firefox"], default="chrome",
                   help="firefox: no kerning across spaces when the font makes it shape word by word")
    s.add_argument("--axes", help="variable fonts: e.g. wght=700,opsz=24")
    s.add_argument("--instance", help="variable fonts: a named instance")
    s.add_argument("--optical-sizing", choices=["auto", "none"], default="auto")
    s.set_defaults(fn=cmd_lines)

    s = sub.add_parser("compose", help="multidisciplinary solver: type + use + density -> leading, measure, padding, gutter, margin, columns")
    s.add_argument("--font", default="inter", help="profile name (see `font`) or a font file")
    s.add_argument("--lang", default="es", help="language of the copy: es, en, fr, de, it, pt")
    s.add_argument("--sample", help="text file with the real copy (needs --font as a file)")
    s.add_argument("--axes", help="variable fonts: point of the design space, e.g. wght=700,opsz=24")
    s.add_argument("--instance", help="variable fonts: a named instance from fvar, e.g. Bold")
    s.add_argument("--optical-sizing", choices=["auto", "none"], default="auto",
                   help="variable fonts with opsz: auto = opsz follows the size (browser default)")
    s.add_argument("--heading-steps", type=int, default=4, help="type-scale steps above body to fit on the baseline grid")
    s.add_argument("--heading-division", type=int, default=4, help="heading line-heights snap to u/this (2 = half lines)")
    for k in ("xh", "cap", "asc", "desc", "cw", "zero"):
        s.add_argument(f"--{k}", type=float, help=f"override metric {k} (em)")
    s.add_argument("--use", choices=list(USES), default="scanning")
    s.add_argument("--density", choices=list(DENSITY), default="default")
    s.add_argument("--body", default="16,18", help="body px at vmin,vmax")
    s.add_argument("--range", default="360,1440")
    s.add_argument("--viewports", default="320,375,600,768,1024,1280,1440,1920")
    s.add_argument("--columns", type=int, default=12)
    s.add_argument("--max", type=float, default=0, help="max content width px")
    s.add_argument("--measure", type=int, help="override target chars per line")
    s.add_argument("--card-chars", type=int, help="override min chars per line inside a card")
    s.add_argument("--ratio", help="spacing chain ratio (default by use)")
    s.add_argument("--type-ratio", default="major-third", help="type scale ratio; density steps along it")
    s.add_argument("--lh-floor", type=float, default=1.5)
    s.add_argument("--unit-step", type=float, default=4, help="snap baseline unit to this px")
    s.add_argument("--snap-baseline", action="store_true", default=True)
    s.add_argument("--root", type=float, default=16)
    s.set_defaults(fn=cmd_compose)

    for sp in sub.choices.values():
        sp.add_argument("--json", action="store_true")
        sp.add_argument("--sin-calibracion", action="store_true", help="ignore calibracion.json (uncalibrated defaults)")
    a = p.parse_args()
    if not getattr(a, "sin_calibracion", False):
        apply_calibration()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles/redirections default to a legacy code page
    a.fn(a)


if __name__ == "__main__":
    main()
