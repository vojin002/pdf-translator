# PDF Translator

A desktop app that translates PDF files from one language to another while keeping the original look — same layout, same fonts, same structure.

![Python](https://img.shields.io/badge/Python-3.9+-blue)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux-lightgrey)

---

## What does it do?

You drag in a PDF, pick the languages, click Translate — and get back a translated PDF that looks just like the original. No subscriptions, no uploading your files to some website. Everything runs on your computer.

Translation is done through Google Translate (free, no API key needed). Only the text from your PDF is sent — not the file itself.

---

## How to install and run

**Windows** — just double-click **`Start.bat`**.

- If Python is not installed → it installs it automatically, then opens the app
- If Python is already installed → opens the app directly

No manual setup needed. Everything is automatic.

---

**Linux** — open a terminal and run:

```bash
sudo apt install python3-gi gir1.2-webkit2-4.0
git clone https://github.com/vojin002/pdf-translator.git
cd pdf-translator
chmod +x run.sh
./run.sh
```

---

## How to use it

1. Double-click `Start.bat`
2. Pick your source and target language — the app remembers your choice next time
3. Drag one or more PDFs into the window, or click to browse
4. Click **Translate PDF** or **Translate N PDFs**
5. Wait for the progress to finish
6. Click **⬇ Download** next to each file, or **⬇ Download all as ZIP** if you translated multiple files

During translation you can **pause** ⏸, **resume** ▶, or **cancel** ✕ at any time.

If you minimize the window while it's working, you'll get a desktop notification when it's done.

---

## Scanned PDFs (optional)

If your PDF is a scanned document (pages are images, not real text), the app can still translate it — but you need to install Tesseract first:

**Windows:**
1. Download and install Tesseract from [here](https://github.com/tesseract-ocr/tesseract)
2. Then run: `pip install pytesseract Pillow`

**Linux:**
```bash
sudo apt install tesseract-ocr
pip install pytesseract Pillow
```

Once installed, the app detects scanned pages automatically and handles them.

---

## Known limitations

- macOS is not supported
- Very complex layouts (multi-column text, tables) might not look perfect after translation
- Translation quality depends on Google Translate
- Translation uses adaptive rate control — starts fast and automatically slows down if Google Translate rate limits are detected, then recovers
