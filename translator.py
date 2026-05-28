import sys
import os
import re
import json
import time
import threading
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


_FONT_ENTRIES = [
    ("arial",       False, False, "arial.ttf"),
    ("arial",       True,  False, "arialbd.ttf"),
    ("arial",       False, True,  "ariali.ttf"),
    ("arial",       True,  True,  "arialbi.ttf"),
    ("helvetica",   False, False, "arial.ttf"),
    ("helvetica",   True,  False, "arialbd.ttf"),
    ("helvetica",   False, True,  "ariali.ttf"),
    ("helvetica",   True,  True,  "arialbi.ttf"),
    ("times",       False, False, "times.ttf"),
    ("times",       True,  False, "timesbd.ttf"),
    ("times",       False, True,  "timesi.ttf"),
    ("times",       True,  True,  "timesbi.ttf"),
    ("calibri",     False, False, "calibri.ttf"),
    ("calibri",     True,  False, "calibrib.ttf"),
    ("calibri",     False, True,  "calibrii.ttf"),
    ("calibri",     True,  True,  "calibriz.ttf"),
    ("cambria",     False, False, "cambria.ttc"),
    ("cambria",     True,  False, "cambriab.ttf"),
    ("cambria",     False, True,  "cambriai.ttf"),
    ("cambria",     True,  True,  "cambriaz.ttf"),
    ("georgia",     False, False, "georgia.ttf"),
    ("georgia",     True,  False, "georgiab.ttf"),
    ("georgia",     False, True,  "georgiai.ttf"),
    ("georgia",     True,  True,  "georgiaz.ttf"),
    ("verdana",     False, False, "verdana.ttf"),
    ("verdana",     True,  False, "verdanab.ttf"),
    ("verdana",     False, True,  "verdanai.ttf"),
    ("verdana",     True,  True,  "verdanaz.ttf"),
    ("tahoma",      False, False, "tahoma.ttf"),
    ("tahoma",      True,  False, "tahomabd.ttf"),
    ("trebuchet",   False, False, "trebuc.ttf"),
    ("trebuchet",   True,  False, "trebucbd.ttf"),
    ("trebuchet",   False, True,  "trebucit.ttf"),
    ("trebuchet",   True,  True,  "trebucbi.ttf"),
    ("courier",     False, False, "cour.ttf"),
    ("courier",     True,  False, "courbd.ttf"),
    ("courier",     False, True,  "couri.ttf"),
    ("courier",     True,  True,  "courbi.ttf"),
    ("palatino",    False, False, "pala.ttf"),
    ("palatino",    True,  False, "palab.ttf"),
    ("palatino",    False, True,  "palai.ttf"),
    ("palatino",    True,  True,  "palabi.ttf"),
    ("garamond",    False, False, "GARA.TTF"),
    ("garamond",    True,  False, "GARABD.TTF"),
    ("impact",      False, False, "impact.ttf"),
    ("comic",       False, False, "comic.ttf"),
    ("comic",       True,  False, "comicbd.ttf"),
    ("segoe",       False, False, "segoeui.ttf"),
    ("segoe",       True,  False, "segoeuib.ttf"),
    ("segoe",       False, True,  "segoeuii.ttf"),
    ("segoe",       True,  True,  "segoeuiz.ttf"),
    ("bookman",     False, False, "BKANT.TTF"),
    ("gothic",      False, False, "GOTHIC.TTF"),
    ("franklin",    False, False, "FRAMD.TTF"),
    ("franklin",    True,  False, "FRAMDIT.TTF"),
    ("century",     False, False, "CENTURY.TTF"),
]

_FONTS_DIR = r"C:\Windows\Fonts"
_FAMILY_INDEX: dict = {}

for _family, _bold, _italic, _filename in _FONT_ENTRIES:
    _path = os.path.join(_FONTS_DIR, _filename)
    if os.path.exists(_path):
        _FAMILY_INDEX.setdefault(_family, []).append((_bold, _italic, _path))

_DEFAULT_FONT: str = ""
for _fp in [r"C:\Windows\Fonts\calibri.ttf", r"C:\Windows\Fonts\arial.ttf",
            r"C:\Windows\Fonts\verdana.ttf", r"C:\Windows\Fonts\tahoma.ttf"]:
    if os.path.exists(_fp):
        _DEFAULT_FONT = _fp
        break

_font_resolve_cache: dict = {}


