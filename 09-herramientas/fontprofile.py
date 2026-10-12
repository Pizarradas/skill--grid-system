#!/usr/bin/env python3
"""fontprofile — turns a font file into the calibration profile gridcalc uses.

Every value is in em (font units / unitsPerEm) unless the key says otherwise.
The profile records where each number comes from, so it can be audited:

  vertical   hhea / OS/2 typo / OS/2 win metrics, USE_TYPO_METRICS, and the line box
             each engine family builds from them (see fontmetrics doc, 08-composicion)
  glyphs     measured ink: x-height ('x'), cap height ('H'), overshoots ('o', 'O'),
             lowercase ascenders/descenders, accented capitals, digits
  leading    minimum line-height without ink collision between lines
  horizontal space, `ch` ("0"), dashes, digits, sidebearings, line-start/end white
  text       average advance per character of running text, per language, measured
             on a corpus WITH kerning (GPOS 'kern' / legacy 'kern'), cross-checked
             against a letter-frequency model
"""
import json
import os
import re
import unicodedata

import fontread

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.join(HERE, "corpus")
PROFILES = os.path.join(HERE, "perfiles")
LANGS = ("es", "en", "fr", "de", "it", "pt", "el", "ru")

# Unicode script (first word of the character name) -> OpenType script tags, kind.
#   alphabet: bicameral or simple scripts; advances + pair kerning give the browser's width
#   cjk:      ideographic/syllabic, near-fixed advances; Latin conventions (x-height, 45–75 chars) do not apply
#   complex:  needs full shaping (contextual forms, reordering, mark positioning): widths are approximate
SCRIPTS = {
    "LATIN": (("latn",), "alphabet"), "CYRILLIC": (("cyrl",), "alphabet"), "GREEK": (("grek",), "alphabet"),
    "ARMENIAN": (("armn",), "alphabet"), "GEORGIAN": (("geor",), "alphabet"),
    "CJK": (("hani",), "cjk"), "HIRAGANA": (("kana",), "cjk"), "KATAKANA": (("kana",), "cjk"),
    "HANGUL": (("hang",), "cjk"), "BOPOMOFO": (("bopo",), "cjk"),
    "ARABIC": (("arab",), "complex"), "HEBREW": (("hebr",), "alphabet"), "SYRIAC": (("syrc",), "complex"),
    "THAANA": (("thaa",), "complex"), "DEVANAGARI": (("dev2", "deva"), "complex"), "BENGALI": (("bng2", "beng"), "complex"),
    "GURMUKHI": (("gur2", "guru"), "complex"), "GUJARATI": (("gjr2", "gujr"), "complex"), "ORIYA": (("ory2", "orya"), "complex"),
    "TAMIL": (("tml2", "taml"), "complex"), "TELUGU": (("tel2", "telu"), "complex"), "KANNADA": (("knd2", "knda"), "complex"),
    "MALAYALAM": (("mlm2", "mlym"), "complex"), "SINHALA": (("sinh",), "complex"), "THAI": (("thai",), "complex"),
    "LAO": (("lao ",), "complex"), "KHMER": (("khmr",), "complex"), "MYANMAR": (("mym2", "mymr"), "complex"),
    "TIBETAN": (("tibt",), "complex"), "ETHIOPIC": (("ethi",), "alphabet"),
}
# Reference glyphs of the alphabets with an x-height. Several characters = median of their tops.
REFS = {
    "latn": dict(x="x", cap="H", o="o", O="O", asc="bdhkl", desc="gjpqy"),
    "cyrl": dict(x="х", cap="Н", o="о", O="О", asc="б", desc="ру"),
    "grek": dict(x="κντ", cap="Η", o="ο", O="Ο", asc="βδζθλξ", desc="γημρχψ"),
}


def char_script(ch):
    try:
        name = unicodedata.name(ch)
    except ValueError:
        return None
    for key in SCRIPTS:
        if name.startswith(key):
            return key
    return None


