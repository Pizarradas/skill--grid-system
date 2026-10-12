#!/usr/bin/env python3
"""calibrar — fits the system's composition models to measured references, inside the evidence's bounds.

  python3 calibrar.py [--referencias referencias/] [--escribir]

Reads the pages measured by medir_sitio.py (referencias/*.json) and, for each model gridcalc uses:

  leading      lh = a + b·xh + λ·(N/66 − 1)  (xh of the font in use, N the real characters per line)
               fitted by least squares; compared by leave-one-out error with the current model and with
               a constant, so 13 noisy references do not buy a complicated model by accident
  measure      real characters per line by use profile: the median of the references, capped by the
               evidence (45–75 average, Bringhurst; no line over 80, WCAG 1.4.8 — enforced per font by
               gridcalc through line simulation)
  margin       page margin on phones (375 px), by use profile
  paragraphs   space between paragraphs, in lines
  headings     type-scale ratio implied by h2/body, and heading line-height

Evidence bounds are not calibrated: line-height ≥ 1.5 (WCAG 1.4.8) stays a floor even where references go
below it (law L9). With --escribir the result goes to calibracion.json, which gridcalc reads. Stdlib only.
"""
import argparse
import datetime
import glob
import json
import os
import statistics as st
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
GENERIC = {"serif", "sans-serif", "monospace", "system-ui", "-apple-system", "blinkmacsystemfont"}
CURRENT = dict(a=0.95, b=1.0, lam=0.2)        # the model gridcalc used before calibration
BOUNDS = dict(lh_floor=1.5, measure_min=45, measure_max=75, longest=80, margin_min=16)


def load(folder):
    out = []
    for p in sorted(glob.glob(os.path.join(folder, "*.json"))):
        with open(p, encoding="utf-8") as fh:
            r = json.load(fh)
        d, m = r["viewports"].get("1440", {}), r["viewports"].get("375", {})
        if not d or "error" in d or not d.get("chars_per_line"):
            continue
        ff = d.get("font_file") or {}
        xh = ff.get("x_height") or d.get("x_height_canvas")
        h = d.get("headings", {})
        out.append(dict(
            file=os.path.basename(p), url=r["url"], uso=r.get("uso"), grupo=r.get("grupo"), medido=r.get("medido"),
            title=d.get("title", "")[:50], font=d.get("font_used"), size=d["size"], lh=d.get("lh_ratio"),
            xh=xh, xh_source="file" if ff.get("x_height") else "canvas",
            generic=(d.get("font_used") or "").lower() in GENERIC,
            cpl=st.mean(d["chars_per_line"]), longest=max(d["chars_per_line"]), lines=len(d["chars_per_line"]),
            gap=(d["para_gap_px"] / d["line_height"]) if d.get("para_gap_px") is not None and d.get("line_height") else None,
            margin375=m.get("margin_left") if m and "error" not in m and m.get("responsive") else None,
            h2=(h["h2"]["size"] / d["size"]) if "h2" in h else None,
            h2lh=(h["h2"]["lh"] / h["h2"]["size"]) if "h2" in h and h["h2"].get("lh") else None))
    return out


def solve3(rows):
    """Least squares for lh = a + b·xh + λ·(N/66 − 1) (3×3 normal equations, Gaussian elimination)."""
    X = [[1.0, r["xh"], r["cpl"] / 66 - 1] for r in rows]
    y = [r["lh"] for r in rows]
    A = [[sum(x[i] * x[j] for x in X) for j in range(3)] + [sum(x[i] * v for x, v in zip(X, y))] for i in range(3)]
    for c in range(3):
        piv = max(range(c, 3), key=lambda r: abs(A[r][c]))
        A[c], A[piv] = A[piv], A[c]
        for r in range(3):
            if r != c and A[c][c]:
                f = A[r][c] / A[c][c]
                A[r] = [u - f * v for u, v in zip(A[r], A[c])]
    a, b, lam = (A[i][3] / A[i][i] for i in range(3))
    return dict(a=a, b=b, lam=lam)


def solve2(rows):
    """lh − xh = a + λ·(N/66 − 1): the current model's shape (white between x-height bands), refitted."""
    xs = [r["cpl"] / 66 - 1 for r in rows]
    ys = [r["lh"] - r["xh"] for r in rows]
    mx, my = st.mean(xs), st.mean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    lam = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx if sxx else 0.0
    return dict(a=my - lam * mx, b=1.0, lam=lam)


def predict(m, r):
    return m["a"] + m["b"] * r["xh"] + m["lam"] * (r["cpl"] / 66 - 1)


