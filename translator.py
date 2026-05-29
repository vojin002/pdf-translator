import sys
import os
import re
import json
import time
import threading
import platform
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

def _safe_print(*args, **kwargs):
    try:
        print(*args, **kwargs)
    except Exception:
        pass


def check_deps():
    missing = []
    for pkg, pip_name in [("fitz", "pymupdf"), ("deep_translator", "deep-translator")]:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pip_name)
    if missing:
        _safe_print(f"\n[ERROR] Missing packages. Run install.bat")
        _safe_print(f"        Or: pip install {' '.join(missing)}")
        sys.exit(1)


check_deps()

import fitz
import inspect as _inspect
from deep_translator import GoogleTranslator

try:
    _redact_kw = ({"images": 0, "graphics": 0}
                  if "graphics" in _inspect.signature(fitz.Page.apply_redactions).parameters
                  else {"images": 0})
except Exception:
    _redact_kw = {"images": 0}
del _inspect

# --- optional OCR support ---
try:
    import pytesseract as _tess
    from PIL import Image as _PILImage
    _OCR_AVAILABLE = True
except ImportError:
    _OCR_AVAILABLE = False


# --- cross-platform font discovery ---

def _font_dirs() -> list:
    home = Path.home()
    system = platform.system()
    if system == "Windows":
        return [os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")]
    if system == "Darwin":
        return [
            "/Library/Fonts",
            "/System/Library/Fonts",
            str(home / "Library" / "Fonts"),
        ]
    return [
        "/usr/share/fonts",
        "/usr/local/share/fonts",
        str(home / ".fonts"),
        str(home / ".local" / "share" / "fonts"),
    ]


def _scan_fonts(dirs: list) -> dict:
    index: dict = {}
    for d in dirs:
        if not os.path.isdir(d):
            continue
        for root, _, files in os.walk(d):
            for fname in files:
                if not fname.lower().endswith((".ttf", ".otf", ".ttc")):
                    continue
                path = os.path.join(root, fname)
                stem = fname.lower().rsplit(".", 1)[0]
                bold   = any(k in stem for k in ("bold", "-bd", "heavy", "black"))
                italic = any(k in stem for k in ("italic", "oblique", "-it", "-sl"))
                base = stem
                for s in ("-bolditalic", "-boldoblique", "-bold", "-italic", "-oblique",
                           "-regular", "-light", "-medium", "-condensed", "-narrow",
                           "-black", "-thin", "bolditalic", "boldmt", "bold",
                           "italic", "oblique", "regular", "mt", "ps",
                           "-mt", "-ps", "-bd", "-bi", "-it", "-sl"):
                    if base.endswith(s):
                        base = base[:-len(s)]
                        break
                base = base.strip("-_ ")
                if base:
                    index.setdefault(base, []).append((bold, italic, path))
    return index


def _load_family_index() -> dict:
    import hashlib, pickle
    dirs = _font_dirs()
    mtimes = []
    for d in dirs:
        if os.path.isdir(d):
            try:
                mtimes.append(os.path.getmtime(d))
            except OSError:
                pass
    key = hashlib.md5((str(dirs) + str(mtimes)).encode()).hexdigest()
    cache_path = Path(__file__).parent / ".font_cache"
    try:
        with open(cache_path, "rb") as f:
            stored_key, index = pickle.load(f)
        if stored_key == key:
            return index
    except Exception:
        pass
    index = _scan_fonts(dirs)
    try:
        with open(cache_path, "wb") as f:
            pickle.dump((key, index), f)
    except Exception:
        pass
    return index

_FAMILY_INDEX = _load_family_index()

_DEFAULT_FONT: str = ""
for _fam in ("arial", "helvetica", "liberationsans", "freesans",
             "dejavusans", "calibri", "verdana", "tahoma", "ubuntu"):
    _variants = _FAMILY_INDEX.get(_fam, [])
    _reg = next((p for b, i, p in _variants if not b and not i), None)
    if _reg:
        _DEFAULT_FONT = _reg
        break
del _fam, _variants, _reg

_font_resolve_cache: dict = {}


def resolve_font(pdf_font_name: str, flags: int) -> str:
    cache_key = (pdf_font_name, flags)
    if cache_key in _font_resolve_cache:
        return _font_resolve_cache[cache_key]
    name = pdf_font_name.split("+")[-1] if "+" in pdf_font_name else pdf_font_name
    n = name.lower()
    is_bold   = bool(flags & (1 << 4)) or any(k in n for k in ("bold", "-bd", ",bold"))
    is_italic = (bool(flags & (1 << 1))
                 or any(k in n for k in ("italic", "oblique", "-it", "-sl", ",italic")))
    base = n
    for strip in ("-bolditalic", "-boldoblique", "-bold", "-italic", "-oblique",
                  "-regular", "-light", "-medium", "-narrow", "-condensed",
                  "-black", "-thin", "bolditalic", "boldmt", "bold",
                  "italic", "oblique", "regular", "mt", "ps", "-mt", "-ps"):
        base = base.replace(strip, "")
    base = base.strip("-_ ")
    result = _DEFAULT_FONT
    for family, variants in _FAMILY_INDEX.items():
        if family in base or base.startswith(family[:5]):
            exact   = next((p for b, i, p in variants if b == is_bold and i == is_italic), None)
            regular = next((p for b, i, p in variants if not b and not i), None)
            result  = exact or regular or result
            if exact or regular:
                break
    _font_resolve_cache[cache_key] = result
    return result


# --- translation API ---

_tl = threading.local()


def _get_translator(src: str, tgt: str) -> GoogleTranslator:
    key = f"tr_{src}_{tgt}"
    if not hasattr(_tl, key):
        setattr(_tl, key, GoogleTranslator(source=src, target=tgt))
    return getattr(_tl, key)


_SPEED_PRESETS = {
    'safe':   (1, 0.35),
    'normal': (2, 0.12),
    'fast':   (4, 0.04),
}

_api_sem       = threading.Semaphore(2)
_rate_lock     = threading.Lock()
_last_call_ts: float = 0.0
_current_workers  = 2
_current_interval = 0.12


def _apply_speed(speed: str):
    global _api_sem, _current_workers, _current_interval
    workers, interval = _SPEED_PRESETS.get(speed, _SPEED_PRESETS['normal'])
    _current_workers  = workers
    _current_interval = interval
    _api_sem = threading.Semaphore(workers)

_CACHE_FILE = Path(__file__).parent / "translations_cache.json"
_CACHE_MAX = 2000
_CACHE_MAX_DISK = 5000
_cache: dict = {}
_cache_lock = threading.Lock()


def _load_cache() -> dict:
    try:
        with open(_CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_cache():
    try:
        with _cache_lock:
            snap = dict(list(_cache.items())[-_CACHE_MAX_DISK:])
        with open(_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(snap, f, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        pass


_cache = _load_cache()

_LIGATURES = str.maketrans({
    0xFB00: 'ff', 0xFB01: 'fi', 0xFB02: 'fl',
    0xFB03: 'ffi', 0xFB04: 'ffl', 0xFB05: 'ft', 0xFB06: 'st',
    0x00AD: '',   # soft hyphen
    0x200B: '',   # zero-width space
    0x200C: '',   # zero-width non-joiner
    0x200D: '',   # zero-width joiner
    0xFEFF: '',   # BOM
    0x2018: "'",  # left single quote
    0x2019: "'",  # right single quote
    0x201C: '"',  # left double quote
    0x201D: '"',  # right double quote
    0x2013: '-',  # en dash
    0x2014: '-',  # em dash
    0x00A0: ' ',  # non-breaking space
})

_HYPHEN_BREAK = re.compile(r'(\w)-\n(\w)')
_MULTI_SPACE  = re.compile(r'  +')


def _norm(text: str) -> str:
    text = text.translate(_LIGATURES)
    text = _HYPHEN_BREAK.sub(r'\1\2', text)
    text = text.replace('\n', ' ')
    text = _MULTI_SPACE.sub(' ', text)
    return text.strip()


def _cache_get(key: str):
    with _cache_lock:
        return _cache.get(key)


def _cache_set(key: str, val: str):
    with _cache_lock:
        if len(_cache) >= _CACHE_MAX:
            for k in list(_cache.keys())[:200]:
                del _cache[k]
        _cache[key] = val


def _should_translate(text: str) -> bool:
    stripped = text.strip()
    if len(stripped) < 2:
        return False
    return sum(1 for c in stripped if c.isalpha()) >= 3


_MAX_CHUNK = 4500

_SEP = " ⟦§⟧ "
_SEP_PAT = re.compile(r"\s*⟦§⟧\s*")


def _call(text: str, src: str, tgt: str) -> str:
    global _last_call_ts
    with _api_sem:
        with _rate_lock:
            gap = _current_interval - (time.monotonic() - _last_call_ts)
            if gap > 0:
                time.sleep(gap)
            _last_call_ts = time.monotonic()
        tr = _get_translator(src, tgt)
        for attempt in range(3):
            try:
                r = tr.translate(text)
                return r if r else text
            except Exception as e:
                if attempt == 2:
                    _safe_print(f"    [!] API error (3/3): {e}")
                    return text
                wait = 0.5 * (2 ** attempt)
                _safe_print(f"    [!] API error (attempt {attempt+1}/3), waiting {wait}s: {e}")
                time.sleep(wait)
    return text


_SENT_END = re.compile(r'(?<=[.!?])\s+')


def translate_single(text: str, src: str = "en", tgt: str = "sr") -> str:
    if not text.strip():
        return text
    n = _norm(text)
    if not n:
        return text
    ck = f"{src}|{tgt}|{n}"
    cached = _cache_get(ck)
    if cached is not None:
        return cached
    if len(n) <= _MAX_CHUNK:
        result = _call(n, src, tgt)
        _cache_set(ck, result)
        return result
    sentences = _SENT_END.split(n)
    chunks, cur = [], ""
    for sent in sentences:
        if len(cur) + len(sent) + 1 > _MAX_CHUNK:
            if cur:
                chunks.append(cur)
            cur = sent
        else:
            cur = (cur + " " + sent).strip() if cur else sent
    if cur:
        chunks.append(cur)
    result = " ".join(_call(c, src, tgt) for c in chunks)
    _cache_set(ck, result)
    return result


def translate_batch(texts: list, src: str = "en", tgt: str = "sr") -> list:
    if not texts:
        return []
    if len(texts) == 1:
        return [translate_single(texts[0], src, tgt)]
    normed = [_norm(t) for t in texts]
    cks = [f"{src}|{tgt}|{n}" for n in normed]
    cached_all = [_cache_get(ck) for ck in cks]
    if all(r is not None for r in cached_all):
        return cached_all
    joined = _SEP.join(normed)
    if len(joined) > _MAX_CHUNK:
        mid = len(texts) // 2
        return translate_batch(texts[:mid], src, tgt) + translate_batch(texts[mid:], src, tgt)
    joined_ck = f"{src}|{tgt}|{joined}"
    cached_joined = _cache_get(joined_ck)
    if cached_joined is not None:
        parts = _SEP_PAT.split(cached_joined)
        if len(parts) == len(texts):
            return [p.strip() for p in parts]
    result = _call(joined, src, tgt)
    parts = _SEP_PAT.split(result)
    if len(parts) == len(texts):
        _cache_set(joined_ck, result)
        out = [p.strip() for p in parts]
        for ck, t in zip(cks, out):
            _cache_set(ck, t)
        return out
    _safe_print(f"    [!] Batch separator changed, translating individually ({len(texts)} blocks)")
    return [translate_single(n, src, tgt) for n in normed]


def unpack_color(color) -> tuple:
    if isinstance(color, (list, tuple)) and len(color) >= 3:
        return tuple(float(x if x <= 1.0 else x / 255.0) for x in color[:3])
    if isinstance(color, int):
        return (
            ((color >> 16) & 0xFF) / 255.0,
            ((color >> 8)  & 0xFF) / 255.0,
            (color         & 0xFF) / 255.0,
        )
    return (0.0, 0.0, 0.0)



def _ocr_text(page) -> str:
    if not _OCR_AVAILABLE:
        return ""
    try:
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
        img = _PILImage.frombytes("RGB", [pix.width, pix.height], pix.samples)
        return _tess.image_to_string(img).strip()
    except Exception:
        return ""


def extract_text_blocks(page) -> list:
    data = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
    blocks = []
    for blk in data["blocks"]:
        if blk["type"] != 0:
            continue
        lines_text, anchor_span = [], None
        for line in blk["lines"]:
            lines_text.append("".join(s["text"] for s in line["spans"]))
            if anchor_span is None:
                for s in line["spans"]:
                    if s["text"].strip():
                        anchor_span = s
                        break
        text = "\n".join(lines_text).strip()
        if not text or anchor_span is None:
            continue
        blocks.append({
            "rect":      fitz.Rect(blk["bbox"]),
            "text":      text,
            "size":      anchor_span["size"],
            "color":     unpack_color(anchor_span["color"]),
            "font_name": anchor_span.get("font", ""),
            "flags":     anchor_span.get("flags", 0),
        })

    if not blocks:
        has_images = any(blk["type"] == 1 for blk in data["blocks"])
        if has_images:
            text = _ocr_text(page)
            if text and _should_translate(text):
                blocks.append({
                    "rect":      page.rect,
                    "text":      text,
                    "size":      9.0,
                    "color":     (0.0, 0.0, 0.0),
                    "font_name": "Arial",
                    "flags":     0,
                    "ocr":       True,
                })

    return blocks


def insert_text_block(page, rect: fitz.Rect, text: str,
                      size: float, color: tuple, font_name: str, flags: int):
    font_path = resolve_font(font_name, flags)
    kw = {"color": color, "align": fitz.TEXT_ALIGN_LEFT}
    if font_path:
        kw["fontfile"] = font_path
        kw["fontname"] = Path(font_path).stem
    else:
        kw["fontname"] = "helv"
    for scale in [1.0, 0.90, 0.78, 0.65, 0.55]:
        kw["fontsize"] = round(size * scale, 1)
        if page.insert_textbox(rect, text, **kw) >= 0:
            return
    page.insert_textbox(rect, text, **kw)


def translate_pdf(input_path: str, output_path: str = None,
                  src_lang: str = "en", tgt_lang: str = "sr",
                  progress_callback=None, pause_event=None,
                  cancel_event=None, speed: str = "normal") -> bool:
    input_path = os.path.abspath(input_path)
    if not os.path.exists(input_path):
        _safe_print(f"Error: file not found - {input_path}")
        return False
    if output_path is None:
        p = Path(input_path)
        output_path = str(p.parent / f"{p.stem}_translated.pdf")

    _apply_speed(speed)

    _safe_print("\n" + "=" * 56)
    _safe_print(f"  PDF TRANSLATOR  -  {src_lang} -> {tgt_lang}  [{speed}]")
    if _OCR_AVAILABLE:
        _safe_print("  OCR: enabled")
    _safe_print("=" * 56)
    _safe_print(f"  Input  : {input_path}")
    _safe_print(f"  Output : {output_path}")

    doc = fitz.open(input_path)
    try:
        total = len(doc)
        _safe_print(f"  Pages  : {total}")

        all_blocks = [extract_text_blocks(doc[i]) for i in range(total)]

        need_api: list = []
        seen: set = set()
        for blocks in all_blocks:
            for blk in blocks:
                n = _norm(blk["text"])
                if _should_translate(n) and n not in seen:
                    seen.add(n)
                    if _cache_get(f"{src_lang}|{tgt_lang}|{n}") is None:
                        need_api.append(n)

        cached_count = len(seen) - len(need_api)
        _safe_print(f"  Unique blocks: {len(seen)}  (cached: {cached_count},  api: {len(need_api)})\n")

        if need_api:
            GROUP = 20
            groups = [need_api[i:i + GROUP] for i in range(0, len(need_api), GROUP)]
            done_count = 0
            if progress_callback:
                progress_callback({"type": "translating", "done": 0, "total": len(need_api), "pages": total})
            with ThreadPoolExecutor(max_workers=_current_workers) as pool:
                futures = {pool.submit(translate_batch, g, src_lang, tgt_lang): len(g) for g in groups}
                for future in as_completed(futures):
                    if cancel_event and cancel_event.is_set():
                        break
                    future.result()
                    done_count += futures[future]
                    if progress_callback:
                        progress_callback({"type": "translating", "done": done_count, "total": len(need_api), "pages": total})
        else:
            if progress_callback:
                progress_callback({"type": "translating", "done": 0, "total": 0, "pages": total})

        if cancel_event and cancel_event.is_set():
            return False

        for i in range(total):
            if cancel_event and cancel_event.is_set():
                return False

            if pause_event is not None and not pause_event.is_set():
                if progress_callback:
                    progress_callback({"type": "paused", "page": i + 1, "total": total})
                pause_event.wait()
                if cancel_event and cancel_event.is_set():
                    return False
                if progress_callback:
                    progress_callback({"type": "resumed", "page": i + 1, "total": total})

            page = doc[i]
            blocks = all_blocks[i]

            if not blocks:
                _safe_print(f"  [{i+1}/{total}] No text")
                if progress_callback:
                    progress_callback({"type": "page_done", "page": i + 1, "total": total, "msg": "No text"})
                continue

            if progress_callback:
                progress_callback({"type": "progress", "page": i + 1, "total": total, "msg": f"{len(blocks)} block(s)"})

            translations = []
            for blk in blocks:
                n = _norm(blk["text"])
                tr = _cache_get(f"{src_lang}|{tgt_lang}|{n}") if _should_translate(n) else None
                translations.append(tr if tr is not None else blk["text"])

            is_ocr_page = blocks[0].get("ocr", False)

            if is_ocr_page:
                # Keep original image, add translated text in a white strip at the bottom
                r = page.rect
                strip = fitz.Rect(r.x0 + 10, r.y1 - min(r.height * 0.35, 220),
                                  r.x1 - 10, r.y1 - 10)
                page.add_redact_annot(strip, fill=(1, 1, 1))
                page.apply_redactions(**_redact_kw)
                page.insert_textbox(strip, translations[0],
                                    fontsize=8, color=(0.1, 0.1, 0.1),
                                    align=fitz.TEXT_ALIGN_LEFT)
            else:
                for blk in blocks:
                    page.add_redact_annot(blk["rect"], fill=(1, 1, 1))
                page.apply_redactions(**_redact_kw)
                for blk, tr in zip(blocks, translations):
                    insert_text_block(page, blk["rect"], tr,
                                      blk["size"], blk["color"], blk["font_name"], blk["flags"])

            ocr_label = " [OCR]" if is_ocr_page else ""
            _safe_print(f"  [{i+1}/{total}] Done ({len(blocks)} block(s)){ocr_label}", flush=True)
            if progress_callback:
                progress_callback({"type": "page_done", "page": i + 1, "total": total})

        _save_cache()
        _safe_print("\n  Saving PDF...")
        doc.save(output_path, garbage=4, deflate=True)
    finally:
        doc.close()

    size_kb = os.path.getsize(output_path) // 1024
    _safe_print(f"\n  Done! -> {output_path}  ({size_kb} KB)\n")
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("\nUsage:")
        print("  python translator.py  document.pdf")
        print("  python translator.py  document.pdf  output.pdf")
        print()
        sys.exit(0)
    translate_pdf(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
