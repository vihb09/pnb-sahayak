# PNB Sahayak — Interview Q&A Cheat-Sheet

Crisp, honest answers to the questions a Sarvam interviewer (pre-sales lens) is likely to ask.
Speak to **business value first**, then the technical "how".

---

## The pitch (30 seconds)
> "PNB Sahayak is a multilingual, voice-first assistant for bank employees. They ask about internal
> policies — pension, medical insurance, KYC, customer rights — by voice or text, in Hindi, English,
> Hinglish or 8 more languages. It answers **only from the bank's approved documents**, shows the
> source, drafts routine content like emails and summaries, and when it isn't sure it escalates
> instead of guessing. It's built end-to-end on the Sarvam stack, for the RFP's Employee
> Productivity Assistant use case."

---

## Product / business

**Q. Which use case is this and why?**
The RFP's **Use Case #7 — Employee Productivity Assistant**. It's real (PNB's public GenAI RFP,
02.03.2026), high-volume, and India-specific: ~100k staff across 10,000+ branches who lose time
hunting through circulars. It shows Sarvam's India-language edge directly.

**Q. Who's the end user and what's the pain?**
Branch/ops/field employees, mixed digital literacy, working in many languages. Today they search
PDFs and circulars or ask colleagues — slow and inconsistent. Voice + native language removes that
friction.

**Q. What's the ROI story?**
Illustrative: ~40k frontline staff × ~3 lookups/day × 250 days ≈ **30M queries/yr**. Automating ~70%
at a few ₹ each vs. ~₹80–100 of staff time per manual lookup saves **millions of staff-hours/yr**.
State it as assumptions, not a promise — the point is the *order of magnitude*.

**Q. Why not just ChatGPT / a generic LLM?**
Three reasons a bank cares about: (1) **Indian languages + code-mixing** (Hinglish/Tanglish) done
natively; (2) **data sovereignty** — Sarvam can run **on-prem**, so no document data leaves the
bank, which is what the RFP demands; (3) **grounding + governance** — answers only from approved
docs, cited, audited. A generic model gives none of these out of the box.

---

## Why Sarvam specifically
- **Saaras** — speech-to-text across 22 Indian languages, with auto language detection.
- **Bulbul** — natural text-to-speech in 11 languages (30+ voices).
- **Mayura / Translate** — the differentiator: **code-mixed** output (real Hinglish in Roman script),
  not just literal translation.
- **Sarvam-30B** — the LLM; I chose the **30B over the 105B** deliberately for **low latency** in a
  voice loop (Sarvam recommends 30B for voice).
- **Sarvam Vision** — OCR'd the 2 scanned circulars that had no text layer.
- **On-prem / sovereign deployment** — the compliance clincher for BFSI.

---

## Architecture (60 seconds)
> "Speak → **Saaras** transcribes and detects language → if needed **Mayura** translates the question
> to English → a **BM25 search** over the 56 real PNB documents → a **relevance gate**: if nothing
> clears the threshold it escalates and never reaches the model → otherwise **Sarvam-30B** writes an
> answer grounded only in the retrieved passages and names the source → **Mayura** translates it back
> into the user's language → **Bulbul** speaks it. Every turn is logged; unanswered ones become **n8n**
> tickets. It's both a voice bot and an agentic workflow."

Diagrams: [architecture.md](architecture.md) — 6 views (context, components, sequence+latency, RAG,
agentic escalation, deployment).

**Q. How do you prevent hallucination? (they WILL ask)**
Two hard controls: generation is **retrieval-gated** (no relevant passage → the model is never
called) and **citation-enforced** (it must answer only from the injected passages and name the
document). Plus a relevance guard (the query's own words must appear in the top passage) and a
"couldn't answer → escalate" net. That's why it declines "who's the PM of India" and raises a ticket
for a real-but-missing policy instead of inventing one.

**Q. How does multilingual stay consistent?**
Detect the language **once**, answer internally in English against the English docs, then do **one**
Mayura translation that locks the reply's language and script. No mid-answer switching.

**Q. What's the "agentic" part?**
The escalation workflow: an unanswered question is an **event** → the app builds a structured ticket
→ POSTs to an **n8n** webhook → n8n appends a row to a Google Sheet for the policy team. Event →
reason → tool call → downstream system updated, no human in the loop.

**Q. Latency?**
Text answer in ~2–3s, voice follows (~4–6s end-to-end). Levers: skip translate when it's English,
skip the LLM entirely on a gate-fail, cap answer length, reasoning off, and a cache for common
questions.

---

## Scope / honesty

**Q. What's a PoC shortcut vs. production?**
| Area | PoC (built) | Production |
|---|---|---|
| Retrieval | BM25 over ~1,683 passages | Hybrid: BM25 + embeddings + reranker on a vector store |
| Knowledge | 56 real PNB PDFs (local) | Bank **DMS** feed + scheduled re-ingestion |
| Escalation | n8n → Google Sheet | n8n → bank **ITSM** |
| Hosting | Sarvam hosted API | Sarvam **on-prem / sovereign** |
| Access | open/local | **SSO / IAM**, role-based |

**Q. What would a 90-day rollout look like?**
Pilot cohort → connect the DMS + SSO → hybrid retrieval + on-prem models → feedback loop (thumbs
up/down → content fixes) → expand once the output-quality KPIs (grounding, correctness, escalation
rate) clear the bar.

**Q. Limitations?**
Keyword retrieval can miss paraphrases (fixed by hybrid retrieval); TTS is hosted for the PoC;
telephony isn't wired yet; the KB is a fixed snapshot. All are known and roadmapped, not hidden.

**Q. Compliance?**
Maps to **DPDP** (consent, data minimisation, access control) and **RBI FREE-AI** (fairness,
accountability, transparency, explainability), with **on-prem residency** and an immutable audit log
of every question, source and answer.

---

## If asked to prove a claim, demo it
- *"It won't hallucinate"* → ask "who is the PM of India?" → it declines.
- *"It's grounded"* → any policy question → point to the real source PDF + confidence.
- *"It's multilingual"* → same question in Hindi and Hinglish.
- *"It's auditable"* → dashboard → expand a row → full question + answer.
- *"It's agentic"* → ask an unknown policy → ticket appears in the Google Sheet.
