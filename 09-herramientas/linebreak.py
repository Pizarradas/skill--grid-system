#!/usr/bin/env python3
"""linebreak — sets real text into a measure the way a browser does, and reports the lines it gets.

A measure of "66 characters" is a capacity: words do not split, so lines end short and vary. This module
breaks paragraphs with the browser's algorithm (CSS `text-wrap: wrap`: first fit, no hyphenation by default)
using the font's measured advances and kerning, and returns what readers actually get: characters per line,
fill, rag, short last lines, lines over 80 characters. `solve()` finds the width whose lines AVERAGE the target.

Break opportunities (a practical subset of Unicode UAX #14 for prose): after spaces, after hyphens and en/em
dashes inside words, before an em dash that follows a letter. Trailing spaces hang (they never count).
Widths: per-glyph advance + the kerning of the pair it starts (in Chrome the pair "letter + space" stays with
the letter); with `firefox=True`, pairs touching a space are not kerned when the font makes Firefox shape
word by word, and (given the size) each advance and each kerning value is rounded to Firefox's app unit,
1/60 px (measured: 99.7 % of lines identical to Firefox 157, see metricas-de-fuente.md §9). Stdlib only.
"""
import re
import statistics

import fontprofile

BREAK_AFTER = "-‐–—"   # hyphen-minus, hyphen, en dash, em dash


def paragraphs(text):
    out = []
    for p in re.split(r"\n+", text):
        p = re.sub(r"[ \t\r\f\v]+", " ", p).strip()
        if p:
            out.append(p)
    return out


def segments(p):
    """Split a paragraph into (text, is_space) pieces that are unbreakable inside."""
    out = []
    for tok in re.split(r"( )", p):
        if not tok:
            continue
        if tok == " ":
            out.append((" ", True))
            continue
        cur = ""
        for i, ch in enumerate(tok):
            if ch == "—" and cur and cur[-1].isalpha():   # break before an em dash after a letter
                out.append((cur, False)); cur = ""
            cur += ch
            nxt = tok[i + 1] if i + 1 < len(tok) else ""
            # UAX #14: a break after dashes (BA/B2) even at the start of a word; never after a word-initial
            # hyphen-minus (LB20.1), so "-5" or "-mente" stay whole
            if ch in BREAK_AFTER and nxt and nxt.isalpha() and (ch in "\u2013\u2014" or len(cur) > 1):
                out.append((cur, False)); cur = ""
        if cur:
            out.append((cur, False))
    return out


class Setter:
    """Prepared text for one font: glyph-adjusted widths per piece, so each layout is cheap."""

    def __init__(self, font, text, firefox=False, size=None):
        self.font, self.upm = font, font.upm
        if firefox and size:   # app units: 60 per CSS px
            q = lambda u: round(u / self.upm * size * 60) / 60 / size * self.upm
        else:
            q = lambda u: u
        font.set_script(fontprofile.text_script(text)[1])
        subs = font.substitutions()
        sp = font.gid(" ")
        word_mode = firefox and not font.shapes_across_spaces()
        self.paras = []
        self.missing = 0
        for p in paragraphs(text):
            gids = []
            for ch in p:
                g = font.gid(ch)
                if g is None:
                    self.missing += 1
                    g = font.gid("?") or 0
                gids.append(subs.get(g, g))
            adj = []
            for i, g in enumerate(gids):
                k = font.kern(g, gids[i + 1]) if i + 1 < len(gids) else 0
                if word_mode and (g == sp or (i + 1 < len(gids) and gids[i + 1] == sp)):
                    k = 0
                adj.append(q(font.advances[g]) + q(k))
            pieces, pos = [], 0
            for txt, is_space in segments(p):
                n = len(txt)
                pieces.append((txt, is_space, sum(adj[pos:pos + n])))
                pos += n
            self.paras.append(pieces)

    def set(self, width_em):
        """Lines for a measure of width_em: list of (text, width_em, is_last_of_paragraph)."""
        W = width_em * self.upm
        lines = []
        for pieces in self.paras:
            cur, cur_w, pend_txt, pend_w = "", 0.0, "", 0.0   # pend = spaces waiting for the next word
            for txt, is_space, w in pieces:
                if is_space:
                    if cur:
                        pend_txt += txt; pend_w += w
                    continue
                if cur and cur_w + pend_w + w > W:
                    lines.append((cur, cur_w / self.upm, False))
                    cur, cur_w = txt, w
                else:
                    cur, cur_w = cur + pend_txt + txt, cur_w + pend_w + w
                pend_txt, pend_w = "", 0.0
            if cur:
                lines.append((cur, cur_w / self.upm, True))
        return lines


def stats(lines, width_em, limit=80):
    """What a reader gets from these lines. Fill and rag ignore paragraph-final lines."""
    body = [l for l in lines if not l[2]] or lines
    chars = [len(t) for t, _, _ in body]
    fill = [w / width_em for _, w, _ in body]
    lasts = [l for l in lines if l[2]]
    runts = [l for l in lasts if " " not in l[0].strip()]
    q = statistics.quantiles(chars, n=20) if len(chars) >= 20 else [min(chars)] * 19
    return dict(lines=len(lines), chars_mean=statistics.mean(chars), chars_p5=q[0], chars_p50=statistics.median(chars),
                chars_p95=q[-1], chars_min=min(chars), chars_max=max(len(t) for t, _, _ in lines),
                over_limit=sum(1 for t, _, _ in lines if len(t) > limit),
                fill_mean=statistics.mean(fill), rag=statistics.pstdev(fill),
                short=sum(1 for f in fill if f < 0.85) / len(fill),
                saw=statistics.mean(abs(a - b) for a, b in zip(fill, fill[1:])) if len(fill) > 1 else 0.0,
                runts=len(runts) / max(1, len(lasts)), overflow=sum(1 for _, w, _ in lines if w > width_em + 1e-9))


def solve(setter, target_chars, lo=5.0, hi=80.0, tol=0.01):
    """Width (em) whose body lines AVERAGE target_chars characters (bisection; the mean grows with the width)."""
    for _ in range(40):
        mid = (lo + hi) / 2
        if stats(setter.set(mid), mid)["chars_mean"] < target_chars:
            lo = mid
        else:
            hi = mid
        if hi - lo < tol / 10:
            break
    return round(hi, 3)
