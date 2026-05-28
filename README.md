# PDF Prevodilac

Desktop aplikacija za prevod PDF dokumenata sa engleskog na srpski uz očuvanje originalnog izgleda, fontova i rasporeda teksta.

![Python](https://img.shields.io/badge/Python-3.9--3.12-blue)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)
![License](https://img.shields.io/badge/License-MIT-green)

---

## Karakteristike

- **Očuvanje izgleda** — tekst se prevodi direktno u PDF bez narušavanja rasporeda
- **Originalni fontovi** — koristi Windows sistemske fontove koji odgovaraju originalnim
- **Keš prevoda** — jednom prevedeni blokovi se čuvaju lokalno i ne šalju ponovo na API
- **Pauza / nastavak** — prevod može da se pauzira i nastavi u bilo kom trenutku
- **Progres u realnom vremenu** — praćenje napretka po blokovima i stranicama sa procenom preostalog vremena
- **Lokalno** — sve ostaje na računaru, nema slanja dokumenata na eksterne servere osim teksta na Google Translate
- **Besplatno** — koristi Google Translate bez API ključa

---

## Zahtevi

- **Windows** 10 ili noviji
- **Python 3.9 – 3.12** (preporučeno: [Python 3.12](https://www.python.org/downloads/release/python-3120/))
  - Python 3.13+ trenutno nije podržan jer paketi nemaju prebuilt wheel-ove za te verzije
  - Tokom instalacije Pythona obavezno čekirati **"Add Python to PATH"**

---

## Instalacija i pokretanje

### 1. Preuzmi projekat

```bash
git clone https://github.com/vojin002/pdf-translator-sr.git
```

ili preuzmi ZIP sa GitHub-a i raspakuj.

### 2. Pokreni

Dvoklikom na **`Run.pyw`** — to je jedini fajl koji trebaš.

- Ako paketi **nisu instalirani** → automatski se otvara instalater
- Ako paketi **jesu instalirani** → aplikacija se odmah pokreće

> **Napomena:** Potreban je Python 3.9–3.12. Tokom instalacije Pythona obavezno čekirati **"Add Python to PATH"**.

---

## Upotreba

1. **Odaberi PDF** — prevuci fajl u prozor ili klikni za odabir
2. **Prevedi PDF** — klikni dugme, prati napredak u realnom vremenu
3. **Preuzmi** — po završetku klikni "Preuzmi prevedeni PDF" i odaberi lokaciju za čuvanje

### Pauza i nastavak

Tokom prevoda možeš pauzirati proces klikom na dugme `⏸` i nastaviti klikom na `▶`.

---

## Struktura projekta

```
pdf-prevodilac/
├── Run.pyw              # Jedini pokretač — proverava deps, instalira ako treba
├── app.py               # Flask server + pywebview
├── translator.py        # Logika prevoda, font matching, keš
├── installer.py         # Grafički instalater (pokreće se automatski)
├── index.html           # Frontend UI
└── translations_cache.json  # Lokalni keš prevoda (generiše se automatski)
```

---

## Tehnički detalji

| Komponenta | Tehnologija |
|---|---|
| GUI | pywebview (Microsoft Edge WebView2) |
| Backend | Flask (lokalni server, port 5173) |
| PDF obrada | PyMuPDF (fitz) |
| Prevod | deep-translator → Google Translate |
| Streaming | Server-Sent Events (SSE) |
| Keš | JSON fajl, max 5000 unosa |

### Kako radi prevod

1. Svi tekst blokovi se izvlače iz PDF-a
2. Duplicirani blokovi se deduplikuju — isti tekst se prevodi samo jednom
3. Blokovi se grupišu u batch zahteve po 20 (separator-bazirani batch)
4. Paralelni API pozivi (2 threada) ubrzavaju prevod
5. Originalni tekst se briše redakcijom (bela pravougaonika)
6. Prevedeni tekst se upisuje na isto mesto sa originalnim fontom i veličinom
7. Ako prevedeni tekst ne staje, automatski se smanjuje (5 koraka skaliranja)

---

## Poznata ograničenja

- Radi samo na **Windows**-u (koristi Windows Fonts direktorijum)
- PDF-ovi sa tekstom kao slikom (skenirani dokumenti) **nisu podržani** — potreban je selektabilan tekst
- Kvalitet prevoda zavisi od Google Translate-a
- Složeni PDF layout (višekolonski tekst, tabele) može imati neprecizno pozicioniranje

---

## Licenca

MIT
