#!/usr/bin/env python3
"""medir_sitio — measures the typography a live web page really applies, in a real browser.

  python3 medir_sitio.py URL [URL…] [--uso reading|scanning|operating] [--viewports 375,1440]
                         [--chrome RUTA] [--chrome-libs RUTA] [--out referencias/]

For the page's running text (the paragraphs that hold most of its prose) it records, at each viewport:
body size, line-height, weight, font, x-height and cap height of the font in use (canvas metrics),
average advance per character, characters per line of the lines actually set (every line, by Range),
measure in px/em, paragraph spacing, page margins, and size / line-height / space above of h1–h3.

It drives a headless Chrome/Chromium through the DevTools protocol (a minimal WebSocket client in the
standard library) with a throwaway profile, so the page is measured as it renders, web fonts included.
Each result is saved as JSON in referencias/ for calibrar.py. Stdlib only.
"""
import argparse
import base64
import datetime
import json
import os
import random
import re
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------- minimal WebSocket (RFC 6455) client
class WebSocket:
    def __init__(self, url, timeout=60):
        u = urllib.parse.urlparse(url)
        self.sock = socket.create_connection((u.hostname, u.port or 80), timeout=timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        req = (f"GET {u.path}{'?' + u.query if u.query else ''} HTTP/1.1\r\nHost: {u.hostname}:{u.port}\r\n"
               f"Upgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n")
        self.sock.sendall(req.encode())
        head = b""
        while b"\r\n\r\n" not in head:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("WebSocket handshake failed")
            head += chunk
        if b" 101 " not in head.split(b"\r\n", 1)[0]:
            raise ConnectionError(head.split(b"\r\n", 1)[0].decode(errors="replace"))
        self.buf = head.split(b"\r\n\r\n", 1)[1]

    def send(self, text):
        data = text.encode()
        mask = os.urandom(4)
        n = len(data)
        hdr = bytes([0x81]) + (bytes([0x80 | n]) if n < 126 else
                               bytes([0x80 | 126]) + struct.pack(">H", n) if n < 65536 else
                               bytes([0x80 | 127]) + struct.pack(">Q", n))
        self.sock.sendall(hdr + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

    def _read(self, n):
        while len(self.buf) < n:
            chunk = self.sock.recv(1 << 16)
            if not chunk:
                raise ConnectionError("WebSocket closed")
            self.buf += chunk
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def recv(self):
        msg = b""
        while True:
            b0, b1 = self._read(2)
            n = b1 & 0x7F
            if n == 126:
                n = struct.unpack(">H", self._read(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", self._read(8))[0]
            if b1 & 0x80:
                mask = self._read(4)
                data = bytes(b ^ mask[i % 4] for i, b in enumerate(self._read(n)))
            else:
                data = self._read(n)
            op = b0 & 0x0F
            if op == 9:          # ping -> pong
                continue
            if op == 8:
                raise ConnectionError("WebSocket closed by the browser")
            msg += data
            if b0 & 0x80:
                return msg.decode(errors="replace")


class CDP:
    def __init__(self, ws_url):
        self.ws, self.n = WebSocket(ws_url), 0

    def call(self, method, timeout=90, **params):
        self.n += 1
        self.ws.send(json.dumps({"id": self.n, "method": method, "params": params}))
        end = time.time() + timeout
        while time.time() < end:
            m = json.loads(self.ws.recv())
            if m.get("id") == self.n:
                if "error" in m:
                    raise RuntimeError(f"{method}: {m['error'].get('message')}")
                return m.get("result", {})
        raise TimeoutError(method)


# ---------------------------------------------------------------- what is measured in the page
MEASURE_JS = r"""
(async () => {
  await document.fonts.ready;
  await new Promise(r => setTimeout(r, 1500));
  const vis = e => { const r = e.getBoundingClientRect(); const s = getComputedStyle(e);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const ps = [...document.querySelectorAll('p, li')].filter(p => vis(p) && p.innerText.trim().length >= 140
               && !p.closest('nav, header, footer, aside, [role=navigation], [role=banner], [role=contentinfo]'));
  if (!ps.length) return {error: 'no running text found'};
  // the body style = the (font, size, line-height, width) group holding most characters
  const groups = {};
  for (const p of ps) { const s = getComputedStyle(p);
    const k = [s.fontFamily, s.fontSize, s.lineHeight, s.fontWeight, Math.round(p.getBoundingClientRect().width)].join('|');
    (groups[k] = groups[k] || []).push(p); }
  const best = Object.values(groups).sort((a, b) => b.reduce((n, p) => n + p.innerText.length, 0) - a.reduce((n, p) => n + p.innerText.length, 0))[0];
  const p0 = best[0], s0 = getComputedStyle(p0), size = parseFloat(s0.fontSize);
  // used face: the first family in the stack that the document can render
  const fams = s0.fontFamily.split(',').map(f => f.trim().replace(/^["']|["']$/g, ''));
  const used = fams.find(f => { try { return document.fonts.check(`${s0.fontWeight} ${size}px "${f}"`); } catch (e) { return false; } }) || fams[0];
  const ctx = document.createElement('canvas').getContext('2d');
  // canvas ink boxes are rounded to whole pixels: measure them at 1000px (approximate; the font FILE is better)
  ctx.font = `${s0.fontStyle} ${s0.fontWeight} 1000px ${s0.fontFamily}`;
  const mx = ctx.measureText('x'), mH = ctx.measureText('H');
  ctx.font = `${s0.fontStyle} ${s0.fontWeight} ${size}px ${s0.fontFamily}`;
  // lines actually set, per paragraph (characters grouped by line box)
  const rg = document.createRange(), lines = [], last = [];
  let chars = 0, width = 0;
  for (const p of best.slice(0, 40)) {
    const walker = document.createTreeWalker(p, NodeFilter.SHOW_TEXT); const ls = []; let cur = '', top = null, n;
    while ((n = walker.nextNode())) {
      for (let i = 0; i < n.length; i++) { const ch = n.data[i];
        if (!/\s/.test(ch)) { rg.setStart(n, i); rg.setEnd(n, i + 1); const r = rg.getClientRects()[0];
          if (r) { const t = Math.round(r.top); if (top !== null && t > top + 2) { ls.push(cur.trim()); cur = ''; } top = t; } }
        cur += /\s/.test(ch) ? ' ' : ch; } }
    ls.push(cur.trim());
    const clean = ls.map(l => l.replace(/\s+/g, ' ')).filter(l => l.length);
    lines.push(...clean.slice(0, -1).map(l => l.length)); if (clean.length) last.push(clean[clean.length - 1].length);
    const txt = p.innerText.replace(/\s+/g, ' ').trim(); chars += txt.length; width += ctx.measureText(txt).width;
  }
  const lh = s0.lineHeight === 'normal' ? null : parseFloat(s0.lineHeight);
  const r0 = p0.getBoundingClientRect();
  // paragraph spacing: gaps between consecutive paragraphs of the body group
  const gaps = [];
  for (let i = 0; i + 1 < best.length; i++) { const a = best[i].getBoundingClientRect(), b = best[i + 1].getBoundingClientRect();
    const g = b.top - a.bottom; if (g >= 0 && g < 4 * size && best[i].parentElement === best[i + 1].parentElement) gaps.push(g); }
  gaps.sort((a, b) => a - b);
  const heads = {};
  for (const tag of ['h1', 'h2', 'h3']) {
    const h = [...document.querySelectorAll(tag)].find(e => vis(e) && e.innerText.trim().length > 3 && !e.closest('nav, header, footer, aside'));
    if (h) { const s = getComputedStyle(h); const prev = h.previousElementSibling;
      heads[tag] = {size: parseFloat(s.fontSize), lh: s.lineHeight === 'normal' ? null : parseFloat(s.lineHeight),
                    weight: s.fontWeight, family: s.fontFamily.split(',')[0].replace(/["']/g, ''),
                    space_above: prev ? h.getBoundingClientRect().top - prev.getBoundingClientRect().bottom : null}; }
  }
  return {url: location.href, title: document.title, viewport: innerWidth, font_stack: s0.fontFamily, font_used: used,
          weight: s0.fontWeight, size, line_height: lh, lh_ratio: lh ? lh / size : null,
          letter_spacing: s0.letterSpacing, word_spacing: s0.wordSpacing,
          x_height_canvas: mx.actualBoundingBoxAscent / 1000, cap_height_canvas: mH.actualBoundingBoxAscent / 1000,
          font_urls: performance.getEntriesByType('resource').map(e => e.name).filter(u => /\.(woff2?|ttf|otf)(\?|#|$)/i.test(u)),
          char_em: chars ? width / chars / size : null, paragraphs: best.length,
          measure_px: r0.width, measure_em: r0.width / size, margin_left: r0.left, margin_right: innerWidth - r0.right,
          lines: lines.length, chars_per_line: lines, last_lines: last,
          para_gap_px: gaps.length ? gaps[gaps.length >> 1] : null, headings: heads,
          layout_width: document.documentElement.clientWidth};
})()
"""


# ---------------------------------------------------------------- browser
def find_chrome(path):
    for c in ([path] if path else []) + ["google-chrome", "chromium", "chromium-browser", "chrome",
                                         r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                                         "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]:
        if c and (os.path.isfile(c) or shutil.which(c)):
            return c if os.path.isfile(c) else shutil.which(c)
    sys.exit("no Chrome/Chromium found: pass --chrome (e.g. a Chrome for Testing build)")


def start_chrome(exe, libs=None):
    port = random.randint(20000, 40000)
    prof = tempfile.mkdtemp(prefix="medir-sitio-")
    env = dict(os.environ)
    if libs:
        env["LD_LIBRARY_PATH"] = libs
    proc = subprocess.Popen([exe, "--headless=new", f"--remote-debugging-port={port}", f"--user-data-dir={prof}",
                             "--no-first-run", "--no-default-browser-check", "--disable-gpu", "--hide-scrollbars",
                             "--lang=es-ES", "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
    for _ in range(100):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=1):
                return proc, port, prof
        except OSError:
            time.sleep(0.1)
    proc.kill()
    sys.exit("Chrome did not open its DevTools port")


def stop_chrome(proc, port, prof):
    """Close Chrome through DevTools (Browser.close), then make sure the whole process tree is gone:
    on Windows, killing only the parent leaves children alive and the profile folder locked."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=3) as r:
            CDP(json.load(r)["webSocketDebuggerUrl"]).call("Browser.close", timeout=5)
    except Exception:
        pass
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
        else:
            proc.kill()
    for _ in range(10):
        shutil.rmtree(prof, ignore_errors=True)
        if not os.path.exists(prof):
            break
        time.sleep(0.5)


def measure(port, url, viewports, timeout=60):
    req = urllib.request.Request(f"http://127.0.0.1:{port}/json/new?about:blank", method="PUT")
    with urllib.request.urlopen(req, timeout=10) as r:
        target = json.load(r)
    cdp = CDP(target["webSocketDebuggerUrl"])
    out = {}
    try:
        for vw in viewports:
            cdp.call("Emulation.setDeviceMetricsOverride", width=vw, height=900, deviceScaleFactor=1, mobile=vw < 600)
            cdp.call("Page.navigate", url=url)
            end = time.time() + timeout
            while time.time() < end:
                st = cdp.call("Runtime.evaluate", expression="document.readyState", returnByValue=True)
                if st.get("result", {}).get("value") == "complete":
                    break
                time.sleep(0.5)
            res = cdp.call("Runtime.evaluate", expression=MEASURE_JS, awaitPromise=True, returnByValue=True, timeout=timeout)
            out[str(vw)] = res.get("result", {}).get("value") or {"error": str(res.get("exceptionDetails", "no value"))[:300]}
    finally:
        try:
            urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{port}/json/close/{target['id']}", method="PUT"), timeout=5)
        except OSError:
            pass
    return out


GENERIC = {"serif", "sans-serif", "monospace", "system-ui", "ui-sans-serif", "ui-serif", "-apple-system",
           "blinkmacsystemfont", "cursive", "fantasy"}


def font_from_file(d, cache):
    """Download the page's web fonts, pick the one drawing the body text (family + weight), and measure it with
    fontprofile at the body size's optical size: exact x-height, cap height and char_em of what readers see."""
    sys.path.insert(0, HERE)
    import fontprofile
    import fontread
    if d.get("font_used", "").lower() in GENERIC:
        return None
    want, weight = d["font_used"].lower().replace(" ", ""), float(d.get("weight") or 400)
    best = None
    for url in dict.fromkeys(d.get("font_urls", [])):
        path = os.path.join(cache, re.sub(r"[^A-Za-z0-9.]+", "_", url)[-120:])
        if not os.path.isfile(path):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Referer": d["url"]})
                with urllib.request.urlopen(req, timeout=30) as r, open(path, "wb") as fh:
                    fh.write(r.read())
            except OSError:
                continue
        try:
            f = fontread.load(path)
        except Exception:
            continue
        names = {(f.names.get(i) or "").lower().replace(" ", "") for i in (1, 4, 6, 16)}
        if not any(want == n or want in n for n in names if n):
            continue
        ax = {a["tag"]: a for a in f.axes}
        w = weight if "wght" in ax else (f.os2 or {}).get("weight", 400)
        score = abs(w - weight) + (0 if "wght" in ax else 1) * 0 + (100 if f.italic_angle else 0)
        if best is None or score < best[0]:
            best = (score, path, url, ax)
    if not best:
        return None
    _, path, url, ax = best
    axes = {}
    if "wght" in ax:
        axes["wght"] = min(max(weight, ax["wght"]["min"]), ax["wght"]["max"])
    if "opsz" in ax:
        axes["opsz"] = min(max(d["size"], ax["opsz"]["min"]), ax["opsz"]["max"])
    lang = "es" if any(k in d["url"] for k in ("eldiario.es", "es.wikipedia", "elpais")) else "en"
    prof = fontprofile.build(path, langs=(lang,), axes=axes or None)
    t = prof["text"].get(lang, {})
    return dict(file_url=url, name=prof["name"], x_height=prof["glyphs"]["x_height"], cap_height=prof["glyphs"]["cap_height"],
                char_em=t.get("cw"), lh_min_letters=t.get("lh_no_collision_letters"), lang=lang, axes=axes)


def slug(url):
    u = urllib.parse.urlparse(url)
    return re.sub(r"[^a-z0-9]+", "-", (u.netloc + u.path).lower()).strip("-")[:80]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("urls", nargs="+")
    ap.add_argument("--uso", choices=["reading", "scanning", "operating"], help="the use profile this reference stands for")
    ap.add_argument("--grupo", default="", help="free label (editorial, docs, design-system…)")
    ap.add_argument("--viewports", default="375,1440")
    ap.add_argument("--chrome")
    ap.add_argument("--chrome-libs")
    ap.add_argument("--out", default=os.path.join(HERE, "referencias"))
    a = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    os.makedirs(a.out, exist_ok=True)
    cache = os.path.join(tempfile.gettempdir(), "medir-sitio-fuentes")
    os.makedirs(cache, exist_ok=True)
    proc, port, prof = start_chrome(find_chrome(a.chrome), a.chrome_libs)
    try:
        for url in a.urls:
            try:
                r = measure(port, url, [int(v) for v in a.viewports.split(",")])
            except Exception as e:  # one bad page must not stop the batch
                print(f"  {url}: {e}")
                continue
            for vw, d in r.items():
                if "error" not in d:
                    d["responsive"] = abs(d.get("layout_width", int(vw)) - int(vw)) <= 20
                    d["font_file"] = font_from_file(d, cache)
            rec = dict(url=url, uso=a.uso, grupo=a.grupo, medido=datetime.date.today().isoformat(), viewports=r)
            path = os.path.join(a.out, slug(url) + ".json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(rec, fh, ensure_ascii=False, indent=1)
            d = r.get(a.viewports.split(",")[-1], {})
            if "error" in d:
                print(f"  {url}: {d['error']}")
            else:
                cpl = d["chars_per_line"]
                ff = d.get("font_file") or {}
                xh = f"xh {ff['x_height']:.3f} (file)" if ff.get("x_height") else f"xh ~{d['x_height_canvas']:.3f} (canvas)"
                print(f"  {d['title'][:40]:40} {d['font_used'][:18]:18} {d['size']:.0f}px/{(d['lh_ratio'] or 0):.2f}"
                      f" {xh} · {sum(cpl) / max(1, len(cpl)):.1f} chars/line ({len(cpl)} lines)"
                      f" · {d['measure_em']:.1f}em → {os.path.basename(path)}")
    finally:
        stop_chrome(proc, port, prof)


if __name__ == "__main__":
    main()
