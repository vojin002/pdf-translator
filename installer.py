import os, sys, re, json, time, threading, subprocess, urllib.request
from pathlib import Path
from http.server import BaseHTTPRequestHandler
from socketserver import ThreadingMixIn, TCPServer

class _ThreadingHTTPServer(ThreadingMixIn, TCPServer):
    daemon_threads = True
    allow_reuse_address = True
    def server_bind(self):
        import socket
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        TCPServer.server_bind(self)

_dir = Path(__file__).parent
_PORT = 15173
_events: list = []
_events_cond = threading.Condition()
_started = False
_server = None
_window = None


def _add_event(evt: dict):
    with _events_cond:
        _events.append(evt)
        _events_cond.notify_all()

_PACKAGES = [
    ("pymupdf",        "📄", "PyMuPDF",        "Obrada i editovanje PDF dokumenata"),
    ("deep-translator","🌐", "deep-translator", "Google Translate API"),
    ("flask",          "⚗", "Flask",           "Lokalni web server"),
    ("pywebview",      "🪟", "pywebview",       "Desktop prozor aplikacije"),
]

_ANSI = re.compile(r"\x1b\[[0-9;]*[mGKH]")


def _webview_ok() -> bool:
    try:
        import importlib
        importlib.import_module("webview")
        return True
    except ImportError:
        return False


def _bootstrap() -> bool:
    if _webview_ok():
        return True
    try:
        import tkinter as tk
        root = tk.Tk()
        root.overrideredirect(True)
        root.configure(bg="#07070e")
        root.attributes("-topmost", True)
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        w, h = 340, 150
        root.geometry(f"{w}x{h}+{(sw - w)//2}+{(sh - h)//2}")
        tk.Label(root, text="⚙", fg="#818cf8", bg="#07070e",
                 font=("Segoe UI", 32)).pack(pady=(16, 6))
        msg = tk.StringVar(value="Priprema instalater...")
        tk.Label(root, textvariable=msg, fg="#8892aa", bg="#07070e",
                 font=("Segoe UI", 11)).pack()
        root.update()
        ok = [False]
        def _do():
            root.after(0, msg.set, "Instaliram pywebview...")
            r = subprocess.run(
                [sys.executable, "-m", "pip", "install", "pywebview", "-q"],
                capture_output=True,
            )
            ok[0] = r.returncode == 0
            root.after(400, root.destroy)
        threading.Thread(target=_do, daemon=True).start()
        root.mainloop()
    except Exception:
        r = subprocess.run(
            [sys.executable, "-m", "pip", "install", "pywebview", "-q"],
            capture_output=True,
        )
        ok = [r.returncode == 0]
    return ok[0] and _webview_ok()


def _show_error(msg: str):
    try:
        import tkinter as tk
        from tkinter import messagebox
        r = tk.Tk()
        r.withdraw()
        messagebox.showerror("PDF Prevodilac — Instalacija", msg)
        r.destroy()
    except Exception:
        print(f"[ERROR] {msg}")
        input("Press Enter to exit...")


