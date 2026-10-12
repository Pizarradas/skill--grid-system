#!/usr/bin/env python3
"""verificar — checks that the typographic calibration is exact.

  python3 verificar.py                     internal checks (stdlib only)
  python3 verificar.py Fuente.woff2 ...    plus checks against those font files

Internal (always):
  1. brotlidec.py against fixed vectors made with the reference brotli (length + SHA-1)
  2. every stored profile is coherent (x-height < cap, ch ≥ char, model gap small, …)
With font files:
  3. regression: if a stored profile has the same SHA-1, a fresh measurement must match it
  4. fontTools installed: head/hhea/OS/2 fields, every advance, the whole cmap, every glyph bbox
  5. uharfbuzz installed: kerned width of the corpus vs HarfBuzz (the shaper of Chrome and Firefox)
  6. variable fonts (fontTools + uharfbuzz): at three named instances, every glyph bbox and advance vs
     fontTools and the kerned corpus width vs HarfBuzz (axes, avar, gvar/CFF2, HVAR, MVAR, GDEF deltas)
Exit code 1 if anything fails.
"""
import base64
import hashlib
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import brotlidec  # noqa: E402
import fontprofile  # noqa: E402
import fontread  # noqa: E402

results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(f"  {'ok ' if ok else 'FAIL'}  {name}{('  · ' + detail) if detail else ''}")


def brotli_vectors():
    print("1 · Brotli (WOFF2) against reference vectors")
    with open(os.path.join(HERE, "pruebas", "brotli-vectores.json"), encoding="utf-8") as fh:
        vecs = json.load(fh)["vectores"]
    for v in vecs:
        try:
            out = brotlidec.decompress(base64.b64decode(v["brotli_b64"]))
            ok = len(out) == v["longitud"] and hashlib.sha1(out).hexdigest() == v["sha1"]
            check(v["nombre"], ok, f"{len(out)} bytes")
        except ValueError as e:
            check(v["nombre"], False, str(e))


def profiles():
    print("2 · stored profiles are coherent")
    seen = set()
    for key, path in fontprofile.available().items():
        if path in seen:
            continue
        seen.add(path)
        with open(path, encoding="utf-8") as fh:
            p = json.load(fh)
        g, h, v = p["glyphs"], p["horizontal"], p["vertical"]
        errs = []
        if g["x_height"] and g["cap_height"] and g["x_height"] > g["cap_height"] + 1e-9:
            errs.append("x-height > cap height")
        if v["web"]["asc"] <= 0 or v["web"]["desc"] < 0:
            errs.append("line box with non-positive ascent")
        for lang, t in p["text"].items():
            if not 0.2 < t["cw"] < 1.0:
                errs.append(f"{lang}: char_em {t['cw']} out of range")
            if t.get("reliable") is False:
                continue
            if abs(t.get("model_gap_pct", 0)) > 2.5:
                errs.append(f"{lang}: corpus vs frequency model {t['model_gap_pct']}%")
            if t["cw"] > t["cw_no_kern"] + 1e-9 and t["kern_pct"] < 0:
                errs.append(f"{lang}: kerning sign")
        check(key, not errs, "; ".join(errs))


