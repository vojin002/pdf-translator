import os
import sys
import time
import json
import uuid
import queue
import threading
import tempfile
import urllib.request
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent))

try:
    from flask import Flask, request, jsonify, Response, send_file
except ImportError:
    print("\n[ERROR] Flask not installed. Run install.bat\n")
    sys.exit(1)

import translator as core

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024

JOBS: dict = {}
INDEX_HTML = Path(__file__).parent / "index.html"


@app.route("/")
def index():
    return INDEX_HTML.read_text(encoding="utf-8")


@app.route("/upload", methods=["POST"])
def upload():
    f = request.files.get("pdf")
    if not f or not f.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Not a valid PDF file"}), 400
    job_id = uuid.uuid4().hex[:10]
    tmp = tempfile.gettempdir()
    input_path = os.path.join(tmp, f"{job_id}_in.pdf")
    output_path = os.path.join(tmp, f"{job_id}_out.pdf")
    f.save(input_path)
    resume_event = threading.Event()
    resume_event.set()
    JOBS[job_id] = {
        "input_path":   input_path,
        "output_path":  output_path,
        "filename":     f.filename,
        "src_lang":     request.form.get("src_lang", "en"),
        "tgt_lang":     request.form.get("tgt_lang", "sr"),
        "queue":        queue.Queue(),
        "resume_event": resume_event,
        "done":         False,
    }
    return jsonify({"job_id": job_id})


@app.route("/translate/<job_id>")
def start_translate(job_id):
    job = JOBS.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    threading.Thread(target=_run_job, args=(job_id,), daemon=True).start()
    return jsonify({"status": "started"})


def _run_job(job_id: str):
    job = JOBS[job_id]
    q = job["queue"]

    def cb(msg):
        q.put(msg)

    try:
        ok = core.translate_pdf(
            job["input_path"],
            job["output_path"],
            src_lang=job["src_lang"],
            tgt_lang=job["tgt_lang"],
            progress_callback=cb,
            pause_event=job["resume_event"],
        )
        q.put({"type": "done"} if ok else {"type": "error", "msg": "Translation failed"})
    except Exception as e:
        q.put({"type": "error", "msg": str(e)})
    finally:
        job["done"] = True


@app.route("/pause/<job_id>", methods=["POST"])
def pause_job(job_id):
    job = JOBS.get(job_id)
    if not job or job["done"]:
        return jsonify({"error": "Job not active"}), 404
    job["resume_event"].clear()
    return jsonify({"status": "paused"})


@app.route("/resume/<job_id>", methods=["POST"])
def resume_job(job_id):
    job = JOBS.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    job["resume_event"].set()
    return jsonify({"status": "resumed"})


@app.route("/stream/<job_id>")
def stream(job_id):
    job = JOBS.get(job_id)
    if not job:
        return "", 404

    def generate():
        q = job["queue"]
        while True:
            try:
                msg = q.get(timeout=180)
            except queue.Empty:
                yield 'data: {"type":"error","msg":"Timeout"}\n\n'
                break
            yield f"data: {json.dumps(msg, ensure_ascii=False)}\n\n"
            if msg.get("type") in ("done", "error"):
                break

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/download/<job_id>")
def download(job_id):
    job = JOBS.get(job_id)
    if not job or not os.path.exists(job["output_path"]):
        return "File not found", 404
    stem = Path(job["filename"]).stem
    return send_file(
        job["output_path"],
        as_attachment=True,
        download_name=f"{stem}_translated.pdf",
        mimetype="application/pdf",
    )


def _build_icon(dest: str):
    import struct
    SIZE = 32
    BG = (241, 102, 99, 255)
    DOC = (255, 255, 255, 255)
    FLD = (254, 210, 199, 255)
    LN = (248, 140, 129, 255)
    g = [[BG] * SIZE for _ in range(SIZE)]
    for r in range(4, 28):
        for c in range(7, 25):
            if r < 10:
                cut = 18 + (r - 4)
                if c < cut:
                    g[r][c] = DOC
                elif c == cut:
                    g[r][c] = FLD
            else:
                g[r][c] = DOC
    for c in range(10, 23):
        g[14][c] = LN
        g[15][c] = LN
    for c in range(10, 23):
        g[19][c] = LN
        g[20][c] = LN
    for c in range(10, 19):
        g[24][c] = LN
        g[25][c] = LN
    px = bytearray()
    for r in reversed(range(SIZE)):
        for c in range(SIZE):
            px.extend(g[r][c])
    and_mask = bytes(SIZE * 4)
    bih = struct.pack('<IiiHHIIiiII', 40, SIZE, SIZE * 2, 1, 32, 0, 0, 0, 0, 0, 0)
    img = bih + bytes(px) + and_mask
    header = struct.pack('<HHH', 0, 1, 1)
    entry = struct.pack('<BBBBHHII', SIZE, SIZE, 0, 0, 1, 32, len(img), 6 + 16)
    with open(dest, 'wb') as f:
        f.write(header + entry + img)


if __name__ == "__main__":
    try:
        import webview
    except ImportError:
        print("\n[ERROR] pywebview not installed. Run install.bat\n")
        sys.exit(1)

    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("PDFTranslator.App.1")
    except Exception:
        pass

    PORT = 5173

    icon_path = str(Path(__file__).parent / "icon.ico")
    if not os.path.exists(icon_path):
        try:
            _build_icon(icon_path)
        except Exception:
            icon_path = None

    def _run_flask():
        import logging
        logging.getLogger("werkzeug").setLevel(logging.ERROR)
        app.run(host="127.0.0.1", port=PORT, debug=False, threaded=True, use_reloader=False)

    threading.Thread(target=_run_flask, daemon=True).start()

    for _ in range(25):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/")
            break
        except Exception:
            time.sleep(0.2)

    webview.create_window(
        "PDF Translator",
        f"http://127.0.0.1:{PORT}",
        width=640,
        height=860,
        resizable=True,
        min_size=(480, 600),
    )
    webview.start(icon=icon_path)