_HTML = """\
<!DOCTYPE html><html lang="sr"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Instalacija — PDF Prevodilac</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root{--bg:#07070e;--card:rgba(12,12,28,.75);--panel:rgba(255,255,255,.04);
  --border:rgba(255,255,255,.07);--border2:rgba(255,255,255,.13);
  --a1:#818cf8;--a2:#c084fc;--a3:#f472b6;
  --ok:#34d399;--err:#fb7185;--warn:#fbbf24;
  --fg:#eeeeff;--sub:#8892aa;--dim:#4a5068;--log:#04040b;--r:16px}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{min-height:100vh;background:var(--bg);font-family:'Inter',system-ui,sans-serif;
  color:var(--fg);display:flex;align-items:center;justify-content:center;
  padding:24px 16px 32px;overflow-x:hidden}
.orb{position:fixed;border-radius:50%;filter:blur(100px);pointer-events:none;z-index:0;
  animation:drift 22s ease-in-out infinite}
.orb1{width:520px;height:520px;top:-160px;left:-140px;
  background:radial-gradient(circle,rgba(129,140,248,.2) 0%,transparent 70%)}
.orb2{width:440px;height:440px;bottom:-100px;right:-100px;
  background:radial-gradient(circle,rgba(244,114,182,.14) 0%,transparent 70%);animation-delay:-9s}
.orb3{width:300px;height:300px;top:45%;left:55%;
  background:radial-gradient(circle,rgba(192,132,252,.1) 0%,transparent 70%);
  animation-delay:-17s;animation-duration:18s}
@keyframes drift{0%,100%{transform:translate(0,0) scale(1)}
  33%{transform:translate(40px,-30px) scale(1.06)}66%{transform:translate(-30px,40px) scale(.94)}}
.card{position:relative;z-index:1;width:100%;max-width:500px;
  background:var(--card);backdrop-filter:blur(36px) saturate(1.4);
  -webkit-backdrop-filter:blur(36px) saturate(1.4);
  border:1px solid var(--border);border-radius:24px;padding:30px 28px 26px;
  box-shadow:0 0 0 1px rgba(129,140,248,.08),0 1px 0 rgba(255,255,255,.06) inset,
    0 40px 100px rgba(0,0,0,.7)}
.hd{margin-bottom:20px}
.logo{display:flex;align-items:center;gap:13px;margin-bottom:10px}
.logo-badge{width:44px;height:44px;border-radius:13px;flex-shrink:0;
  background:linear-gradient(135deg,var(--a1) 0%,var(--a3) 100%);
  display:flex;align-items:center;justify-content:center;font-size:20px;
  box-shadow:0 6px 18px rgba(129,140,248,.32),0 0 0 1px rgba(255,255,255,.1) inset}
h1{font-size:1.4rem;font-weight:700;letter-spacing:-.02em;line-height:1;
  background:linear-gradient(100deg,var(--fg) 40%,var(--a2));
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}
.logo-sub{font-size:.76rem;color:var(--sub);margin-top:3px}
.py-badge{display:inline-flex;align-items:center;gap:5px;
  background:rgba(52,211,153,.07);border:1px solid rgba(52,211,153,.2);
  border-radius:20px;padding:3px 10px;font-size:.73rem}
.py-badge b{color:var(--ok)}
.steps{display:flex;align-items:center;margin-bottom:18px}
.step{display:flex;flex-direction:column;align-items:center;gap:4px;flex-shrink:0}
.sn{width:28px;height:28px;border-radius:50%;border:1.5px solid var(--dim);
  display:flex;align-items:center;justify-content:center;
  font-size:.75rem;font-weight:700;color:var(--dim);transition:all .35s}
.sl{font-size:.65rem;font-weight:500;color:var(--dim);white-space:nowrap;transition:color .35s}
.step.active .sn{border-color:var(--a1);color:var(--a1);background:rgba(129,140,248,.12);
  box-shadow:0 0 0 4px rgba(129,140,248,.1)}
.step.active .sl{color:var(--a1)}
.step.done .sn{border-color:var(--ok);background:rgba(52,211,153,.12);color:var(--ok)}
.step.done .sl{color:var(--ok)}
.step-line{flex:1;height:1.5px;background:var(--dim);margin:0 5px;margin-bottom:12px;transition:background .35s}
.step-line.done{background:var(--ok)}
.pkg-list{display:flex;flex-direction:column;gap:6px;margin-bottom:16px}
.pkg-row{display:flex;align-items:center;gap:11px;
  background:var(--panel);border:1px solid var(--border);
  border-radius:11px;padding:11px 13px;transition:all .3s}
.pkg-row.installing{border-color:rgba(129,140,248,.3);background:rgba(129,140,248,.05)}
.pkg-row.done{border-color:rgba(52,211,153,.25);background:rgba(52,211,153,.04)}
.pkg-row.error{border-color:rgba(251,113,133,.3);background:rgba(251,113,133,.05)}
.pkg-ic{width:34px;height:34px;border-radius:9px;flex-shrink:0;
  background:rgba(255,255,255,.04);border:1px solid var(--border);
  display:flex;align-items:center;justify-content:center;font-size:.9rem;transition:all .3s}
.pkg-row.installing .pkg-ic{background:rgba(129,140,248,.1);border-color:rgba(129,140,248,.2)}
.pkg-row.done       .pkg-ic{background:rgba(52,211,153,.1);border-color:rgba(52,211,153,.2)}
.pkg-info{flex:1;min-width:0}
.pkg-name{font-size:.85rem;font-weight:600}
.pkg-desc{font-size:.7rem;color:var(--sub);margin-top:1px}
.pkg-st{font-size:.69rem;font-weight:600;padding:2px 9px;border-radius:20px;white-space:nowrap;
  transition:all .25s;background:rgba(255,255,255,.05);color:var(--dim);border:1px solid var(--border)}
.pkg-row.installing .pkg-st{background:rgba(129,140,248,.12);color:var(--a1);border-color:rgba(129,140,248,.25)}
.pkg-row.done       .pkg-st{background:rgba(52,211,153,.12);color:var(--ok);border-color:rgba(52,211,153,.25)}
.pkg-row.error      .pkg-st{background:rgba(251,113,133,.12);color:var(--err);border-color:rgba(251,113,133,.25)}
.btn{display:flex;align-items:center;justify-content:center;gap:9px;
  width:100%;padding:13px 20px;border:none;border-radius:var(--r);
  font-family:inherit;font-size:.94rem;font-weight:700;cursor:pointer;
  letter-spacing:-.01em;transition:all .2s}
.btn-install{background:linear-gradient(135deg,var(--a1) 0%,#6366f1 50%,var(--a2) 100%);
  background-size:200% 100%;color:#fff;box-shadow:0 4px 24px rgba(99,102,241,.32)}
.btn-install:hover:not(:disabled){background-position:100% 0;transform:translateY(-2px);
  box-shadow:0 8px 32px rgba(99,102,241,.42)}
.btn-install:disabled{opacity:.38;cursor:not-allowed;box-shadow:none}
.btn-launch{display:none;background:rgba(52,211,153,.08);
  border:1px solid rgba(52,211,153,.25);color:var(--ok);margin-top:8px}
.btn-launch.show{display:flex;animation:popIn .4s cubic-bezier(.34,1.56,.64,1)}
.btn-launch:hover{background:rgba(52,211,153,.13);transform:translateY(-2px);
  box-shadow:0 6px 22px rgba(52,211,153,.18)}
@keyframes popIn{from{opacity:0;transform:scale(.9) translateY(8px)}
  to{opacity:1;transform:scale(1) translateY(0)}}
#pw{display:none;margin-top:13px}
#pw.show{display:block;animation:fadeIn .3s ease}
@keyframes fadeIn{from{opacity:0}to{opacity:1}}
.prog-track{height:6px;background:rgba(255,255,255,.06);border-radius:3px;overflow:hidden}
#pf{height:100%;width:0%;
  background:linear-gradient(90deg,var(--a1) 0%,var(--a2) 50%,var(--a3) 100%);
  background-size:200% 100%;border-radius:3px;
  transition:width .5s cubic-bezier(.4,0,.2,1);
  box-shadow:0 0 8px rgba(129,140,248,.35);position:relative}
#pf::after{content:'';position:absolute;inset:0;
  background:linear-gradient(90deg,transparent,rgba(255,255,255,.28) 50%,transparent);
  animation:shim 1.6s infinite}
@keyframes shim{0%{transform:translateX(-150%)}100%{transform:translateX(250%)}}
#pf.done{box-shadow:0 0 8px rgba(52,211,153,.35)}
#pf.done::after{display:none}
#pt{font-size:.79rem;color:var(--sub);margin-top:6px;text-align:center}
#lw{margin-top:11px}
.lhdr{display:flex;align-items:center;gap:7px;cursor:pointer;padding:7px 0 5px;user-select:none}
.lhdr:hover .ltit{color:var(--sub)}
.ltit{font-size:.66rem;font-weight:700;color:var(--dim);
  text-transform:uppercase;letter-spacing:.09em;transition:color .15s;flex:1}
.lcnt{font-size:.63rem;font-weight:600;background:rgba(255,255,255,.05);
  border:1px solid var(--border);color:var(--dim);padding:1px 7px;border-radius:20px;transition:all .2s}
.lcnt.has{background:rgba(129,140,248,.1);border-color:rgba(129,140,248,.2);color:var(--a1)}
.lchev{font-size:.63rem;color:var(--dim);transition:transform .25s}
.lchev.open{transform:rotate(180deg)}
#lb{overflow:hidden;max-height:0;transition:max-height .35s cubic-bezier(.4,0,.2,1)}
#lb.open{max-height:170px}
#log{background:var(--log);border:1px solid rgba(255,255,255,.05);border-radius:12px;
  height:144px;overflow-y:auto;margin-top:5px;
  font-family:'Cascadia Code','Consolas','Courier New',monospace}
#log::-webkit-scrollbar{width:4px}
#log::-webkit-scrollbar-track{background:transparent}
#log::-webkit-scrollbar-thumb{background:rgba(255,255,255,.07);border-radius:2px}
.le{display:flex;align-items:center;gap:7px;padding:3px 12px;
  border-bottom:1px solid rgba(255,255,255,.02);animation:li .15s ease}
.le:last-child{border-bottom:none}
@keyframes li{from{opacity:0;transform:translateX(-5px)}to{opacity:1;transform:translateX(0)}}
.lic{width:14px;height:14px;border-radius:50%;flex-shrink:0;
  display:flex;align-items:center;justify-content:center;font-size:.55rem;font-weight:800}
.ok{background:rgba(52,211,153,.15);color:#34d399}
.er{background:rgba(251,113,133,.15);color:#fb7185}
.di{background:rgba(255,255,255,.04);color:#3a3f58}
.lm{flex:1;font-size:.7rem;line-height:1.5;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.mok{color:rgba(52,211,153,.8)}.mer{color:rgba(251,113,133,.9)}.mdi{color:#4a5570}
.card-ft{display:flex;align-items:center;justify-content:center;
  flex-wrap:wrap;gap:5px;margin-top:16px;font-size:.67rem;color:var(--dim)}
.ft-dot{width:2px;height:2px;border-radius:50%;background:var(--dim)}
.spin{display:inline-block;animation:rot .7s linear infinite}
@keyframes rot{to{transform:rotate(360deg)}}
</style></head><body>
<div class="orb orb1"></div><div class="orb orb2"></div><div class="orb orb3"></div>
<main class="card">
  <div class="hd">
    <div class="logo">
      <div class="logo-badge">⚙</div>
      <div><h1>Instalacija</h1><div class="logo-sub">PDF Prevodilac — podešavanje</div></div>
    </div>
    <div class="py-badge">🐍 Python <b>__VER__</b></div>
  </div>
  <div class="steps">
    <div class="step done" id="s1"><div class="sn">✓</div><div class="sl">Python</div></div>
    <div class="step-line done"></div>
    <div class="step active" id="s2"><div class="sn">2</div><div class="sl">Paketi</div></div>
    <div class="step-line" id="l2"></div>
    <div class="step" id="s3"><div class="sn">3</div><div class="sl">Gotovo</div></div>
  </div>
  <div class="pkg-list">__ROWS__</div>
  <button class="btn btn-install" id="btn" onclick="go()">
    <span id="bi">⬇</span><span id="bl">Instaliraj pakete</span>
  </button>
  <button class="btn btn-launch" id="btnL" onclick="launch()">
    <span>✦</span><span>Pokreni PDF Prevodilac</span>
  </button>
  <div id="pw">
    <div class="prog-track"><div id="pf"></div></div>
    <div id="pt">Priprema...</div>
  </div>
  <div id="lw">
    <div class="lhdr" onclick="tgl()">
      <span class="ltit">Detalji instalacije</span>
      <span class="lcnt" id="lc">0</span>
      <span class="lchev" id="lv">▾</span>
    </div>
    <div id="lb"><div id="log"></div></div>
  </div>
  <div class="card-ft">
    <span>Lokalna instalacija</span><div class="ft-dot"></div>
    <span>Besplatno</span><div class="ft-dot"></div>
    <span>Bez internet zavisnosti</span>
  </div>
</main>
<script>
const pf=e('pf'),pt=e('pt'),btn=e('btn'),bi=e('bi'),bl=e('bl'),
      btnL=e('btnL'),logEl=e('log'),lb=e('lb'),lc=e('lc'),lv=e('lv');
let n=0,_evtDone=false;
function e(id){return document.getElementById(id)}
function setStep(s){
  [1,2,3].forEach(i=>{
    const el=e('s'+i); el.classList.remove('active','done');
    if(i<s){el.classList.add('done');el.querySelector('.sn').textContent='✓';}
    else if(i===s) el.classList.add('active');
  });
  const l2=e('l2'); if(l2) l2.classList.toggle('done',s>2);
}
function tgl(){lb.classList.toggle('open');lv.classList.toggle('open');}
function addLog(msg,cls){
  const ic={ok:'✓',er:'✕',di:'·'}[cls]||'·';
  const row=document.createElement('div'); row.className='le';
  const i=document.createElement('span'); i.className='lic '+cls; i.textContent=ic;
  const m=document.createElement('span'); m.className='lm m'+cls; m.textContent=msg; m.title=msg;
  row.append(i,m); logEl.appendChild(row); logEl.scrollTop=logEl.scrollHeight;
  lc.textContent=++n; lc.classList.add('has');
}
function setPkg(id,state,lbl){
  const r=e('pkg-'+id), s=e('st-'+id);
  if(r) r.className='pkg-row '+state;
  if(s) s.textContent=lbl;
}
function go(){
  btn.disabled=true;
  bi.innerHTML='<span class="spin">⟳</span>';
  bl.textContent='Instaliram...';
  e('pw').classList.add('show');
  if(!lb.classList.contains('open')) tgl();
  fetch('/start').then(()=>{
    const sse=new EventSource('/stream');
    sse.onmessage=ev=>{
      const d=JSON.parse(ev.data);
      if(d.t==='pkg_start'){setPkg(d.pkg,'installing','⟳ Instaliram...');pt.innerHTML='Instaliram <strong>'+d.pkg+'</strong>...';addLog('Instaliram '+d.pkg+'...','di');}
      if(d.t==='pkg_done'){setPkg(d.pkg,'done','✓ OK');addLog(d.pkg+' OK','ok');}
      if(d.t==='pkg_err'){setPkg(d.pkg,'error','✗ Greška');addLog('GREŠKA: '+d.pkg+(d.d?' — '+d.d:''),'er');}
      if(d.t==='prog'){pf.style.width=Math.round(d.d/d.tot*100)+'%';}
      if(d.t==='log'&&d.m) addLog(d.m,'di');
      if(d.t==='done'){
        _evtDone=true; sse.close(); pf.style.width='100%'; pf.classList.add('done');
        if(d.ok){
          pt.innerHTML='<strong>Instalacija završena!</strong>';
          setStep(3);
          bi.textContent='✓'; bl.textContent='Instalirano';
          btn.style.cssText='display:flex;align-items:center;justify-content:center;gap:9px;'+
            'width:100%;padding:13px 20px;border-radius:var(--r);font-family:inherit;'+
            'font-size:.94rem;font-weight:700;letter-spacing:-.01em;cursor:default;'+
            'background:rgba(129,140,248,.08);border:1px solid rgba(129,140,248,.2);'+
            'color:var(--a1);box-shadow:none';
          btnL.classList.add('show');
          addLog('Sve instalirano.','ok');
        } else {
          pt.innerHTML='<strong style="color:var(--err)">Instalacija nije uspela.</strong>';
          btn.disabled=false; btn.style.cssText=''; bi.textContent='↺'; bl.textContent='Pokusaj ponovo';
          addLog('Pogledaj log za detalje.','er');
        }
      }
    };
    sse.onerror=()=>{if(!_evtDone){addLog('Greška veze — pokušavam ponovo...','di');}else{sse.close();}};
  });
}
function launch(){
  btnL.innerHTML='<span class="spin">⟳</span><span>Pokretanje...</span>';
  btnL.disabled=true;
  setTimeout(()=>{
    btnL.innerHTML='<span>✓</span><span>Aplikacija pokrenuta!</span>';
  }, 600);
  fetch('/launch').catch(()=>{});
}
</script></body></html>"""


