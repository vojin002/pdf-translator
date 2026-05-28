# PDF Translator

Desktop application for translating PDF documents from English to Serbian (or any supported language pair) while preserving the original layout, fonts, and text arrangement.

![Python](https://img.shields.io/badge/Python-3.9--3.12-blue)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)

---

## Features

- **Layout preservation** — text is translated directly inside the PDF without disrupting the arrangement
- **Original fonts** — uses Windows system fonts that match the originals
- **Translation cache** — once translated, blocks are stored locally and not sent to the API again
- **Pause / resume** — translation can be paused and resumed at any time
- **Real-time progress** — tracks progress by blocks and pages with an estimated time remaining
- **Local** — everything stays on your machine; no documents are sent to external servers (only text goes to Google Translate)
- **Free** — uses Google Translate without an API key

---

## Requirements

- **Windows** 10 or later
- **Python 3.9 – 3.12** (recommended: [Python 3.12](https://www.python.org/downloads/release/python-3120/))
  - Python 3.13+ is not currently supported because packages lack prebuilt wheels for those versions
  - Make sure to check **"Add Python to PATH"** during Python installation

---

## Installation and Running

### 1. Download the project

```bash
git clone https://github.com/vojin002/pdf-translator-sr.git
```

or download the ZIP from GitHub and extract it.

### 2. Run

Double-click **`Run.pyw`** — that is the only file you need.

- If packages **are not installed** → the installer opens automatically
- If packages **are already installed** → the application starts immediately

> **Note:** Python 3.9–3.12 is required. Make sure to check **"Add Python to PATH"** during Python installation.

---

## Usage

1. **Select PDF** — drag a file into the window or click to browse
2. **Translate PDF** — click the button and follow the real-time progress
3. **Download** — once finished, click "Download translated PDF" and choose a save location

### Pause and resume

During translation you can pause the process by clicking `⏸` and resume it by clicking `▶`.

---

## Project structure

```
pdf-prevodilac/
├── Run.pyw              # Single launcher — checks deps, installs if needed
├── app.py               # Flask server + pywebview
├── translator.py        # Translation logic, font matching, cache
├── installer.py         # Graphical installer (launched automatically)
├── index.html           # Frontend UI
└── translations_cache.json  # Local translation cache (generated automatically)
```

---

## Technical details

| Component | Technology |
|---|---|
| GUI | pywebview (Microsoft Edge WebView2) |
| Backend | Flask (local server, port 5173) |
| PDF processing | PyMuPDF (fitz) |
| Translation | deep-translator → Google Translate |
| Streaming | Server-Sent Events (SSE) |
| Cache | JSON file, max 5000 entries |

### How translation works

1. All text blocks are extracted from the PDF
2. Duplicate blocks are deduplicated — identical text is translated only once
3. Blocks are grouped into batch requests of 20 (separator-based batching)
4. Parallel API calls (2 threads) speed up translation
5. Original text is erased by redaction (white rectangles)
6. Translated text is written back in the same position with the original font and size
7. If the translated text does not fit, it is automatically scaled down (5 scaling steps)

---

## Known limitations

- Works on **Windows** only (uses the Windows Fonts directory)
- PDFs with text as images (scanned documents) **are not supported** — selectable text is required
- Translation quality depends on Google Translate
- Complex PDF layouts (multi-column text, tables) may have imprecise positioning
