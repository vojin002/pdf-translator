# PDF Translator

A desktop app that translates PDF files from one language to another while keeping the original look — same layout, same fonts, same structure.

![Python](https://img.shields.io/badge/Python-3.9+-blue)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux-lightgrey)

---

## What does it do?

You drag in a PDF, pick the languages, click Translate — and get back a translated PDF that looks just like the original. No subscriptions, no uploading your files to some website. Everything runs on your computer.

Translation is done through Google Translate (free, no API key needed). Only the text from your PDF is sent — not the file itself.

---

## What you need

**Windows**
- Python 3.9 or newer → [download here](https://www.python.org/downloads/)
- During installation, check **"Add Python to PATH"**

**Linux**
- Python 3.9 or newer
- One extra command to install the desktop window engine:
  ```bash
  sudo apt install python3-gi gir1.2-webkit2-4.0
  ```

---

## How to install and run

**Windows** — just double-click `Run.pyw`.

The first time it runs, it will automatically install everything it needs. After that it opens straight into the app.

---

**Linux** — open a terminal and run:

```bash
git clone https://github.com/vojin002/pdf-translator.git
cd pdf-translator
chmod +x run.sh
./run.sh
```

Same as Windows — first launch installs everything, then the app opens.

---

## How to use it

1. Open the app
2. Pick your source and target language — the app remembers your choice next time
3. Drag one or more PDFs into the window, or click to browse
4. Choose translation speed (Safe / Normal / Fast)
5. Click **Translate PDF** or **Translate N PDFs**
6. Wait for the progress to finish
7. Click **⬇ Download** next to each file, or **⬇ Download all as ZIP** if you translated multiple files

During translation you can **pause** ⏸, **resume** ▶, or **cancel** ✕ at any time.

If you minimize the window while it's working, you'll get a desktop notification when it's done.

---

## Translation speed

| Mode | Threads | Best for |
|------|---------|----------|
| 🐢 Safe | 1 | Slow connections or avoiding rate limits |
| ⚡ Normal | 2 | Everyday use (default) |
| 🚀 Fast | 4 | Fast connections, large documents |

---

## Scanned PDFs (optional)

If your PDF is a scanned document (pages are images, not real text), the app can still translate it — but you need to install Tesseract first:

**Linux:**
```bash
sudo apt install tesseract-ocr
pip install pytesseract Pillow
```

**Windows:**
1. Download and install Tesseract from [here](https://github.com/tesseract-ocr/tesseract)
2. Then run: `pip install pytesseract Pillow`

Once installed, the app detects scanned pages automatically and handles them.

---

## Known limitations

- macOS is not supported
- Very complex layouts (multi-column text, tables) might not look perfect after translation
- Translation quality depends on Google Translate
- Fast mode may occasionally hit Google Translate rate limits