def _build_html() -> str:
    rows = "".join(
        f'<div class="pkg-row" id="pkg-{pid}">'
        f'<div class="pkg-ic">{ico}</div>'
        f'<div class="pkg-info"><div class="pkg-name">{name}</div>'
        f'<div class="pkg-desc">{desc}</div></div>'
        f'<div class="pkg-st" id="st-{pid}">Ceka</div></div>'
        for pid, ico, name, desc in _PACKAGES
    )
    return _HTML.replace("__VER__", sys.version.split()[0]).replace("__ROWS__", rows)


def _run_install():
    total = len(_PACKAGES)
    for idx, (pid, _ico, _name, _desc) in enumerate(_PACKAGES):
        _add_event({"t": "pkg_start", "pkg": pid})
        _add_event({"t": "prog",      "d": idx, "tot": total})
        proc = subprocess.Popen(
            [sys.executable, "-m", "pip", "install", pid, "--upgrade"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
        )
        last = ""
        for raw in proc.stdout:
            line = _ANSI.sub("", raw).strip()
            if not line:
                continue
            last = line
            if any(k in line.lower() for k in
                   ("successfully", "already", "error", "warning",
                    "collecting", "downloading", "installing",
                    "building", "running", "failed", "note", "requires")):
                _add_event({"t": "log", "m": line})
        proc.wait()
        if proc.returncode == 0:
            _add_event({"t": "pkg_done", "pkg": pid})
        else:
            _add_event({"t": "pkg_err",  "pkg": pid, "d": last})
            _add_event({"t": "done", "ok": False})
            return
        _add_event({"t": "prog", "d": idx + 1, "tot": total})
    _add_event({"t": "done", "ok": True})


class _H(BaseHTTPRequestHandler):
    def log_message(self, *_): pass

    def do_GET(self):
        global _started
        p = self.path.split("?")[0]
        if p == "/":
            body = _build_html().encode("utf-8")
            self._send(200, "text/html; charset=utf-8", body)
        elif p == "/start":
            if not _started:
                _started = True
                with _events_cond:
                    _events.clear()
                threading.Thread(target=_run_install, daemon=True).start()
            self._json({"ok": True})
        elif p == "/stream":
            self.send_response(200)
            self.send_header("Content-Type",      "text/event-stream")
            self.send_header("Cache-Control",     "no-cache")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()
            last_id = self.headers.get("Last-Event-Id", "")
            cursor = (int(last_id) + 1) if last_id.isdigit() else 0
            deadline = time.monotonic() + 1800
            try:
                while True:
                    with _events_cond:
                        if cursor >= len(_events):
                            _events_cond.wait(timeout=20)
                        batch = list(_events[cursor:])
                    if not batch:
                        if time.monotonic() >= deadline:
                            break
                        self.wfile.write(b": ping\n\n")
                        self.wfile.flush()
                        continue
                    for i, evt in enumerate(batch):
                        self.wfile.write(
                            f"id: {cursor + i}\n"
                            f"data: {json.dumps(evt, ensure_ascii=False)}\n\n"
                            .encode())
                    cursor += len(batch)
                    self.wfile.flush()
                    if any(e.get("t") == "done" for e in batch):
                        break
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
        elif p == "/launch":
            try:
                subprocess.Popen(["pythonw", str(_dir / "app.py")])
            except FileNotFoundError:
                subprocess.Popen([sys.executable, str(_dir / "app.py")])
            self._json({"ok": True})
            threading.Thread(target=_close_app, daemon=True).start()
        else:
            self.send_response(404)
            self.end_headers()

    def _send(self, code, ct, body):
        self.send_response(code)
        self.send_header("Content-Type",   ct)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, d):
        self._send(200, "application/json", json.dumps(d).encode())


