# PNB Employee Voice Assistant

A multilingual (Hindi / English / Hinglish) voice assistant that answers Punjab
National Bank employees' questions about internal policies — by listening to a
spoken question, finding the answer in the bank's policy documents, and speaking
the answer back in the same language, while showing the exact source document.

Built on the **Sarvam** AI stack (Saaras speech-to-text, sarvam LLM,
Bulbul text-to-speech, and Translate).

> ⚠️ All policy documents in this project are **fictional samples** created for a
> demo. They are not real PNB material.

---

## Project status

Currently in **Phase 1 — Setup & "hello Sarvam" connection test**.
This README will be expanded with full setup and architecture details in Phase 8.

## Folder layout

| Folder | What's inside |
|--------|---------------|
| `src/`  | the application code |
| `docs/` | documentation, notes, and the architecture diagram |
| `data/policies/` | the sample (fictional) PNB policy documents |

## Setup (quick version — full version coming in Phase 8)

1. Install the Python packages: `py -m pip install -r requirements.txt`
2. Copy `.env.example` to `.env` and paste your Sarvam API key inside it.
