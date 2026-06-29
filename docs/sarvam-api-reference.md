# Sarvam API — Verified Reference

> Confirmed from the live docs at https://docs.sarvam.ai on **2026-06-29**.
> (Product details change — re-check before relying on this later.)

**Base web address for all calls:** `https://api.sarvam.ai`

**Login / authentication:** every request carries a header named
`api-subscription-key` set to your secret key. (The chat/LLM endpoint also
accepts `Authorization: Bearer <key>`, but we'll use `api-subscription-key`
everywhere for consistency.)

---

## 1. Speech-to-Text — "Saaras" (spoken question → text)
- **Call:** `POST https://api.sarvam.ai/speech-to-text`
- **Sends:** an audio file (multipart form field `file`)
- **Model string:** `saaras:v3`
- **`mode` options:** transcribe, translate, verbatim, translit, codemix
- **Audio formats accepted:** WAV, MP3, AAC, OGG/OPUS, FLAC, M4A, WebM, PCM (16 kHz), and more
- **Languages:** 23 (22 Indian + English), with optional auto language detection

## 2. Text-to-Speech — "Bulbul" (answer text → spoken audio)
- **Call:** `POST https://api.sarvam.ai/text-to-speech`
- **Sends (JSON):** `text` (max 2500 chars for v3), `target_language_code`, optional `speaker`, `model`
- **Model string:** `bulbul:v3`
- **Default speaker:** `shubh` (30+ voices available)
- **Languages:** bn-IN, en-IN, gu-IN, hi-IN, kn-IN, ml-IN, mr-IN, od-IN, pa-IN, ta-IN, te-IN
- **Returns:** base64-encoded audio (default WAV)

## 3. Chat / LLM (reads a document and writes the answer)
- **Call:** `POST https://api.sarvam.ai/v1/chat/completions` (OpenAI-compatible)
- **Sends (JSON):** `messages` array, `model`, optional `reasoning_effort`
- **Model string we use:** `sarvam-30b` — Sarvam recommends the 30B for
  "voice-agent pipelines, interactive chat, high-throughput workloads", which is
  exactly this project. (`sarvam-105b` is the larger flagship, also available.)
- **Reasoning:** these are "thinking" models (`reasoning_effort` default `low`).
  We set `reasoning_effort = null` so the answer comes back directly in
  `message.content` with no thinking pause — important for a snappy voice reply.
  (If reasoning is on, the thinking text appears in `message.reasoning_content`.)

## 4. Translate (cross-language step)
- **Call:** `POST https://api.sarvam.ai/translate`
- **Sends (JSON):** `input`, `source_language_code`, `target_language_code`, `model`
- **Model strings:** `mayura:v1` (max 1000 chars, supports `source_language_code="auto"`)
  or `sarvam-translate:v1` (max 2000 chars, more languages)
- **Languages:** same core set as TTS, plus extended set for sarvam-translate

---

## How the brief's names map to the current models
| Brief calls it | Current model string | Used for |
|----------------|----------------------|----------|
| Saaras | `saaras:v3` | speech-to-text |
| Bulbul | `bulbul:v3` | text-to-speech |
| sarvam-105b | `sarvam-30b` (chosen for voice; 105b also available) | the LLM (answer writing) |
| Translate | `mayura:v1` | cross-language translation |
