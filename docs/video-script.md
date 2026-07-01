# PNB Sahayak — Demo Video Script (record-ready, ~3.5–4 min)

A **word-for-word** narration with exact click cues. Speak naturally; the bracketed **[DO]**
lines are what to click. Assignment needs **2+ Indian languages** — this shows English, **Hindi**,
and **Hinglish**. Full reference walkthrough: [demo-script.md](demo-script.md).

**Before you hit record:** app running at `http://127.0.0.1:8000`, mic allowed, and open tabs for
the assistant `/`, the **Dashboard** `/dashboard`, the **Live** page `/stream`, and your **n8n
Google Sheet**. Have the [question bank](question-bank.md) beside you.

---

### 0:00 — Intro (~20s)
> "This is **PNB Sahayak**, a multilingual, voice-first assistant for Punjab National Bank
> employees. It answers policy questions from the bank's **own approved documents**, in the
> employee's language, always shows the source, and never guesses. It's built entirely on the
> **Sarvam AI stack**, for the RFP's *Employee Productivity Assistant* use case."

**[DO]** Show the home page; point to *"Ready · 56 documents."*

### 0:20 — Voice Q&A in English (~40s)
**[DO]** Click the mic, ask: *"How often must pensioners submit a life certificate?"*
> "Sarvam's **Saaras** turns my speech to text and detects the language. It searches **56 real PNB
> documents**, and **Sarvam-30B** writes a short answer grounded only in what it found. **Bulbul**
> speaks it back."

**[DO]** Point to the panel: the **transcribed question**, the **spoken answer**, the **genuine
source document**, and the **High confidence** badge.

### 1:00 — Concise → Detailed (~20s)
**[DO]** On that answer, click **Detailed**.
> "Not enough detail? One click expands the *same* answer to the full policy — concise or detailed,
> per answer, on demand."

### 1:20 — Multilingual: Hindi + Hinglish (~40s)
**[DO]** Type (or speak) in Hindi: *"पेंशनभोगी को जीवन प्रमाण पत्र कब जमा करना होता है?"*
> "The same question in **Hindi** — and the answer comes back in Hindi, in Devanagari script."

**[DO]** Then ask in Hinglish: *"pension life certificate kab jama karna hai?"*
> "And in **Hinglish** — Sarvam's **Mayura** translation model bridges the language and the English
> documents, and locks the reply to the language I used. Text and voice stay consistent — no switching."

### 2:00 — Draft / summarise, grounded in policy (~35s)
**[DO]** Tap **✍️ Draft**, pick **🌐 Hindi**, type: *"summarise the life-certificate policy as key points."*
> "Beyond answering, it **prepares content** — summaries, notes, emails, replies — using only the
> approved documents, and in any language. Here, key points in Hindi."

**[DO]** Click **📋 Copy** (or **✉️ Email this draft**, enter an address, Send).
> "Employees can copy it, or email it — translated into any of eleven languages — to a customer or a colleague."

### 2:35 — It doesn't guess; it escalates (~35s)
**[DO]** Ask something not in the docs: *"What is the current gold loan interest rate?"*
> "A bank assistant must never invent policy. When the answer isn't in the documents, it says so
> honestly and **raises a follow-up ticket** instead of guessing."

**[DO]** Point to the **ticket number**, then switch to the **n8n** / **Google Sheet** tab — show the
new row appear.
> "That's the agentic part: an unanswered question becomes a tracked ticket for the policy team,
> automatically — event to action, no human in the loop."

### 3:10 — Governance dashboard (~25s)
**[DO]** Open **/dashboard**; click a recent row to expand it.
> "Everything is logged for governance — how many questions, in which languages, at what confidence,
> and which were escalated. Click any row to see the **full question and answer** — complete
> auditability, which a bank needs."

### 3:35 — Real-time streaming + close (~20s)
**[DO]** Open **/stream**, speak a sentence to show live captions.
> "The same listening, in real time. So: a multilingual, voice-first assistant that answers PNB
> staff from genuine documents, drafts their routine content, escalates when unsure, and gives the
> bank governance and oversight — all on the Sarvam stack. Thank you."

---

## Recording tips
- **Languages covered:** English + Hindi + Hinglish (satisfies the "2+ Indian languages" rule).
- Ask **direct, keyword-bearing** questions ("life certificate", not "life insurance").
- Text appears in ~2–3s; the voice follows — keep narrating while it speaks.
- Mic issues on the day? **Type** the question — same pipeline, same answer.
- Keep it under 5 minutes; 3.5–4 is ideal.
