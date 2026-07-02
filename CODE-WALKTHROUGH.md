# PNB Sahayak — Code Walkthrough

A plain-English, line-by-line guide to the code — written so a non-technical reader can both **understand it** and **explain it** in an interview.

> You don't need to memorise code. Understand the **story**: what each file is for, and what the few important lines do. Each section shows the real code, explains it in everyday language, and gives a sentence you can say out loud (in _italic quotes_). If someone opens the code and points at something, find that file here and read the explanation.

---

## The 60-second mental model (memorise THIS, not the code)

One question travels through the system like this:

1. **You speak** → **Saaras** turns your speech into text and detects the language.
2. We **translate** the question to English (our documents are in English).
3. We **search** the approved PNB documents and pull out the 2–3 best-matching passages.
4. We hand **only those passages** to the AI (**Sarvam-30B**) with strict rules: *answer only from this, and cite the source*.
5. We **translate the answer back** into your language, and **Bulbul** speaks it aloud.
6. If nothing relevant is found, it does **not guess** — it says so and logs a ticket for the policy team.

Five files do this, each with one job:

| File | Role | What it does |
|------|------|--------------|
| `src/sarvam_client.py` | **the toolbox** | Talks to Sarvam: ear, translator, brain, voice |
| `src/knowledge_base.py` | **the librarian** | Finds the right passages in the documents |
| `src/assistant.py` | **the brain** | Decides what to do; applies the safety rules |
| `src/app.py` | **the receptionist** | The web addresses the browser talks to |
| `src/web/index.html` | **the face** | The screen you see and click |

---

## File 1 — `sarvam_client.py` · "the toolbox"

A small toolbox with four tools, one per Sarvam ability. Nothing clever — it just makes the calls to Sarvam.

**Setup**
```python
API_KEY = os.getenv("SARVAM_API_KEY")   # the secret key, read from the private .env file
CHAT_MODEL = "sarvam-30b"               # Sarvam's fast model, recommended for voice
```
The key is read from a private `.env` file — it is **never** written in the code and never goes to GitHub. The model is fixed as Sarvam-30B, their fast model.
> _"Notice the API key is never in the code — it lives in a private .env file, so nothing secret is on GitHub."_

**Tool 1 — `listen()` (our EAR — Saaras speech-to-text)**
```python
r = requests.post(f"{BASE_URL}/speech-to-text", ..., data={"model": "saaras:v3"})
return {"transcript": ..., "language_code": ...}
```
Sends the recorded audio to Sarvam's Saaras model and gets back two things: the words that were said, and which language they were in — detected automatically, so the user never has to choose.
> _"This is our ear — Saaras turns speech into text and tells us the language, so we can reply in the same one."_

**Tool 2 — `translate()` (our TRANSLATOR — Mayura)**
```python
if is_mayura:
    if mode: body["mode"] = mode                   # e.g. "code-mixed" for Hinglish
    if output_script: body["output_script"] = ...  # e.g. "roman"
```
Converts text from one language to another. Those two lines are the **Hinglish trick**: we ask for *code-mixed* style in *roman* (English letters), which produces natural Hinglish instead of pure Hindi.
> _"This is our translator. The special 'code-mixed, roman' setting is how we produce real Hinglish, the way staff actually talk."_

**Tool 3 — `think()` (the BRAIN — Sarvam-30B writes the answer)**
```python
json={"model": CHAT_MODEL,
      "messages": [{"role": "system", "content": system_prompt},   # the RULES
                   {"role": "user",   "content": user_prompt}],     # context + question
      "temperature": 0.2,          # low = factual, not creative
      "reasoning_effort": None}    # no thinking pause = fast answer
```
Where the AI actually writes the answer. We give it a *system* message (the strict rules) and a *user* message (the retrieved passages + the question). Temperature `0.2` keeps it factual, not creative — for a bank we want the same reliable answer every time. `reasoning_effort=None` means it answers fast, with no thinking delay.
> _"This is the brain. We deliberately keep it factual, not creative — the temperature is low — and fast, because it's a voice assistant."_