def text_script(text):
    """Dominant script of a text (by letters), its OpenType tags and kind."""
    counts = {}
    for ch in text:
        if ch.isalpha():
            s = char_script(ch)
            if s:
                counts[s] = counts.get(s, 0) + 1
    if not counts:
        return "LATIN", ("latn",), "alphabet"
    s = max(counts, key=counts.get)
    tags, kind = SCRIPTS[s]
    if kind != "complex" and any(unicodedata.combining(c) for c in unicodedata.normalize("NFC", text)):
        kind = "complex"   # combining marks left after NFC need mark positioning
    return s, tags, kind


def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def corpus_text(lang):
    with open(os.path.join(CORPUS, f"{lang}.txt"), encoding="utf-8") as fh:
        t = fh.read()
    if t.startswith("#"):
        t = t.split("\n", 1)[1]
    return t


def clean_text(t):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", t)).strip()


def frequencies():
    with open(os.path.join(CORPUS, "frecuencias.json"), encoding="utf-8") as fh:
        d = json.load(fh)
    d.pop("_fuente", None)
    return d


# ---------------------------------------------------------------- text width
def harfbuzz():
    """The HarfBuzz shaper (pip install uharfbuzz) if installed: exact widths for complex scripts."""
    try:
        import uharfbuzz
        return uharfbuzz
    except ImportError:
        return None


def shaped_width(font, text):
    """Width of the text shaped by HarfBuzz with its default features, in font units."""
    hb = harfbuzz()
    face = hb.Face(font.sfnt_bytes())
    hf = hb.Font(face)
    hf.scale = (face.upem * 64, face.upem * 64)
    if font.location:
        hf.set_variations(font.location)
    buf = hb.Buffer()
    buf.add_str(clean_text(text))
    buf.guess_segment_properties()
    hb.shape(hf, buf, {})
    return sum(p.x_advance for p in buf.glyph_positions) / 64


def text_width(font, text):
    """Measure running text as a browser lays it out (advances + pair kerning).

    Lines are joined by spaces; characters the font lacks are skipped and reported
    (a browser would draw them with a fallback font)."""
    text = clean_text(text)
    gids, missing = [], {}
    for ch in text:
        g = font.gid(ch)
        if g is None:
            missing[ch] = missing.get(ch, 0) + 1
        else:
            gids.append(g)
    subs = font.substitutions()
    gids = [subs.get(g, g) for g in gids]
    adv = sum(font.advances[g] for g in gids)
    pairs = [(a, b, font.kern(a, b)) for a, b in zip(gids, gids[1:])]
    kern = sum(k for _, _, k in pairs)
    sp = font.gid(" ")
    # Firefox shapes word by word (its word cache): pairs that touch a space are not kerned (measured)
    kern_words = sum(k for a, b, k in pairs if a != sp and b != sp)
    return dict(n=len(gids), adv=adv, kern=kern, kern_words=kern_words, missing=missing)


def structure(text):
    """Proportions of running text that a letter-frequency table does not give."""
    text = clean_text(text)
    n = len(text)
    letters = [c for c in text if c.isalpha()]
    punct = {}
    for c in text:
        if not c.isalnum() and c != " ":
            punct[c] = punct.get(c, 0) + 1
    return dict(space=text.count(" ") / n, caps=sum(c.isupper() for c in letters) / max(1, len(letters)),
                digits=sum(c.isdigit() for c in text) / n, punct={k: v / n for k, v in punct.items()})


def cw_frequency_model(font, freq, st):
    """Average advance per char = spaces + letters (lower/upper by the corpus caps
    ratio) + punctuation + digits. Letter mix from the frequency table."""
    upm = font.upm
    tot = sum(freq.values())

    def adv(ch):
        a = font.advance(ch)
        return a if a is not None else 0

    letters = 0.0
    for l, f in freq.items():
        up = l.upper()
        a_up = adv(up) if len(up) == 1 else adv(l)
        letters += (f / tot) * ((1 - st["caps"]) * adv(l) + st["caps"] * a_up)
    p_tot = sum(st["punct"].values())
    frac_letters = 1 - st["space"] - st["digits"] - p_tot
    digits = sum(adv(str(d)) for d in range(10)) / 10
    w = (st["space"] * adv(" ") + frac_letters * letters + sum(v * adv(k) for k, v in st["punct"].items())
         + st["digits"] * digits)
    return w / upm


