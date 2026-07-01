# PNB Sahayak — Multilingual Employee Policy Voice Assistant

A voice assistant for **Punjab National Bank** employees. A branch or back-office
staff member asks a question out loud — in **Hindi, English, or Hinglish** — about the
bank's internal policies. The assistant:

- **understands** the spoken question (Sarvam **Saaras**),
- **finds** the answer in a set of **real PNB policy documents** (keyword search),
- **answers only from those documents** and **shows the exact source**, speaking the
  reply back in the user's language (Sarvam **Mayura** + **sarvam-30b** + **Bulbul**),
- **drafts routine content** (emails, notes, replies) grounded in the same documents,
- and when it **isn't confident, it doesn't guess** — it raises a follow-up **ticket**
  via an **n8n** workflow.

It also includes a **governance dashboard** and an **optional real-time streaming** demo.

Built on the **Sarvam** AI stack. Runs locally with Python + FastAPI.

> ⚠️ **Data note:** every policy document is a **genuine, public PNB file** (HR circulars
> from the staff portal and customer policies from pnbindia.in). They are copyrighted, so
> the PDFs and extracted text are **git-ignored**; the repo ships the scripts that rebuild
> the knowledge base.

---

## What it can do

| Capability | Where |
|------------|-------|
| 🎙️ Turn-by-turn voice Q&A (Hindi / English / Hinglish + 8 more languages) | home page `/` |
| 📄 Answers grounded in 56 real PNB documents, with the genuine source shown | home page |
| ✍️ Draft or summarise — emails, notes, key points, replies — grounded in policy | home page (Draft mode) |
| ✉️ Email an answer to anyone, translated into any of 11 languages | home page |
| 🚫 Honest "I can't find that" → **escalates** to a follow-up ticket | home page + n8n |
| 📊 Governance dashboard (questions, languages, confidence, escalations) | `/dashboard` |
| 🔴 Real-time streaming captions (optional, separate) | `/stream` |

## Architecture

> speak → **Saaras** (speech→text) → **Mayura** (translate, if needed) → **BM25 search**
> of real PNB docs → **sarvam-30b** (grounded answer / draft + citation) → **Mayura**
> (translate back) → **Bulbul** (speak) — and unanswered questions become **n8n** tickets.

**System context**

![System context](docs/diagrams/1-system-context.png)

**RAG / knowledge pipeline — grounded, no hallucination**

![RAG pipeline](docs/diagrams/4-rag-pipeline.png)

See **[docs/architecture.md](docs/architecture.md)** for all six views — system context, layered
components, end-to-end sequence with a latency budget, the RAG pipeline, the agentic escalation
workflow, and the on-prem deployment — plus security, NFRs, and the Sarvam-API rationale.

## Sarvam APIs used (and why)

| API / model | Why |
|-------------|-----|
| **Saaras** `saaras:v3` | speech → text (and live streaming) |
| **Mayura** `mayura:v1` (Translate API) | bridge the user's language ↔ the English documents; keep Hinglish consistent |
| **sarvam-30b** (Chat Completions) | write short, grounded answers and drafts (Sarvam recommends 30B for voice) |
| **Bulbul** `bulbul:v3` | speak the answer back in the user's language |
| **Sarvam Vision** (Document Digitization) | OCR the 2 scanned PDFs |

---

## Setup

**1. Install Python 3** (3.10+). Check with `py --version`.

**2. Install the dependencies:**
```
py -m pip install -r requirements.txt
```

**3. Add your Sarvam API key:** copy `.env.example` to `.env` and paste your key:
```
SARVAM_API_KEY=sk_your_real_key_here
```
(Optional) add your `N8N_WEBHOOK_URL` for live escalations — otherwise tickets are still
saved locally.

**4. Build the knowledge base** (downloads the real PNB documents and extracts the text):
```
py src/ingest/download_pdfs.py        # HR / retiree circulars
py src/ingest/download_extra_pdfs.py  # customer policies (KYC, rights, etc.)
py src/ingest/extract_text.py         # pull out the text layer
py src/ingest/ocr_pdfs.py             # OCR the 2 scanned PDFs (Sarvam Vision)
```

## Run the assistant
```
py src/app.py
```
Open **http://127.0.0.1:8000** in Chrome or Edge. Click the mic (allow it the first
time) or type a question. Footer links go to the **dashboard** and the **streaming** demo.
Stop with **Ctrl + C**.

---

## Project structure
```
PnB Assistant/
├─ README.md                 ← you are here
├─ requirements.txt          ← Python dependencies
├─ .env.example              ← template for your API key (real .env is git-ignored)
├─ src/
│  ├─ app.py                 ← FastAPI server: /, /dashboard, /stream, /api/*, /ws/transcribe
│  ├─ sarvam_client.py       ← listen / translate / think / speak wrappers
│  ├─ knowledge_base.py      ← BM25 search over the policy text
│  ├─ assistant.py           ← the answer brain (grounding, citations, language lock, drafting)
│  ├─ escalation.py          ← unanswered → ticket → n8n
│  ├─ interaction_log.py     ← logs every interaction (feeds the dashboard)
│  ├─ hello_sarvam.py        ← Phase-1 connection test
│  ├─ ingest/                ← scripts that rebuild the knowledge base
│  └─ web/                   ← index.html, dashboard.html, stream.html
├─ docs/
│  ├─ architecture.md        ← diagrams + Sarvam API rationale
│  ├─ diagrams/              ← rendered PNG exports of every diagram (for slides)
│  ├─ sarvam-api-reference.md← verified endpoints/models
│  ├─ document-guide.md      ← what each of the 56 documents is
│  ├─ question-bank.md       ← 12 questions × 11 languages
│  ├─ question-answer-key.md ← expected answers + sources
│  └─ demo-script.md         ← 3–5 minute demo narration
└─ data/policies/            ← (git-ignored) downloaded PDFs + extracted text + manifest
```

## Notes
- **Languages:** Saaras understands 22 Indian languages; Bulbul speaks 11 — so spoken
  answers cover 11 languages, with text answers possible for more.
- **Privacy:** your API key lives only in `.env` (git-ignored); copyrighted PDFs/text and
  runtime logs are git-ignored too.
- This is a **demonstration project** built from a public PNB Generative-AI tender use case.