**Tool 4 — `speak()` (our VOICE — Bulbul text-to-speech)**
```python
json={"text": text[:2500], "speaker": "shubh", "model": "bulbul:v3",
      "pace": 0.95, "enable_preprocessing": True, "speech_sample_rate": 16000}
```
Turns the answer text into spoken audio in the *shubh* voice. `enable_preprocessing` makes it read numbers, dates and money the natural way. The slightly slower `pace` (0.95) is clearer, and `16000` (16 kHz) keeps the audio small so it plays quickly.
> _"This is our voice — Bulbul. We turn on preprocessing so it reads dates and amounts naturally, and use a smaller audio size so it plays fast."_

---

## File 2 — `knowledge_base.py` · "the librarian"

Loads the documents, breaks them into small passages, and searches them by keyword.

```python
CHUNK_SIZE = 1000      # characters per passage (a few paragraphs)
CHUNK_OVERLAP = 150    # shared between neighbours so an answer is never cut in half
```
We can't search a whole 6-page PDF at once, so we cut each document into ~1000-character passages (a few paragraphs each). Neighbouring passages overlap by 150 characters so a sentence on the boundary still appears whole in one of them.
> _"We split each document into small passages of about a thousand characters, with a little overlap so nothing gets cut in half."_

```python
self._bm25 = BM25Okapi([_tokenize(c["text"]) for c in self.chunks])
```
This one line builds the search index over all **~1,683 passages**. BM25 is a classic keyword-search method — it ranks passages by how well their words match the question. It's fast, runs on the bank's own machine, and its scores are explainable.

```python
def search(self, query, k=5):
    scores = self._bm25.get_scores(_tokenize(query))
    ...  # return the top-k passages, each with a score + its real source PDF and URL
```
Returns the best-matching passages — and, crucially, each one remembers which genuine PDF it came from. That's how every answer can show its real source.
> _"It's keyword search over the passages, and every passage remembers its real source document — that's how we can always cite it."_

---

## File 3 — `assistant.py` · "the brain" (the most important file)

Decides what to do with a question. It contains the safety rules that make the assistant trustworthy for a bank.

**3a) The rulebook we hand the AI (`SYSTEM_PROMPT`)**
```text
"Answer the QUESTION using ONLY facts explicitly stated in the CONTEXT ...
 1. Never use outside or general knowledge...
 2. If the CONTEXT does not answer the QUESTION, reply with exactly NO_INFO ...
 ... write 'CITED: N' with the single Document number you used."
```
This short paragraph is the heart of "no hallucination". We literally instruct the AI: use only the passages we give you; if they don't answer, reply `NO_INFO`; and tell us which document you used.
> _"This is the anti-hallucination rulebook. We forbid outside knowledge, force it to say NO_INFO when unsure, and demand a source."_

**3b) Turning a search score into a confidence label**
```python
def _confidence(score):
    return "High" if score >= 12 else ("Medium" if score >= 6 else "Low")
```
The number from the search becomes a simple **High / Medium / Low** badge for the user — 12 and 6 are the thresholds we tuned.

**3c) How it decides the reply language (Hindi vs Hinglish)**
```python
has_devanagari = bool(re.search(r"[ऀ-ॿ]", transcript))   # is Hindi script present?
hinglish = any(... Hinglish marker words ...)             # words like kya, hai, kaise
```
If the text is in Hindi script it replies in Hindi; if it's Hindi-in-English-letters with Hinglish words, it replies in Hinglish; otherwise English. The whole reply is locked to one language so it never switches midway.
> _"It decides Hindi versus Hinglish by the script and a few marker words, and locks the whole reply to that one language."_

**3d) The main flow in `answer()` — with the TWO SAFETY GATES**
```python
hits = self.kb.search(query_en, k=6)          # 1. search the documents
top = hits[0] if hits else None

if not top or top["score"] < NOISE_SCORE:     # GATE 1: nothing matched well enough (score < 7)
    return ... off-topic       # -> polite decline, the AI is NEVER called

if present < 2:                               # GATE 2: the question's own words must
    return ... off-topic       #    actually appear in the best passage

raw = sc.think(SYSTEM_PROMPT, f"CONTEXT:\n{context}\n\nQUESTION: {query_en}")  # 2. ask the AI, grounded
m = re.search(r"CITED:\s*#?(\d+)", raw)       # 3. which document did it cite?

if ... answer is NO_INFO / empty ...:         # 4. it couldn't answer from the docs
    return ... escalate        # -> honest refusal + raise a ticket (n8n -> Google Sheet)
```
Read top to bottom, this is the entire safety story:

- It **searches** the documents for the best passages.
- **GATE 1** (score below 7): if nothing matches well, it's treated as off-topic and **the AI is never even called**.
- **GATE 2** (word overlap): the question's own words must appear in the best passage — this stops it answering from a document that only matched by coincidence.
- Only then does it **call the AI**, handing over *only* the retrieved passages plus the strict rulebook.
- It reads the `CITED: N` tag to know which real document to show as the source.
- If the AI says `NO_INFO` (or gives nothing), it does **not guess** — it gives an honest "I don't have that" and raises a ticket.

> _"Everything above the AI call is a filter. Two gates decide whether we even answer; the AI only ever sees approved passages and must cite one; and a miss becomes an honest refusal plus a ticket — never a guess."_

**3e) `draft()` — the drafting feature**
A near-twin of `answer()`, but for writing emails / notes / summaries. The difference: it always returns something (you asked it to write), any policy facts still come only from the retrieved passages, and a human reviews it before sending.

---

## File 4 — `app.py` · "the receptionist"

The web server. Each *route* is a web address the browser can call. It doesn't think — it just takes requests and hands them to the brain.

- `GET /` → serves the main screen (`index.html`)
- `POST /api/ask` → a voice question (audio in → answer out)
- `POST /api/ask_text` → a typed question
- `POST /api/speak` → turn answer text into audio (Bulbul)
- `POST /api/email` → email an answer / draft in the chosen language
- `GET /api/documents` & `/documents` → the Knowledge Base list of 56 sources
- `GET /dashboard` & `/api/stats` → the governance dashboard
- `GET /stream` & WebSocket `/ws/transcribe` → the live-captions streaming demo

**Example — the typed-question route**
```python
async def ask_text(question, language_code, detail, mode, draft_lang, answer_lang):
    if mode == "draft":
        result = bot.draft(question, draft_lang or language_code)
    else:
        result = bot.answer(question, language_code, detail=..., out_lang=answer_lang)
    return JSONResponse(_finalize(result, "text"))
```
It receives the question (and options like the chosen answer language), calls the brain's `answer()` or `draft()`, logs it, and sends the result back to the screen.
> _"The receptionist just routes: it takes your question, passes it to the brain, records it for the dashboard, and returns the answer."_

---

## File 5 — `web/index.html` · "the face"

The single web page you see. In plain terms it: shows the microphone and text box; when you ask, it records/reads your question and sends it to `/api/ask` or `/api/ask_text`; then it shows the answer, the source document, the confidence badge, and plays the audio. The language selector and the Answer/Draft toggle live here too.
> _"The face is just the screen — it sends your question to the server and shows back the answer, the source, and the voice."_

---

## If they point at the screen and ask "where does THAT happen?"

| Question | Where |
|----------|-------|
| "How does it understand my speech?" | `sarvam_client.py` → `listen()` (Saaras) |
| "How does it find the answer?" | `knowledge_base.py` → `search()` (BM25 keyword search) |
| "How do you stop it making things up?" | `assistant.py` → the `SYSTEM_PROMPT` + the two gates + `NO_INFO`/escalate |
| "How does it know the source?" | the `CITED: N` tag, parsed in `assistant.py`; each passage carries its PDF |
| "Why is it fast?" | `sarvam_client.py`: Sarvam-30B, temperature 0.2, `reasoning_effort=None`, 16 kHz audio |
| "How does it reply in my language?" | `decide_reply()` picks the language; `translate()` converts in and out |
| "What if it doesn't know?" | `assistant.py` escalate branch → `app.py` logs a ticket via n8n |

---

## The three sentences to always fall back on

1. **"It answers only from approved PNB documents — it searches them, hands the best passages to Sarvam-30B with strict rules, and shows the source."**
2. **"It never guesses — two checks decide whether to answer at all, and if it can't, it honestly refuses and raises a ticket."**
3. **"Everything runs on the Sarvam stack: Saaras listens, Mayura translates, Sarvam-30B reasons, Bulbul speaks, Vision reads scanned PDFs."**