# ---------------------------------------------------------------- profile
def _em(font, v):
    return None if v is None else round(v / font.upm, 4)


def _top(font, chars):
    best = None
    for c in sorted(chars):  # sorted: ties resolve the same way on every run
        b = font.char_bbox(c)
        if b and (best is None or b[3] > best[0]):
            best = (b[3], c)
    return best


def _bottom(font, chars):
    best = None
    for c in sorted(chars):  # sorted: ties resolve the same way on every run
        b = font.char_bbox(c)
        if b and (best is None or b[1] < best[0]):
            best = (b[1], c)
    return best


def line_metrics(font):
    """The line box each engine family builds. Engines on macOS/Linux read hhea
    (or OS/2 typo when USE_TYPO_METRICS is set); Windows (DirectWrite/GDI) reads
    usWin* unless USE_TYPO_METRICS is set. When the two disagree the same CSS
    line-height places the baseline at different heights per platform."""
    o, h = font.os2 or {}, font.hhea
    use_typo = bool(o.get("use_typo"))
    typo = (o.get("typo_asc"), -o.get("typo_desc", 0), o.get("typo_gap")) if o else None
    hhea = (h["asc"], -h["desc"], h["gap"])
    win = (o.get("win_asc"), o.get("win_desc"), max(0, hhea[0] + hhea[1] + hhea[2] - o.get("win_asc", 0) - o.get("win_desc", 0))) if o else None
    web = typo if (use_typo and typo) else hhea
    windows = typo if (use_typo and typo) else (win or hhea)
    return use_typo, hhea, typo, win, web, windows


def parse_axes(s):
    """'wght=700,opsz=24' -> {'wght': 700.0, 'opsz': 24.0}"""
    out = {}
    for part in (s or "").replace(" ", "").split(","):
        if part:
            k, _, v = part.partition("=")
            out[k] = float(v)
    return out