def font_files(paths):
    stored = {}
    for path in set(fontprofile.available().values()):
        with open(path, encoding="utf-8") as fh:
            p = json.load(fh)
        stored[p["sha1"]] = p
    try:
        from fontTools.ttLib import TTFont
        from fontTools.pens.boundsPen import BoundsPen
    except ImportError:
        TTFont = None
    try:
        import uharfbuzz as hb
    except ImportError:
        hb = None
    for fp in paths:
        print(f"· {os.path.basename(fp)}")
        f = fontread.load(fp)
        print("3 · regression against the stored profile")
        if f.sha1 in stored:
            fresh = fontprofile.build(fp)
            old = stored[f.sha1]
            same = all(json.dumps(fresh[k], sort_keys=True) == json.dumps(old[k], sort_keys=True)
                       for k in ("vertical", "glyphs", "horizontal", "text"))
            check("fresh measurement == stored profile", same)
        else:
            print("  --   no stored profile with this SHA-1 (gridcalc.py font <file> --save to create one)")
        print("4 · structure against fontTools")
        if TTFont is None:
            print("  --   fontTools not installed: skipped (pip install fonttools brotli)")
        else:
            o = TTFont(fp)
            gs = o.getGlyphOrder()
            os2, hh = o["OS/2"], o["hhea"]
            check("unitsPerEm, hhea, OS/2", f.upm == o["head"].unitsPerEm
                  and (f.hhea["asc"], f.hhea["desc"], f.hhea["gap"]) == (hh.ascent, hh.descent, hh.lineGap)
                  and (f.os2["typo_asc"], f.os2["typo_desc"], f.os2["win_asc"], f.os2["win_desc"])
                  == (os2.sTypoAscender, os2.sTypoDescender, os2.usWinAscent, os2.usWinDescent))
            check("advances", [o["hmtx"][g][0] for g in gs] == f.advances, f"{len(gs)} glyphs")
            gi = {n: i for i, n in enumerate(gs)}
            check("cmap", {c: gi[n] for c, n in o.getBestCmap().items()} == f.cmap, f"{len(f.cmap)} characters")
            worst, bad = 0.0, 0
            gset = o.getGlyphSet()
            for i, g in enumerate(gs):
                mine = f.bbox(i)
                if "glyf" in o:
                    gl = o["glyf"][g]
                    ref = None if gl.numberOfContours == 0 else (gl.xMin, gl.yMin, gl.xMax, gl.yMax)
                else:
                    bp = BoundsPen(gset)
                    gset[g].draw(bp)
                    ref = bp.bounds
                if (mine is None) != (ref is None):
                    bad += 1
                elif mine is not None:
                    d = max(abs(a - b) for a, b in zip(mine, ref))
                    worst = max(worst, d)
                    bad += d > 0.01
            check("bbox of every glyph", bad == 0, f"max difference {worst:.4f} units")
        print("5 · kerned text width against HarfBuzz")
        if hb is None or TTFont is None:
            print("  --   uharfbuzz/fontTools not installed: skipped (pip install uharfbuzz fonttools brotli)")
        else:
            o = TTFont(fp)
            o.flavor = None
            buf = io.BytesIO()
            o.save(buf)
            font = hb.Font(hb.Face(buf.getvalue()))
            for lang in fontprofile.LANGS:
                text = fontprofile.clean_text(fontprofile.corpus_text(lang))
                if any(f.gid(c) is None for c in text):
                    continue
                f.set_script(fontprofile.text_script(text)[1])
                mine = fontprofile.text_width(f, text)
                b = hb.Buffer()
                b.add_str(text)
                b.guess_segment_properties()
                hb.shape(font, b, {"liga": False, "clig": False, "calt": False})
                ref = sum(p.x_advance for p in b.glyph_positions)
                err = 100 * (mine["adv"] + mine["kern"] - ref) / ref
                # 0.01 %: contextual GSUB substitutions (not applied) moved Roboto Flex Greek by 0.006 %
                check(f"{lang}: {mine['n']} chars", abs(err) < 0.01, f"difference {err:+.4f}%")
        if f.axes and hb is not None and TTFont is not None:
            print("6 · variable font at named instances")
            insts = f.instances
            for inst in [insts[0], insts[len(insts) // 2], insts[-1]] if insts else []:
                fv = fontread.load(fp, instance=inst["name"])
                o = TTFont(fp)
                gs = o.getGlyphSet(location=inst["coords"], normalized=False)
                order = o.getGlyphOrder()
                worst = bad = 0.0
                for i, g in enumerate(order):
                    mine = fv.bbox(i)
                    if "glyf" in o:
                        from fontTools.pens.boundsPen import ControlBoundsPen as Pen
                    else:
                        Pen = BoundsPen
                    pen = Pen(gs)
                    gs[g].draw(pen)
                    if (mine is None) != (pen.bounds is None):
                        bad += 1
                    elif mine is not None:
                        d = max(abs(a - b) for a, b in zip(mine, pen.bounds))
                        worst = max(worst, d)
                        bad += d > 0.05  # fontTools does not round coordinates to F2Dot14; engines do
                    bad += abs(fv.advances[i] - round(gs[g].width)) > 1
                check(f"{inst['name']}: bbox + advance of {len(order)} glyphs", bad == 0, f"max bbox difference {worst:.3f}")
                text = fontprofile.clean_text(fontprofile.corpus_text("es"))
                if any(fv.gid(c) is None for c in text):
                    continue
                fv.set_script(("latn",))
                mine = fontprofile.text_width(fv, text)
                hf = hb.Font(hb.Face(fv.sfnt_bytes()))
                hf.scale = (fv.upm * 64, fv.upm * 64)
                hf.set_variations(fv.location)
                b = hb.Buffer()
                b.add_str(text)
                b.guess_segment_properties()
                hb.shape(hf, b, {"liga": False, "clig": False, "calt": False})
                ref = sum(p.x_advance for p in b.glyph_positions) / 64
                err = 100 * (mine["adv"] + mine["kern"] - ref) / ref
                check(f"{inst['name']}: kerned width es", abs(err) < 0.001, f"difference {err:+.4f}%")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    brotli_vectors()
    profiles()
    if len(sys.argv) > 1:
        font_files(sys.argv[1:])
    print(f"\n{sum(results)}/{len(results)} checks passed")
    sys.exit(0 if all(results) else 1)
