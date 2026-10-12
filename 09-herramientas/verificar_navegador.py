#!/usr/bin/env python3
"""verificar_navegador — compares the system's predictions with what real browsers lay out.

  python3 verificar_navegador.py Fuente.woff2 [más fuentes] [--fallback arial] [--langs es,en,el,ru]
                                 [--browsers chrome,edge,firefox,chromium] [--chromium RUTA] [--keep]

For each font it serves a test page on 127.0.0.1, opens it in each browser HEADLESS with a throwaway
profile (it never touches your open browser or your data), and measures:

  1. line box   ascent/descent the engine really uses (font-size 1000px, line-height normal)
                -> which prediction it matches: web (hhea/typo) or Windows (usWin*)
  2. width      running text of each language at 16px and 100px, kerning and optical size as the
                browser applies them by default -> error of char_em against the prediction
  3. text-box   trim-both cap alphabetic: height of a trimmed line vs the measured cap height
  4. fallback   (with --fallback) the local font with the computed size-adjust/overrides vs the web font
  5. lines      the corpus set at 16px in the measure whose lines average 66 characters (linebreak.solve):
                every line the browser makes vs the simulated one (normal and geometricPrecision rendering)

Stdlib only. Browsers: Chrome/Edge/Firefox on Windows (also from WSL), Chrome/Chromium on Linux and
macOS when installed (--chromium for a Chrome for Testing build). Results: table + JSON next to the script.
"""
import argparse
import http.server
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import fontprofile  # noqa: E402
import fontread  # noqa: E402
import linebreak  # noqa: E402

LINE_SIZE, LINE_TARGET = 16, 66

IS_WSL = "microsoft" in platform.release().lower()
IS_WIN = os.name == "nt"
SIZES = (16, 100)