def _close_app():
    time.sleep(1.0)
    if _window:
        try:
            _window.destroy()
        except Exception:
            pass
    if _server:
        threading.Thread(target=_server.shutdown, daemon=True).start()


if __name__ == "__main__":
    if sys.version_info < (3, 9):
        _show_error(f"Potreban Python 3.9+.\nImas {sys.version_info.major}.{sys.version_info.minor}.")
        sys.exit(1)

    if sys.version_info >= (3, 13):
        _show_error(
            f"Upozorenje: Python {sys.version_info.major}.{sys.version_info.minor} "
            f"je prenov — paketi poput PyMuPDF nemaju gotove wheel-ove za ovu verziju.\n\n"
            "Preporučena verzija: Python 3.11 ili 3.12\n"
            "Preuzmi na: python.org/downloads\n\n"
            "Možeš nastaviti, ali instalacija može biti spora ili neuspešna."
        )

    if not _bootstrap():
        _show_error("pywebview nije mogao da se instalira.\n\nPokusaj rucno:\n  pip install pywebview")
        sys.exit(1)

    import webview

    try:
        _server = _ThreadingHTTPServer(("127.0.0.1", _PORT), _H)
    except OSError:
        _show_error(
            f"Port {_PORT} je zauzet.\n\n"
            "Zatvori sve prethodne instance instalatora pa pokusaj ponovo."
        )
        sys.exit(1)

    threading.Thread(target=_server.serve_forever, daemon=True).start()

    for _ in range(30):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{_PORT}/")
            break
        except Exception:
            time.sleep(0.1)

    _window = webview.create_window(
        "PDF Prevodilac — Instalacija",
        f"http://127.0.0.1:{_PORT}",
        width=540, height=700,
        resizable=True,
        min_size=(480, 580),
    )
    webview.start()

    _server.shutdown()
    _server.server_close()
