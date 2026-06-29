# Build Brief — PNB Employee Voice Assistant
### A project specification for Claude Code

> Hand this whole file to Claude Code at the start. It tells you what to build, in what order, and — important — *how to teach me as you go*, because I am not a coder and I have to explain this project on a demo video afterwards.

---

## 0. HOW TO WORK WITH ME (read this first — these rules apply to every step)

1. **I am non-technical.** Explain everything in plain language. The moment you use a technical term, define it in one simple sentence with an example.
2. **One step at a time.** Do a small piece, then stop and tell me: (a) what we just did, (b) why we did it, (c) how to check it worked, (d) what's next. Wait for me to say "ok" before moving on.
3. **Never break a working version.** Build in the phases below. At the end of each phase, save the progress with git and tell me clearly: "We now have a working checkpoint — here's what works." If something later breaks, we can always return here.
4. **Always give me copy-paste instructions.** Whenever I need to do something — install something, create an account, paste a key, run a command — give me the exact thing to type or click, and tell me what I should see when it works.
5. **Verify Sarvam details from the live docs, not from memory.** For every Sarvam API (exact web address/endpoint, parameters, model names, audio formats), read the current documentation at `https://docs.sarvam.ai` and `https://www.sarvam.ai/integrations` before writing code. Product details change. The assignment names the models as **Saaras** (speech-to-text), **Bulbul** (text-to-speech), **sarvam-105b** (the LLM, via Chat Completions), and **Translate** — confirm the exact current names and endpoints from the docs/dashboard, as they may differ.
6. **Keep my API key safe.** Put it in a file called `.env`, never inside the code, and make sure `.env` is never saved to git. Never print the key to the screen.
7. **Prepare me to present.** At the end of every phase, give me 2–3 plain-English sentences I could say on a demo video to describe that part. At the very end, give me a full narrated walkthrough script for a 3–5 minute video.
8. **Keep it simple.** Always choose the simplest approach that works and that I can understand and explain. Do not add complexity for its own sake.

---

## 1. WHAT WE ARE BUILDING (the use case)

A **multilingual voice assistant for Punjab National Bank (PNB) employees.** A branch or back-office staff member asks a question out loud — in Hindi, English, or a mix (Hinglish) — about the bank's internal policies, procedures, or circulars. The assistant:

- understands the spoken question,
- finds the answer in a set of the bank's own policy documents,
- speaks the answer back in the language the person used, and
- shows the exact source document it used.

If it cannot find a confident answer, it does **not** guess — it logs the question and raises a follow-up ticket for the policy team.

**Why this exists:** PNB staff currently lose time digging through policy PDFs or phoning head office. This gives them instant, reliable, source-backed answers in their own language. (This is one use case taken from a real, public PNB Generative-AI tender; the other use cases are explained separately in slides, not built here.)

---

## 2. THE SARVAM STACK WE ARE USING

Confirm exact endpoints and model strings from the live docs (rule 5 above), then use all of:

- **Saaras** — speech-to-text (turns the spoken question into text).
- **sarvam-105b** — the LLM (reads the found document and writes the answer).
- **Bulbul** — text-to-speech (speaks the answer back).
- **Translate** — for the cross-language step (question in Hinglish, document in English, answer in Hindi).
- **Real-time streaming** (LiveKit + Sarvam, or Pipecat + Sarvam) — used only for the optional streaming demo in Phase 7.
- **Call Analytics** (Sarvam's Call Analytics cookbook) — used for the post-call analytics in Phase 6.

---

## 3. THE PIECES (architecture, in plain terms)

- **The app** — a small program written in **Python** with **FastAPI** (a helper that handles the web/server plumbing). It runs the voice pipeline: microphone → Saaras → find answer in documents → sarvam-105b → Bulbul → play answer.
- **A simple web page** — a microphone button, and an on-screen panel that shows, live: the transcribed question, the source document it found, the confidence, and then the spoken answer. (This "show the work" panel is what makes the demo look sophisticated.)
- **The document search (RAG)** — a small set of sample PNB-style policy documents the assistant searches to answer from. Keep retrieval simple given the small number of documents.
- **The agentic workflow (n8n)** — a separate visual workflow that fires when the assistant is stuck: it logs the question (and the source/confidence) and creates a follow-up ticket. n8n is visual/no-code so I can show it on screen.
- **A small dashboard** — shows questions asked, languages used, confidence levels, and the unanswered ones that became escalations.
- **Post-call analytics** — an offline step that takes a recorded conversation and produces a transcript, who-said-what, and an LLM summary of topics and sentiment.
- **The streaming demo** — a separate, minimal real-time pipeline shown alongside the main app (does not replace it).

---

## 4. BUILD IT IN THESE PHASES (in order — core first, safe first)

After each phase: test it, explain it to me, give me my demo lines, and save a git checkpoint.

**Phase 1 — Setup & a "hello Sarvam" test.** Set up the project folder, the `.env` file for my key, and dependencies. Then prove the key works: send a short audio clip and get text back (Saaras), and send a line of text and get audio back (Bulbul). Goal: confirm we can talk to Sarvam.

**Phase 2 — The core voice Q&A (turn-by-turn).** Build the web page with a mic button and the "show the work" panel. Wire the full loop: I speak → Saaras → find the right policy document → sarvam-105b writes the answer → Bulbul speaks it. Make it work in Hindi and English, and handle Hinglish. Use Translate so a question in one language can be answered from an English document in the user's language. Goal: a working multilingual voice answer with the source shown on screen.

**Phase 3 — Grounding, citations & "I don't know."** Make the assistant answer *only* from the documents, always show the exact source, and, when it isn't confident, say so and prepare to escalate instead of guessing. Goal: it never makes things up.

**Phase 4 — The agentic escalation (n8n).** When the assistant can't answer, it triggers an n8n workflow that logs the question + source + confidence (to a Google Sheet, or a local file if I prefer) and creates a follow-up ticket. Goal: one complete event → reason → tool → downstream sequence I can demonstrate (mock data is fine).

**Phase 5 — The dashboard.** A simple screen showing questions asked, languages, confidence, and unanswered → escalations. Goal: it looks like a real product and matches what a bank would want for governance.

**Phase 6 — Post-call analytics (offline).** Take a recorded conversation and produce a transcript, who-said-what (diarisation), and an LLM summary, following Sarvam's Call Analytics cookbook. Goal: an "insights" layer. Low risk — it runs offline and cannot break the live demo.

**Phase 7 — Real-time streaming demo (last, optional, riskiest).** A small, separate live pipeline using LiveKit + Sarvam or Pipecat + Sarvam, shown as "the same experience, running in real time." Because the main app does not depend on this, a glitch here must not affect anything else. If it stays unreliable, we keep it as "shown, not bulletproof."

**Phase 8 — Repo polish & handover.** Organise the repository as `README.md` + `/src` + `/docs`. Include `requirements.txt` (or `package.json`), a `.env.example` (with placeholder, no real key), the architecture diagram, and a clear README (setup steps, architecture overview, which Sarvam APIs are used and why). Finally, write me the 3–5 minute demo narration script and a one-line description of each Sarvam API used.

---

## 5. SAMPLE DATA TO CREATE

- Generate a handful of **realistic but fictional** PNB-style policy documents for the assistant to answer from (clearly marked as mock/sample) — for example: cash-deposit limits and PAN rules, KYC norms, account-opening checklist, employee leave policy. Keep them short.
- Prepare a few sample questions in Hindi, English, and Hinglish to use while testing and demoing.

---

## 6. WHAT I (THE USER) WILL PROVIDE

- My **Sarvam API key** (I'll paste it into `.env` when you ask).
- Approval and sign-in for any accounts needed (n8n, optionally Google, optionally LiveKit) — guide me through each.
- Running commands when you give them to me.

---

## 7. NON-NEGOTIABLES

- Never put the API key in the code or in git; never print it.
- Keep a working version saved at every checkpoint.
- If Phase 7 (streaming) becomes flaky, keep it separate — do not let it break the core.
- Explain every step in plain language and give me demo lines, as in Section 0.

---

## 8. DEFINITION OF DONE

- A working, multilingual, turn-by-turn voice assistant that answers PNB policy questions from documents, shows its source, and escalates when unsure.
- The n8n escalation, the dashboard, and the offline post-call analytics all working.
- A streaming demo shown alongside (even if minimal).
- A clean repo (README, /src, /docs, architecture diagram) and a demo narration script.
- And me — able to explain, in plain words, what every part does and why.