WIN_BROWSERS = {
    "chrome": [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
               r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"],
    "edge": [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
             r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"],
    "firefox": [r"C:\Program Files\Mozilla Firefox\firefox.exe"],
}


def win_to_wsl(p):
    return "/mnt/" + p[0].lower() + p[2:].replace("\\", "/")


def find_browsers(wanted, chromium=None):
    out = {}
    if IS_WIN or IS_WSL:
        for name, paths in WIN_BROWSERS.items():
            for p in paths:
                local = p if IS_WIN else win_to_wsl(p)
                if os.path.isfile(local):
                    out[name] = dict(exe=local, kind="firefox" if name == "firefox" else "chromium", windows=True)
                    break
    if not IS_WIN:
        for exe in ([chromium] if chromium else []) + ["google-chrome", "chromium", "chromium-browser",
                                                       "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]:
            path = exe if os.path.isfile(exe or "") else shutil.which(exe or "")
            if path:
                out["chromium"] = dict(exe=path, kind="chromium", windows=False)
                break
    return {k: v for k, v in out.items() if not wanted or k in wanted}


# ---------------------------------------------------------------- predictions
def predict(path, langs, sizes):
    """What the system says the browser will lay out."""
    base = fontprofile.build(path, langs=langs)
    opsz = next((a for a in base["axes"] if a["tag"] == "opsz"), None)
    pred = dict(name=base["name"], file=os.path.basename(path), line_web=base["vertical"]["web"],
                line_windows=base["vertical"]["windows"], cap=base["glyphs"]["cap_height"],
                opsz=bool(opsz), widths={}, widths_firefox={}, default_widths={})
    for s in sizes:
        prof = base if not opsz else fontprofile.build(
            path, langs=langs, axes={"opsz": round(min(max(s, opsz["min"]), opsz["max"]), 2)})
        for lang, t in prof["text"].items():
            if t.get("reliable", True):
                pred["widths"][f"{lang}@{s}"] = t["cw"]
                pred["widths_firefox"][f"{lang}@{s}"] = t.get("cw_firefox", t["cw"])  # word-by-word kerning
                pred["default_widths"][f"{lang}@{s}"] = base["text"][lang]["cw"]
    # 5. line breaks at LINE_SIZE (opsz follows the size), for the first covered language
    if langs:
        at = {"opsz": min(max(LINE_SIZE, opsz["min"]), opsz["max"])} if opsz else None
        text = fontprofile.corpus_text(langs[0])
        chrome = linebreak.Setter(fontread.load(path, axes=at), text)
        firefox = linebreak.Setter(fontread.load(path, axes=at), text, firefox=True, size=LINE_SIZE)
        width = linebreak.solve(chrome, LINE_TARGET)
        pred["lines"] = dict(lang=langs[0], width=width, paras=linebreak.paragraphs(text),
                             chrome=by_paragraph(chrome.set(width)), firefox=by_paragraph(firefox.set(width)))
    return pred


def by_paragraph(lines):
    out, cur = [], []
    for text, _, last in lines:
        cur.append(text)
        if last:
            out.append(cur)
            cur = []
    return out


FALLBACK_SIZE = 16  # the fallback is computed and tested at body size (opsz follows it)


def fallback_css(family, path, fb_name, langs):
    """@font-face of the fallback, computed for langs[0] at FALLBACK_SIZE, and the predicted residual per language."""
    import gridcalc
    lang = langs[0]
    ax = next((x for x in fontread.load(path).axes if x["tag"] == "opsz"), None)
    axes = {"opsz": min(max(FALLBACK_SIZE, ax["min"]), ax["max"])} if ax else None
    prof = fontprofile.build(path, langs=langs, axes=axes)
    fb = gridcalc.load_profile(fb_name)
    m, f = gridcalc.profile_metrics(prof, lang), gridcalc.profile_metrics(fb, lang)
    k = m["cw"] / f["cw"]
    v = prof["vertical"]["web"]
    resid = {l: 100 * (k * fb["text"][l]["cw"] / prof["text"][l]["cw"] - 1) for l in langs if l in fb["text"] and l in prof["text"]}
    names = [x for x in (fb.get("full_name"), fb.get("postscript")) if x] + gridcalc.METRIC_CLONES.get(fb.get("family"), [])
    locs = ", ".join(f'local("{n}")' for n in dict.fromkeys(names))
    return (f'@font-face{{font-family:"{family} FB";src:{locs};size-adjust:{100 * k:.4f}%;'
            f'ascent-override:{100 * v["asc"] / k:.4f}%;descent-override:{100 * v["desc"] / k:.4f}%;'
            f'line-gap-override:{100 * v["gap"] / k:.4f}%}}'), resid


# ---------------------------------------------------------------- page
PAGE = """<!doctype html><meta charset="utf-8"><title>gridcalc</title>
<style>%(css)s body{margin:0} .m{position:absolute;left:0;top:0;white-space:pre}</style>
<script src="data.js"></script>
<script>
async function run(){
  const out={ua:navigator.userAgent, textBox:CSS.supports('text-box','trim-both cap alphabetic'), fonts:[]};
  for(const f of DATA.fonts){
    const r={file:f.file};
    try{
      await document.fonts.load('100px "'+f.family+'"');
      // 1. line box at 1000px: an inline span's box is the content area; a 0-size inline-block marks the baseline
      const d=document.createElement('div'); d.className='m';
      d.style.font='1000px/normal "'+f.family+'"';
      d.innerHTML='<span>Hxgp<i style="display:inline-block;width:0;height:0;vertical-align:baseline"></i></span>';
      document.body.appendChild(d);
      const sp=d.firstChild.getBoundingClientRect(), mk=d.querySelector('i').getBoundingClientRect();
      r.asc=(mk.top-sp.top)/1000; r.desc=(sp.bottom-mk.top)/1000; r.normal=d.getBoundingClientRect().height/1000;
      d.remove();
      // 2. widths of running text
      r.widths={};
      for(const [lang,text] of Object.entries(DATA.texts)){
        for(const s of DATA.sizes){
          const e=document.createElement('span'); e.className='m';
          e.style.font=s+'px "'+f.family+'"'; e.textContent=text; document.body.appendChild(e);
          r.widths[lang+'@'+s]=e.getBoundingClientRect().width/s/text.length; e.remove();
          if(lang===DATA.langs0){            // diagnostics: does the engine kern? does it round/hint?
            for(const [tag,style] of [['nokern','font-kerning:none'],['geo','text-rendering:geometricPrecision']]){
              const v=document.createElement('span'); v.className='m';
              v.style.cssText+='font:'+s+'px "'+f.family+'";'+style; v.textContent=text; document.body.appendChild(v);
              r.widths[lang+'@'+s+'@'+tag]=v.getBoundingClientRect().width/s/text.length; v.remove();
            }
          }
          if(f.fallback && s===16){
            const g=document.createElement('span'); g.className='m';
            g.style.font=s+'px "'+f.family+' FB"'; g.textContent=text; document.body.appendChild(g);
            r.widths[lang+'@fallback']=g.getBoundingClientRect().width/s/text.length; g.remove();
          }
        }
      }
      // 3. text-box-trim: a one-line box trimmed to cap height and baseline
      if(out.textBox){
        const t=document.createElement('div'); t.className='m';
        t.style.cssText+='font:100px/3 "'+f.family+'";text-box:trim-both cap alphabetic';
        t.textContent='H'; document.body.appendChild(t);
        r.trimmed=t.getBoundingClientRect().height/100; t.remove();
      }
      // 5. line breaks: group characters by the line box they fall in
      if(f.lines){
        r.lines={};
        for(const [tag,style] of [['normal',''],['geo','text-rendering:geometricPrecision']]){
          const box=document.createElement('div'); box.className='m';
          box.style.cssText+='white-space:normal;font:'+DATA.lineSize+'px "'+f.family+'";width:'+f.lines.width+'em;'+style;
          for(const para of f.lines.paras){ const p=document.createElement('p'); p.style.margin='0'; p.textContent=para; box.appendChild(p); }
          document.body.appendChild(box);
          const out=[]; const rg=document.createRange();
          for(const p of box.children){
            const tn=p.firstChild, ls=[]; let cur='', top=null;
            for(let i=0;i<tn.length;i++){
              const ch=tn.data[i];
              rg.setStart(tn,i); rg.setEnd(tn,i+1); const rs=rg.getClientRects();
              if(ch!==' ' && rs.length){
                const tp=Math.round(rs[0].top);
                if(top!==null && tp>top+2){ ls.push(cur.trim()); cur=''; }
                top=tp;
              }
              cur+=ch;
            }
            ls.push(cur.trim()); out.push(ls);
          }
          r.lines[tag]=out; box.remove();
        }
      }
    }catch(e){ r.error=String(e); }
    out.fonts.push(r);
  }
  await fetch('/result?b='+encodeURIComponent(DATA.browser),{method:'POST',body:JSON.stringify(out)});
  document.title='done';
}
run();
</script>"""


class Server(http.server.ThreadingHTTPServer):
    def __init__(self, root):
        self.root, self.results, self.event = root, {}, threading.Event()
        super().__init__(("127.0.0.1", 0), Handler)


class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def translate_path(self, path):
        path = path.split("?", 1)[0].lstrip("/")
        b = path.split("/", 1)[-1] if "/" in path else path
        return os.path.join(self.server.root, b)

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        browser = self.path.split("b=", 1)[-1]
        self.server.results[browser] = json.loads(self.rfile.read(n))
        self.send_response(204)
        self.end_headers()
        self.server.event.set()


def winpath(p):
    if IS_WSL:
        return subprocess.run(["wslpath", "-w", p], capture_output=True, text=True).stdout.strip()
    return p


def launch(name, b, url, marker, tmpbase):
    prof = os.path.join(tmpbase, f"{marker}-{name}")
    os.makedirs(prof, exist_ok=True)
    pp = winpath(prof) if b["windows"] else prof
    if b["kind"] == "firefox":
        with open(os.path.join(prof, "user.js"), "w") as fh:
            fh.write('user_pref("browser.shell.checkDefaultBrowser", false);\n'
                     'user_pref("datareporting.policy.dataSubmissionEnabled", false);\n')
        args = [b["exe"], "--headless", "-no-remote", "-profile", pp, url]
    else:
        args = [b["exe"], "--headless=new", f"--user-data-dir={pp}", "--no-first-run",
                "--no-default-browser-check", "--disable-extensions", "--disable-gpu", url]
    env = dict(os.environ)
    if b.get("libs"):
        env["LD_LIBRARY_PATH"] = b["libs"]
    return subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env), prof


def stop(proc, marker, windows):
    proc.kill()
    if windows:  # Windows browsers outlive the WSL/launcher process: stop them by their profile marker
        ps = ("powershell.exe" if IS_WSL else "powershell")
        subprocess.run([ps, "-NoProfile", "-Command",
                        f"Get-CimInstance Win32_Process | Where-Object {{ $_.CommandLine -like '*{marker}*' }} | "
                        f"ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }}"],
                       capture_output=True)


# ---------------------------------------------------------------- run
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("fonts", nargs="+")
    ap.add_argument("--langs", default="es,en,el,ru")
    ap.add_argument("--browsers", default="", help="chrome,edge,firefox,chromium (default: all found)")
    ap.add_argument("--chromium", help="path to a Chrome/Chromium executable (Linux/macOS)")
    ap.add_argument("--chromium-libs", help="LD_LIBRARY_PATH for that executable")
    ap.add_argument("--fallback", help="profile of a local fallback font to test size-adjust (e.g. arial)")
    ap.add_argument("--timeout", type=float, default=90)
    ap.add_argument("--keep", action="store_true", help="keep the temporary page and profiles")
    a = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    langs = tuple(x for x in a.langs.split(",") if x)
    browsers = find_browsers(set(filter(None, a.browsers.split(","))), a.chromium)
    if a.chromium_libs and "chromium" in browsers:
        browsers["chromium"]["libs"] = a.chromium_libs
    if not browsers:
        sys.exit("no browser found")
    tmpdir = None
    if IS_WSL and any(b["windows"] for b in browsers.values()):  # Windows browsers need their profiles on Windows
        wtemp = subprocess.run(["cmd.exe", "/c", "echo %TEMP%"], capture_output=True, text=True,
                               cwd="/mnt/c").stdout.strip()
        tmpdir = subprocess.run(["wslpath", "-u", wtemp], capture_output=True, text=True).stdout.strip() or None
    tmpbase = tempfile.mkdtemp(prefix="gridtest-", dir=tmpdir)
    root = os.path.join(tmpbase, "page")
    os.makedirs(root)
    texts = {l: fontprofile.clean_text(fontprofile.corpus_text(l)) for l in langs}
    fonts, css, preds = [], [], []
    print("predicting…", flush=True)
    for i, p in enumerate(a.fonts):
        f = fontread.load(p)
        if f.container == "ttc":
            print(f"  skip {p}: browsers do not load font collections (.ttc) with @font-face")
            continue
        ext = os.path.splitext(p)[1].lower()
        shutil.copy(p, os.path.join(root, f"f{i}{ext}"))
        fmt_ = {".woff2": "woff2", ".woff": "woff", ".otf": "opentype"}.get(ext, "truetype")
        fam = f"T{i}"
        css.append(f'@font-face{{font-family:"{fam}";src:url("f{i}{ext}") format("{fmt_}")}}')
        covered = [l for l in langs if not any(f.gid(c) is None for c in texts[l])]
        resid = {}
        if a.fallback and covered:
            rule, resid = fallback_css(fam, p, a.fallback, covered)
            css.append(rule)
        preds.append(dict(predict(p, tuple(covered), SIZES), family=fam, langs=covered, fallback_resid=resid))
        pl = preds[-1].get("lines")
        fonts.append(dict(family=fam, file=os.path.basename(p), fallback=bool(a.fallback),
                          lines=dict(width=pl["width"], paras=pl["paras"]) if pl else None))
    srv = Server(root)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    marker = "gridtest-" + uuid.uuid4().hex[:8]
    results = {}
    for name, b in browsers.items():
        with open(os.path.join(root, "data.js"), "w", encoding="utf-8") as fh:
            fh.write("const DATA=" + json.dumps(dict(fonts=fonts, texts=texts, sizes=SIZES, browser=name, langs0=langs[0],
                                                     lineSize=LINE_SIZE),
                                                ensure_ascii=False))
        with open(os.path.join(root, "index.html"), "w", encoding="utf-8") as fh:
            fh.write(PAGE % dict(css="".join(css)))
        srv.event.clear()
        url = f"http://127.0.0.1:{srv.server_address[1]}/index.html?{name}"
        print(f"{name}: running…", flush=True)
        proc, _ = launch(name, b, url, marker, tmpbase)
        ok = srv.event.wait(a.timeout)
        stop(proc, marker, b["windows"])
        if ok:
            results[name] = srv.results[name]
        else:
            print(f"  {name}: no result in {a.timeout:g}s")
    srv.shutdown()
    time.sleep(1)
    if not a.keep:
        shutil.rmtree(tmpbase, ignore_errors=True)
    report(preds, results)
    out = os.path.join(HERE, "pruebas", "navegador-resultados.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(dict(predictions=preds, results=results), fh, ensure_ascii=False, indent=1)
    print(f"\nresults: {out}")


def report(preds, results):
    for name, res in results.items():
        ua = res.get("ua", "")
        print(f"\n== {name} · {ua[ua.find('(') + 1:ua.find(')')] if '(' in ua else ua}"
              f" · text-box-trim {'yes' if res.get('textBox') else 'no'}")
        for pr, r in zip(preds, res["fonts"]):
            if "error" in r:
                print(f"  {pr['file']}: {r['error']}")
                continue
            web, win = pr["line_web"], pr["line_windows"]
            dw = abs(r["asc"] - web["asc"]) + abs(r["desc"] - web["desc"])
            dn = abs(r["asc"] - win["asc"]) + abs(r["desc"] - win["desc"])
            match = ("web=Windows" if web == win else "web (hhea/typo)" if dw < dn else "Windows (usWin)") \
                if min(dw, dn) < 0.003 else "neither"
            line = (f"  {pr['name'][:30]:30} line box asc {r['asc']:.4f} desc {r['desc']:.4f} → {match}")
            errs = []
            for key, cw in (pr["widths_firefox"] if name == "firefox" else pr["widths"]).items():
                if key in r["widths"]:
                    e = 100 * (r["widths"][key] - cw) / cw
                    errs.append(f"{key} {e:+.3f}%")
                    if pr["opsz"]:
                        d = pr["default_widths"][key]
                        errs[-1] += f" (vs default opsz {100 * (r['widths'][key] - d) / d:+.2f}%)"
            if r.get("trimmed") and pr["cap"]:
                errs.append(f"text-box {r['trimmed']:.4f} vs cap {pr['cap']:.4f}")
            for key in [k for k in r["widths"] if k.endswith("@fallback")]:
                lang = key.split("@")[0]
                ref = r["widths"].get(f"{lang}@16")
                if ref and lang in pr["fallback_resid"]:
                    errs.append(f"fallback {lang} {100 * (r['widths'][key] - ref) / ref:+.2f}%"
                                f" (predicted {pr['fallback_resid'][lang]:+.2f}%)")
            print(line + "\n      width: " + " · ".join(errs))
            pl = pr.get("lines")
            if pl and r.get("lines"):
                sim = pl["firefox" if name == "firefox" else "chrome"]
                tot = sum(len(x) for x in sim)
                parts = []
                for tag, got in r["lines"].items():
                    same_l = sum(1 for a_, b_ in zip(sim, got) for x, y in zip(a_, b_) if x == y)
                    same_p = sum(1 for a_, b_ in zip(sim, got) if a_ == b_)
                    parts.append(f"{tag}: {100 * same_l / tot:.1f}% of lines identical, {same_p}/{len(sim)} paragraphs,"
                                 f" {sum(len(p_) for p_ in got)} lines vs {tot} simulated")
                print(f"      lines ({pl['lang']}, {LINE_SIZE}px, {pl['width']}em): " + " · ".join(parts))


if __name__ == "__main__":
    main()
