# PNB Sahayak — Demo Narration Script (3–5 minutes)

A walkthrough you can read on camera. **SAY** = what to say. **DO** = what to click.
Practise the voice questions once so the timing feels natural.

## Before you record (1-minute checklist)
- [ ] App running: `py src/app.py` → open **http://127.0.0.1:8000** in Chrome/Edge.
- [ ] Microphone allowed in the browser.
- [ ] n8n workflow **Published**, and your **PNB Escalations** Google Sheet open in a tab.
- [ ] Open tabs ready: the assistant `/`, the dashboard `/dashboard`, the streaming page `/stream`.
- [ ] Have [docs/question-bank.md](question-bank.md) handy for the multilingual questions.

---

## 0:00 — Intro (~25s)
**SAY:** "This is PNB Sahayak, a multilingual voice assistant for Punjab National Bank
employees. Staff can ask about internal policies in Hindi, English, or Hinglish and get a
spoken answer — and importantly, it answers only from **real PNB documents** and shows the
exact source. It's built on the Sarvam AI stack."
**DO:** Show the home page; point to *"searching 56 real PNB documents."*

## 0:25 — Core voice Q&A in English (~45s)
**DO:** Click the mic and ask: *"How often must pensioners submit their life certificate?"*
**SAY (while it answers):** "Sarvam's **Saaras** model turns my speech into text; it
searches the real documents, and **sarvam-30b** writes a short answer grounded in what it
found. **Bulbul** speaks it back."
**DO:** Point to the panel — the transcript, the **genuine source document** (a real PNB
link), the **confidence**, and the spoken answer playing.

## 1:10 — Multilingual (~40s)
**DO:** Ask in Hindi/Hinglish (from the question bank), e.g. *"Pension ke liye life
certificate kab jama karna hai?"*
**SAY:** "Same question in Hinglish. **Mayura**, Sarvam's translation model, bridges my
language and the English documents, and the answer comes back in the **same language** —
text and voice stay consistent, no switching."

## 1:35 — Detailed answers & email in any language (~40s)
**DO:** Ask a policy question — you get a **concise** answer. Not enough? Click **Detailed** on that answer and it re-writes the same question in full (the Concise/Detailed toggle sits on every answer; toggling back is instant).
**SAY:** "Employees choose how much detail they want, per answer — read the short version, then expand to the full policy detail on demand."
**DO:** On any answer, click **✉️ Email this answer**, type a **recipient** (a customer or a colleague — any address), choose a **language**, and Send.
**SAY:** "The answer is translated into the chosen language and emailed directly to anyone — a customer or a peer — from the assistant's own mailbox. The employee never types any password."

## 1:50 — Draft, summarise & make notes — grounded in policy (~35s)
**DO:** Tap **✍️ Draft** (next to Answer), then try e.g. *"summarise the life-certificate policy as key points"* — or *"draft an email to a customer about it."* The assistant produces exactly that (bulleted notes, or a ready-to-send email), grounded in the cited policy.
**SAY:** "Beyond answering, it **prepares content** — summaries, key points, notes, emails, replies — using only the approved documents, and it cites the source. Employees can **Copy** it or **email it in any language**."

## 2:25 — It doesn't guess; it escalates (~45s)
**DO:** Ask something not in the documents, e.g. *"What is the current gold loan interest
rate?"*
**SAY:** "A bank assistant must never invent policy. When the answer isn't in the
documents, it says so honestly and **raises a follow-up ticket** instead of guessing."
**DO:** Point to the **ticket number** on screen, then switch to the **n8n** tab and the
**Google Sheet** — show the new ticket **row appear automatically**.
**SAY:** "That's a complete event-to-action chain: an unanswered question becomes a
tracked ticket for the policy team, with no human in the loop."

## 2:35 — Governance dashboard (~30s)
**DO:** Open **/dashboard**.
**SAY:** "Everything is logged for governance: how many questions, in which languages, with
what confidence, and which ones were escalated. A bank needs exactly this oversight — to
see what staff ask and spot gaps in the documents."

## 3:05 — Real-time streaming (~25s)
**DO:** Open **/stream**, click start, and speak a sentence.
**SAY:** "The same listening capability, running in real time — Sarvam's streaming model
transcribes word-by-word as I speak. It runs as a separate, isolated demo."

## 3:55 — Close (~20s)
**SAY:** "So: a multilingual, voice-first assistant that answers PNB staff from genuine
documents, always cites its source, escalates when unsure, and gives the bank governance
and insights — all on the Sarvam stack."

---

## One-line description of each Sarvam API used
- **Saaras** — speech-to-text: turns the spoken question into text (22 Indian languages).
- **Mayura** (Translate API) — translates between the user's language and the documents,
  with code-mixed/Roman styles for natural Hinglish.
- **sarvam-30b** (Chat Completions) — the LLM that reads the found document and writes the
  grounded answer (the 30B is Sarvam's recommended model for voice).
- **Bulbul** — text-to-speech: speaks the answer back in the user's language (11 languages).
- **Sarvam Vision** (Document Digitization) — OCR that turned the scanned PDFs into text.
- **Saaras streaming + batch diarization** — real-time captions, and who-said-what for the
  offline call analytics.

## Backup tips (if something misbehaves on the day)
- Mic not cooperating? **Type** the question instead — same pipeline, same answer.
- n8n trial deactivated? Re-click **Publish**; tickets are also saved locally regardless.
- Spoken answer slow? The text appears in ~1–2s; the voice follows — narrate over it.