def loo(rows, fit):
    errs = []
    for i in range(len(rows)):
        train = rows[:i] + rows[i + 1:]
        m = fit(train) if fit else None
        p = predict(m, rows[i]) if m else st.mean(x["lh"] for x in train)
        errs.append(p - rows[i]["lh"])
    return (sum(e * e for e in errs) / len(errs)) ** 0.5


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--referencias", default=os.path.join(HERE, "referencias"))
    ap.add_argument("--escribir", action="store_true", help="write calibracion.json for gridcalc")
    a = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    refs = load(a.referencias)
    if len(refs) < 5:
        sys.exit(f"only {len(refs)} usable references: measure more with medir_sitio.py")
    print(f"{len(refs)} references ({', '.join(sorted({r['grupo'] or '?' for r in refs}))})\n")

    # ---- leading
    fitset = [r for r in refs if r["lh"] and r["xh"] and not r["generic"]]
    m3, m2 = solve3(fitset), solve2(fitset)
    cands = {"current (a 0.95, λ 0.2)": (lambda rows: CURRENT, CURRENT),
             "refit a, λ (x-height slope 1)": (solve2, m2),
             "refit a, b, λ": (solve3, m3),
             "constant (median)": (None, None)}
    scores = {k: loo(fitset, f) for k, (f, _) in cands.items()}
    best = min(scores, key=scores.get)
    print(f"leading model — leave-one-out RMSE of line-height on {len(fitset)} references with a known font")
    for k, v in scores.items():
        print(f"  {k:32} {v:.4f}{'   ← best' if k == best else ''}")
    chosen = cands[best][1] or dict(a=st.median(r["lh"] for r in fitset), b=0.0, lam=0.0)
    print(f"  chosen: lh = {chosen['a']:.3f} + {chosen['b']:.3f}·xh + {chosen['lam']:.3f}·(N/66 − 1),"
          f" floored at {BOUNDS['lh_floor']} (WCAG 1.4.8, not calibrated)")
    below = [r for r in refs if r["lh"] and r["lh"] < BOUNDS["lh_floor"]]
    print(f"  {len(below)} of {len(refs)} references set body text below {BOUNDS['lh_floor']}: "
          + ", ".join(f"{r['title'][:22]} {r['lh']:.2f}" for r in below))

    # ---- measure by use
    uses = {}
    print("\nreal characters per line by use (1440 px)")
    for uso in ("reading", "scanning", "operating"):
        rs = [r for r in refs if r["uso"] == uso]
        if not rs:
            print(f"  {uso:9} no references: keeps its uncalibrated value (measure pages of that kind to calibrate it)")
            continue
        med = st.median(r["cpl"] for r in rs)
        over = [r for r in rs if r["longest"] > BOUNDS["longest"]]
        target = min(max(round(med), BOUNDS["measure_min"]), BOUNDS["measure_max"])
        uses[uso] = dict(measure=target, reference_median=round(med, 1), n=len(rs))
        print(f"  {uso:9} median {med:.1f} (range {min(r['cpl'] for r in rs):.0f}–{max(r['cpl'] for r in rs):.0f}, n={len(rs)})"
              f" → target average {target}; {len(over)} reference(s) have lines over {BOUNDS['longest']}"
              f" ({', '.join(r['title'][:18] for r in over)})")
        for g in sorted({r["grupo"] for r in rs}):
            gs = [r["cpl"] for r in rs if r["grupo"] == g]
            print(f"            {g}: median {st.median(gs):.1f} (n={len(gs)})")
    print(f"  gridcalc lowers the target per font until no line exceeds {BOUNDS['longest']} characters")

    # ---- margins, paragraphs, headings
    marg = {}
    print("\npage margin at 375 px (responsive references)")
    for uso in ("reading", "scanning"):
        ms = [r["margin375"] for r in refs if r["uso"] == uso and r["margin375"]]
        if ms:
            marg[uso] = st.median(ms)
            print(f"  {uso:9} median {marg[uso]:.1f}px (range {min(ms):.0f}–{max(ms):.0f}) → μ = {marg[uso] / 375:.4f}")
    gaps = [r["gap"] for r in refs if r["gap"]]
    gap = st.median(gaps)
    print(f"\nparagraph spacing: median {gap:.2f} lines (range {min(gaps):.2f}–{max(gaps):.2f}, n={len(gaps)})")
    h2s = [r["h2"] for r in refs if r["h2"] and r["h2"] > 1.05]
    h2lh = [r["h2lh"] for r in refs if r["h2lh"]]
    ratio = st.median(h2s) ** 0.5
    print(f"headings: h2/body median {st.median(h2s):.3f} → {ratio:.3f} per step if h2 is step +2"
          f" (gridcalc default 1.25) · h2 line-height median {st.median(h2lh):.3f}")
    sizes = [r["size"] for r in refs]
    print(f"body size at 1440 px: median {st.median(sizes):.1f}px (range {min(sizes):.1f}–{max(sizes):.1f})")

    cal = dict(
        _fuente="calibrar.py sobre referencias medidas con medir_sitio.py; límites de la evidencia sin calibrar",
        fecha=datetime.date.today().isoformat(),
        referencias=[dict(url=r["url"], uso=r["uso"], grupo=r["grupo"], medido=r["medido"]) for r in refs],
        leading=dict(model=best, a=round(chosen["a"], 4), b=round(chosen["b"], 4), lam=round(chosen["lam"], 4),
                     loo_rmse={k: round(v, 4) for k, v in scores.items()}, n=len(fitset), floor=BOUNDS["lh_floor"]),
        uses=uses, longest=BOUNDS["longest"],
        margin_375={k: round(v, 2) for k, v in marg.items()},
        paragraph_gap_lines=round(gap, 3), heading_ratio=round(ratio, 4), h2_line_height=round(st.median(h2lh), 3),
        body_px_1440=st.median(sizes))
    if a.escribir:
        path = os.path.join(HERE, "calibracion.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(cal, fh, ensure_ascii=False, indent=1)
        print(f"\nwritten: {path}")


if __name__ == "__main__":
    main()