def build(path, langs=LANGS, sample=None, index=0, axes=None, instance=None):
    f = fontread.load(path, index, axes, instance)
    em = lambda v: _em(f, v)
    use_typo, hhea, typo, win, web, windows = line_metrics(f)
    o = f.os2 or {}
    bb = f.char_bbox

    def ymax(c):
        b = bb(c)
        return None if b is None else b[3]

    def ymin(c):
        b = bb(c)
        return None if b is None else b[1]

    def glyph_metrics(r):
        def top(chars):
            v = sorted(ymax(c) for c in chars if ymax(c) is not None)
            return v[len(v) // 2] if v else None
        xh, cap = top(r["x"]), top(r["cap"])
        asc = [ymax(c) for c in r["asc"] if ymax(c) is not None]
        desc = [ymin(c) for c in r["desc"] if ymin(c) is not None]
        return dict(
            x_height=em(xh), cap_height=em(cap),
            o_overshoot=em(ymax(r["o"]) - xh) if ymax(r["o"]) is not None and xh else None,
            o_undershoot=em(-ymin(r["o"])) if ymin(r["o"]) is not None else None,
            O_overshoot=em(ymax(r["O"]) - cap) if ymax(r["O"]) is not None and cap else None,
            ascender=em(max(asc)) if asc else None, descender=em(-min(desc)) if desc else None)

    by_script = {s: glyph_metrics(r) for s, r in REFS.items()
                 if any(f.gid(c) is not None for c in r["x"]) and f.gid(r["cap"]) is not None}
    primary = "latn" if "latn" in by_script else next(iter(by_script), None)
    prof = dict(
        name=f.name, family=f.names.get(16) or f.names.get(1), style=f.names.get(17) or f.names.get(2),
        full_name=f.names.get(4), postscript=f.names.get(6),
        file=os.path.basename(path), path=portable_path(path), sha1=f.sha1, container=f.container, outlines=f.outlines, upm=f.upm,
        glyph_count=f.num_glyphs, axes=f.axes,
        location={a["tag"]: f.location.get(a["tag"], a["default"]) for a in f.axes},
        instances=[i["name"] for i in f.instances],
        weight=o.get("weight"), width_class=o.get("width"), italic_angle=round(f.italic_angle, 2),
        fixed_pitch=f.fixed_pitch or (o.get("panose", [0] * 4)[3] == 9 if o else False),
        kerning=f.kern_source(),
    )
    lm = lambda t: None if t is None else dict(asc=em(t[0]), desc=em(t[1]), gap=em(t[2]), content=em(t[0] + t[1]),
                                               normal=em(t[0] + t[1] + t[2]))
    prof["vertical"] = dict(
        use_typo_metrics=use_typo, hhea=lm(hhea), typo=lm(typo), win=lm(win),
        web=lm(web), windows=lm(windows),
        web_source="typo" if (use_typo and typo) else "hhea",
        platform_divergence=None if windows == web else round((windows[0] - web[0]) / f.upm, 4),
    )
    # measured ink: the primary alphabet (Latin when present); every covered alphabet in glyphs_by_script
    g = dict(by_script.get(primary) or dict(x_height=None, cap_height=None, o_overshoot=None, o_undershoot=None,
                                            O_overshoot=None, ascender=None, descender=None))
    g.update(script=primary, x_height_os2=em(o.get("x_height")), cap_height_os2=em(o.get("cap_height")),
             digit_height=em(ymax("0")), d_height=em(ymax("d")))
    g["lining_digits"] = None if g["digit_height"] is None or not g["cap_height"] else abs(g["digit_height"] - g["cap_height"]) < 0.03
    g["xh_cap"] = round(g["x_height"] / g["cap_height"], 4) if g["x_height"] and g["cap_height"] else None
    prof["glyphs"] = g
    prof["glyphs_by_script"] = by_script

    # horizontal
    def sb(c):
        b, a = bb(c), f.advance(c)
        return None if b is None or a is None else [em(b[0]), em(a - b[2])]

    digits = [f.advance(str(d)) for d in range(10)]
    prof["horizontal"] = dict(
        space=em(f.advance(" ")), zero_ch=em(f.advance("0")), en_dash=em(f.advance("–")), em_dash=em(f.advance("—")),
        digit_avg=em(sum(d for d in digits if d) / max(1, sum(1 for d in digits if d))),
        tabular_digits=len({d for d in digits if d}) == 1,
        os2_avg_width=em(o.get("avg_width")),
        sidebearings={c: sb(c) for c in "HOnoa" if sb(c)},
    )

    # text, per language
    freq = frequencies()
    texts, uncovered = {}, {}
    sources = {l: corpus_text(l) for l in langs}
    if sample:
        with open(sample, encoding="utf-8") as fh:
            sources["sample"] = fh.read()
    for lang, raw in sources.items():
        sname, tags, kind = text_script(raw)
        f.set_script(tags)
        tw = text_width(f, raw)
        miss = sum(tw["missing"].values()) / max(1, tw["n"] + sum(tw["missing"].values()))
        if not tw["n"] or (miss > 0.02 and lang != "sample"):
            uncovered[lang] = round(100 * miss, 1)   # a fallback font would draw this text: no honest number
            continue
        st = structure(raw)
        cw, cw0 = (tw["adv"] + tw["kern"]) / tw["n"] / f.upm, tw["adv"] / tw["n"] / f.upm
        reliable = True
        if kind == "complex":
            if harfbuzz():
                cw = shaped_width(f, raw) / tw["n"] / f.upm   # contextual forms, ligatures, marks: shaped
            else:
                reliable = False                               # measured: +21–25 % on Arabic without shaping
        entry = dict(chars=tw["n"], cw=round(cw, 4), cw_no_kern=round(cw0, 4), reliable=reliable,
                     shaper="harfbuzz" if kind == "complex" and reliable else "fontread",
                     kern_pct=round(100 * tw["kern"] / tw["adv"], 3) if tw["adv"] else 0.0,
                     missing="".join(sorted(tw["missing"])), script=tags[-1] if tags[0].endswith("2") else tags[0],
                     shaping="simple" if kind == "alphabet" else kind)
        if kind != "complex" and abs(tw["kern"] - tw["kern_words"]) > 0.0005 * tw["adv"] and not f.shapes_across_spaces():
            entry["cw_firefox"] = round((tw["adv"] + tw["kern_words"]) / tw["n"] / f.upm, 4)
        if lang in freq:
            cwf = cw_frequency_model(f, freq[lang], st) + (tw["kern"] / tw["n"] / f.upm)
            entry["cw_freq_model"] = round(cwf, 4)
            entry["model_gap_pct"] = round(100 * (cwf - cw) / cw, 2)
        # line-start / line-end white: word-initial and word-final characters
        words = clean_text(raw).split(" ")
        firsts = [w[0] for w in words if w and f.gid(w[0]) is not None and bb(w[0])]
        lasts = [w[-1] for w in words if w and f.gid(w[-1]) is not None and bb(w[-1])]
        if firsts:
            entry["line_start_white"] = round(sum(bb(c)[0] for c in firsts) / len(firsts) / f.upm, 4)
        if lasts:
            entry["line_end_white"] = round(sum(f.advance(c) - bb(c)[2] for c in lasts) / len(lasts) / f.upm, 4)
        # ink extent of this language's text (letters both cases + punctuation in the corpus)
        chars = {c for c in clean_text(raw) if c != " " and f.gid(c) is not None}
        if lang in freq:
            chars |= {c for l in freq[lang] for c in (l, l.upper()) if len(c) == 1 and f.gid(c) is not None}
        lowers = {c for c in chars if c.islower()} or {c for c in chars if c.isalpha()}  # caseless scripts
        top_all, bot_all = _top(f, chars), _bottom(f, chars)
        top_low, bot_low = _top(f, lowers), _bottom(f, lowers)
        letters = {c for c in chars if c.isalpha()}
        bot_let = _bottom(f, letters)
        if top_all and bot_all and top_low and bot_low:
            entry["ink"] = dict(top=em(top_all[0]), top_char=top_all[1], bottom=em(-bot_all[0]), bottom_char=bot_all[1],
                                top_lower=em(top_low[0]), top_lower_char=top_low[1],
                                bottom_lower=em(-bot_low[0]), bottom_lower_char=bot_low[1])
            # minimum line-height (unitless) so that line n+1's ink never touches line n's
            entry["lh_no_collision_lower"] = em(top_low[0] - bot_low[0])
            entry["lh_no_collision_letters"] = em(_top(f, letters)[0] - bot_let[0]) if bot_let else None
            entry["lh_no_collision_all"] = em(top_all[0] - bot_all[0])
        texts[lang] = entry
    prof["text"] = texts
    notes = []
    if uncovered:
        notes.append("languages not covered by the font (characters missing): "
                     + ", ".join(f"{k} {v}%" for k, v in uncovered.items()))
    for lang, e in texts.items():
        if e["shaping"] == "complex" and not e["reliable"]:
            notes.append(f"{lang}: {e['script']} needs full shaping (contextual forms, ligatures, marks) and HarfBuzz is not"
                         f" installed: char_em is NOT reliable (+21–25 % measured on Arabic). pip install uharfbuzz")
        elif e["shaping"] == "complex":
            notes.append(f"{lang}: {e['script']} shaped with HarfBuzz (exact); kern_% and no_kern are pre-shaping values")
        elif e["shaping"] == "cjk":
            notes.append(f"{lang}: {e['script']} text — x-height and the 45–75 character measure are Latin conventions"
                         f" and do not apply; use char_em only as the advance per character")
    if not texts:
        notes.append("no corpus language is covered: measure your own text with --sample <file>")
    if f.outlines not in ("glyf", "CFF", "CFF2"):
        notes.append(f"outlines {f.outlines}: glyph ink not read; vertical values fall back to OS/2")
    if f.bbox_errors:
        names = "".join(sorted({chr(c) for c, g_ in f.cmap.items() if g_ in f.bbox_errors and c < 0x3000}))[:40]
        notes.append(f"{len(f.bbox_errors)} glyphs without measurable ink ({next(iter(f.bbox_errors.values()))}): {names}")
    if f.axes and not f.varied:
        notes.append("variable font measured at its default instance: use --axes or --instance for another point of the design space")
    prof["notes"] = notes
    return prof


# ---------------------------------------------------------------- where the font file is
def portable_path(path):
    """Relative to this folder when the font lives inside the system (fuentes/), so a profile works on any
    machine; otherwise the absolute path, written with forward slashes."""
    ab = os.path.abspath(path)
    try:
        rel = os.path.relpath(ab, HERE)
        if not rel.startswith(".."):
            return rel.replace(os.sep, "/")
    except ValueError:      # another drive on Windows
        pass
    return ab.replace(os.sep, "/")


def _font_dirs():
    home = os.path.expanduser("~")
    dirs = [os.path.join(HERE, "fuentes"), os.environ.get("WINDIR", "C:/Windows") + "/Fonts",
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Windows", "Fonts"),
            "/mnt/c/Windows/Fonts", "/usr/share/fonts", "/usr/local/share/fonts", os.path.join(home, ".fonts"),
            os.path.join(home, ".local", "share", "fonts"), "/Library/Fonts", "/System/Library/Fonts",
            os.path.join(home, "Library", "Fonts")]
    return [d for d in dirs if d and os.path.isdir(d)]


def _sha1(path):
    import hashlib
    with open(path, "rb") as fh:
        return hashlib.sha1(fh.read()).hexdigest()


def locate(prof):
    """The font file a stored profile was measured from, on this machine, or None. Tries the stored path
    (relative to this folder, or absolute), its Windows <-> WSL spelling, then the file name in the usual font
    folders; a candidate only counts if its SHA-1 matches the profile."""
    p, sha = prof.get("path"), prof.get("sha1")
    if not p:
        return None
    cands = [os.path.join(HERE, p), p]
    m = re.match(r"^([A-Za-z]):[/\\](.*)$", p)
    if m:                                            # C:/… -> /mnt/c/…
        cands.append(f"/mnt/{m.group(1).lower()}/{m.group(2)}")
    m = re.match(r"^/mnt/([a-z])/(.*)$", p)
    if m:                                            # /mnt/c/… -> C:/…
        cands.append(f"{m.group(1).upper()}:/{m.group(2)}")
    name = prof.get("file") or os.path.basename(p)
    for d in _font_dirs():
        for root, _, files in os.walk(d):
            if name in files:
                cands.append(os.path.join(root, name))
    seen = set()
    for c in cands:
        c = os.path.normpath(c)
        if c in seen or not os.path.isfile(c):
            continue
        seen.add(c)
        if not sha or _sha1(c) == sha:
            return c
    return None


# ---------------------------------------------------------------- storage
def save(prof, directory=PROFILES):
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, slug(prof["name"]) + ".json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(prof, fh, ensure_ascii=False, indent=1)
    return path


def available(directory=PROFILES):
    """{key: path} with the profile slug and, for Regular styles, the family slug as alias."""
    out = {}
    if not os.path.isdir(directory):
        return out
    for fn in sorted(os.listdir(directory)):
        if fn.endswith(".json"):
            p = os.path.join(directory, fn)
            key = fn[:-5]
            out[key] = p
            with open(p, encoding="utf-8") as fh:
                d = json.load(fh)
            if (d.get("style") or "").lower() in ("regular", "book", "roman", "normal"):
                out.setdefault(slug(d.get("family") or key), p)
    return out


def resolve(name_or_path, langs=LANGS, sample=None, axes=None, instance=None):
    """A profile from a font file path, a profile JSON path, or a profile name/alias."""
    if os.path.isfile(name_or_path):
        if name_or_path.endswith(".json"):
            with open(name_or_path, encoding="utf-8") as fh:
                return json.load(fh)
        return build(name_or_path, langs, sample, axes=axes, instance=instance)
    av = available()
    key = slug(name_or_path)
    if key in av:
        with open(av[key], encoding="utf-8") as fh:
            prof = json.load(fh)
        if sample:
            raise SystemExit("--sample needs the font file, not a stored profile (the text is measured against the glyphs)")
        return prof
    return None