def resolve_font(pdf_font_name: str, flags: int) -> str:
    cache_key = (pdf_font_name, flags)
    if cache_key in _font_resolve_cache:
        return _font_resolve_cache[cache_key]
    name = pdf_font_name.split("+")[-1] if "+" in pdf_font_name else pdf_font_name
    n = name.lower()
    is_bold = bool(flags & (1 << 4)) or any(k in n for k in ("bold", "-bd", ",bold"))
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
            exact = next((p for b, i, p in variants if b == is_bold and i == is_italic), None)
            regular = next((p for b, i, p in variants if not b and not i), None)
            result = exact or regular or result
            if exact or regular:
                break
    _font_resolve_cache[cache_key] = result
    return result


_tl = threading.local()


def _get_translator(src: str, tgt: str) -> GoogleTranslator:
    key = f"tr_{src}_{tgt}"
    if not hasattr(_tl, key):
        setattr(_tl, key, GoogleTranslator(source=src, target=tgt))
    return getattr(_tl, key)


_api_sem = threading.Semaphore(2)
_rate_lock = threading.Lock()
_last_call_ts: float = 0.0
_MIN_INTERVAL = 0.12

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
    'ﬀ': 'ff', 'ﬁ': 'fi', 'ﬂ': 'fl',
    'ﬃ': 'ffi', 'ﬄ': 'ffl', 'ﬅ': 'ft', 'ﬆ': 'st',
    '\xad': '', '​': '', '‌': '', '‍': '', '﻿': '',
    '’': "'", '‘': "'", '“': '"', '”': '"',
    '–': '-', '—': '-', ' ': ' ',
})

_HYPHEN_BREAK = re.compile(r'(\w)-\n(\w)')
_MULTI_SPACE  = re.compile(r'  +')


def _preprocess(text: str) -> str:
    text = text.translate(_LIGATURES)
    text = _HYPHEN_BREAK.sub(r'\1\2', text)
    text = text.replace('\n', ' ')
    text = _MULTI_SPACE.sub(' ', text)
    return text.strip()


_norm = _preprocess


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


_SEP = " ⟦§⟧ "
_SEP_PAT = re.compile(r"\s*⟦§⟧\s*")


def _call(text: str, src: str, tgt: str) -> str:
    global _last_call_ts
    with _api_sem:
        with _rate_lock:
            gap = _MIN_INTERVAL - (time.monotonic() - _last_call_ts)
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
    MAX = 4500
    if len(n) <= MAX:
        result = _call(n, src, tgt)
        _cache_set(ck, result)
        return result
    sentences = _SENT_END.split(n)
    chunks, cur = [], ""
    for sent in sentences:
        if len(cur) + len(sent) + 1 > MAX:
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
    if len(joined) > 4500:
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
                  progress_callback=None, pause_event=None) -> bool:
    input_path = os.path.abspath(input_path)
    if not os.path.exists(input_path):
        _safe_print(f"Error: file not found - {input_path}")
        return False
    if output_path is None:
        p = Path(input_path)
        output_path = str(p.parent / f"{p.stem}_translated.pdf")

    _safe_print("\n" + "=" * 56)
    _safe_print("  PDF TRANSLATOR  -  english -> serbian")
    _safe_print("=" * 56)
    _safe_print(f"  Input  : {input_path}")
    _safe_print(f"  Output : {output_path}")

    doc = fitz.open(input_path)
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
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = {pool.submit(translate_batch, g, src_lang, tgt_lang): len(g) for g in groups}
            for future in as_completed(futures):
                future.result()
                done_count += futures[future]
                if progress_callback:
                    progress_callback({"type": "translating", "done": done_count, "total": len(need_api), "pages": total})
    else:
        if progress_callback:
            progress_callback({"type": "translating", "done": 0, "total": 0, "pages": total})

    for i in range(total):
        if pause_event is not None and not pause_event.is_set():
            if progress_callback:
                progress_callback({"type": "paused", "page": i + 1, "total": total})
            pause_event.wait()
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

        for blk in blocks:
            page.add_redact_annot(blk["rect"], fill=(1, 1, 1))
        page.apply_redactions(**_redact_kw)

        for blk, tr in zip(blocks, translations):
            insert_text_block(page, blk["rect"], tr,
                              blk["size"], blk["color"], blk["font_name"], blk["flags"])

        _safe_print(f"  [{i+1}/{total}] Done ({len(blocks)} blocks)", flush=True)
        if progress_callback:
            progress_callback({"type": "page_done", "page": i + 1, "total": total})

    _save_cache()

    _safe_print("\n  Saving PDF...")
    doc.save(output_path, garbage=4, deflate=True)
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
