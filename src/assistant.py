"""
assistant.py  -  the "answer brain".

Order of checks (each returns early, so greetings/meta never hit the LLM):
  1. greeting / small talk        -> friendly reply, NO ticket
  2. "about you" / capability     -> overview, NO ticket
  3. no real words                -> polite off-topic, NO ticket
  4. translate to English, search the real PNB docs
  5. nothing relevant (low score) -> polite off-topic, NO ticket
  6. LLM answers ONLY from context; if it can't -> escalate (ticket), never guess
  7. real answer -> translate to the locked language + cite the genuine source

Every external call is wrapped so this NEVER crashes the request.
"""
import re
import time

from knowledge_base import KnowledgeBase
import sarvam_client as sc

POLITE_OFFTOPIC = ("I can only help with questions about PNB policies — please ask "
                   "about a policy, procedure, or circular.")
POLITE_ESCALATE = ("I couldn't find this in the PNB policy documents, so I've flagged "
                   "it for the policy team to follow up.")
GREETING_REPLY = ("Namaste! I'm PNB Sahayak, the assistant for PNB employees. Ask me about a "
                  "policy — for example pension life certificates, retiree medical insurance, "
                  "KYC and account opening, or customer rights.")
THANKS_REPLY = "You're welcome! Happy to help with any PNB policy question."
CAPABILITY_ANSWER = (
    "I'm PNB Sahayak, an assistant for Punjab National Bank employees. I answer questions from "
    "PNB's policy documents — for example: pension and life-certificate rules; medical insurance "
    "for retirees; the staff welfare fund; KYC and account opening; customer rights and grievance "
    "redressal; settling a deceased customer's account; service charges; and NRI/NRO accounts. "
    "Ask me about any of these.")

SYSTEM_PROMPT = (
    "You are PNB Sahayak, an assistant for Punjab National Bank employees. "
    "Answer the QUESTION using ONLY facts explicitly stated in the CONTEXT below, which is taken "
    "from official PNB documents. STRICT RULES:\n"
    "1. Never use outside or general knowledge. Even if you know the answer, if it is not in the "
    "CONTEXT you must not state it.\n"
    "2. If the CONTEXT does not explicitly and specifically answer the QUESTION, reply with "
    "exactly NO_INFO and nothing else. Do NOT write explanations like 'not specified'.\n"
    "3. Do not mention document numbers in your answer text.\n"
    "Otherwise reply in ENGLISH in 1 to 2 short sentences suitable for reading aloud, then on a "
    "final separate line write 'CITED: N' with the single Document number you used.")

DETAIL_SYSTEM_PROMPT = (
    "You are PNB Sahayak, an assistant for Punjab National Bank employees. "
    "Answer the QUESTION using ONLY facts explicitly stated in the CONTEXT below, which is taken "
    "from official PNB documents. STRICT RULES:\n"
    "1. Never use outside or general knowledge; if it is not in the CONTEXT, do not state it.\n"
    "2. If the CONTEXT does not answer the QUESTION, reply with exactly NO_INFO and nothing else.\n"
    "3. Do not mention document numbers in your answer text.\n"
    "Otherwise give a THOROUGH answer in ENGLISH — up to 5-6 sentences or a few short bullet "
    "points — covering all the relevant details, conditions, figures and steps in the CONTEXT. "
    "Then on a final separate line write 'CITED: N' with the single Document number you used.")

DRAFT_SYSTEM_PROMPT = (
    "You are PNB Sahayak, helping a Punjab National Bank employee PREPARE the exact content they "
    "asked for, based on the CONTEXT below (from official PNB documents). "
    "First understand what the employee wants — it might be an email or reply, a note or notes, a "
    "summary, key points / bullet points, or a short report — then produce ONE piece of content in "
    "the most fitting format: a bulleted list when they ask for points or notes, flowing prose when "
    "they ask for a summary, and a courteous message (with a 'Subject:' line ONLY for an email) when "
    "they ask for an email or reply. "
    "Do NOT print the format name (like 'summary' or 'bullet points') as a heading, and do NOT "
    "produce more than one version. "
    "Use ONLY facts stated in the CONTEXT for policy details; never invent policy specifics, figures "
    "or dates. If the CONTEXT is not relevant, still produce the requested content but keep policy "
    "claims general. Write in ENGLISH, clear and professional. Output ONLY the content itself — no "
    "preamble and no commentary. If you used a document for facts, add a final separate line "
    "'CITED: N' with the single Document number you used.")

DRAFT_EMPTY = ("Tell me what you'd like me to prepare — for example, 'summarise the life-certificate "
               "policy as key points', 'make notes on retiree medical insurance', or 'draft an email "
               "to a customer about account opening'.")
DRAFT_FAIL = "Sorry, I couldn't prepare that draft just now. Please try rephrasing your request."

NOISE_SCORE = 7.0     # below this the query barely matches anything -> treat as off-topic
STOPWORDS = {
    "the", "and", "for", "are", "was", "what", "when", "how", "why", "who", "which",
    "does", "did", "can", "will", "would", "should", "you", "your", "our", "their",
    "this", "that", "these", "those", "with", "about", "from", "into", "tell", "give",
    "need", "want", "please", "there", "here", "have", "has", "had", "any", "get", "all",
}
# Phrases the LLM emits when it can't actually answer -> treat as "not found".
NOT_FOUND_PHRASES = [
    "no_info", "not specified", "not mentioned", "no information", "not provided",
    "does not contain", "not available in", "not found in", "cannot find", "can't find",
    "not in the context", "not in the provided", "no details", "context does not",
    "i am not provided", "unable to find", "no relevant information",
    "does not specify", "do not specify", "isn't specified",
    "cannot be determined", "unable to determine",
]
_HINGLISH_WORDS = {"kab", "hai", "kya", "kaise", "kyun", "kyon", "nahi", "mujhe", "batao",
                   "chahiye", "kitna", "kitni", "karna", "krna", "mera", "meri", "hota",
                   "hoti", "jama", "milega", "kaun", "konsa", "kitne", "sakta", "sakti"}

_CAPABILITY_PATTERNS = [
    "what can you help", "what all can you", "what do you do", "what can you do",
    "what are you able", "what policies can you", "which policies can you",
    "what all policies", "what topics", "what areas", "what questions can",
    "what can i ask", "what kind of questions", "list of policies", "list the policies",
    "what information can you", "how can you help", "what do you know", "what are you",
    "who are you", "your name", "are you a", "are you an", "are you human", "are you real",
    "documents do you have", "documents you have", "how many documents",
    "what data do you have", "files do you have", "documents do you contain",
    "documents are in your", "your knowledge base", "documents are you trained",
]
_GREETING_WORDS = {"hi", "hii", "hey", "heyy", "hiya", "hello", "helo", "namaste",
                   "namaskar", "yo", "hola", "greetings"}
_GREETING_PHRASES = ["good morning", "good afternoon", "good evening", "good night",
                     "how are you", "whats up", "what's up", "nice to meet"]
_THANKS = {"thanks", "thank", "thankyou", "thx", "ty", "appreciate"}
_FAREWELL = ["bye", "goodbye", "good bye", "see you", "cya", "take care"]

LANG_NAMES = {
    "hi": "Hindi", "en": "English", "bn": "Bengali", "gu": "Gujarati", "kn": "Kannada",
    "ml": "Malayalam", "mr": "Marathi", "od": "Odia", "pa": "Punjabi", "ta": "Tamil",
    "te": "Telugu", "as": "Assamese", "ur": "Urdu", "ne": "Nepali", "sa": "Sanskrit",
    "kok": "Konkani", "mai": "Maithili", "doi": "Dogri", "ks": "Kashmiri", "sd": "Sindhi",
    "mni": "Manipuri", "sat": "Santali", "brx": "Bodo",
}
VOICE_LANGS = {"bn-IN", "en-IN", "gu-IN", "hi-IN", "kn-IN", "ml-IN", "mr-IN",
               "od-IN", "pa-IN", "ta-IN", "te-IN"}


def _tokenize(text):
    return re.findall(r"[a-z0-9]+", text.lower())


def _content_terms(text):
    # meaningful words: >=3 chars, not a stopword, and containing a letter (drops "12345")
    return [t for t in _tokenize(text)
            if len(t) >= 3 and t not in STOPWORDS and re.search(r"[a-z]", t)]


def _confidence(score):
    return "High" if score >= 12 else ("Medium" if score >= 6 else "Low")


def _strip_tags(text):
    """Remove the model's citation markers — 'CITED: 4', 'CITED: 4, 6', '[Document 4]',
    '(Doc 2)' — wherever they appear, and tidy up the leftover whitespace."""
    if not text:
        return ""
    text = re.sub(r"(?i)\bCITED\b\s*:?\s*#?\d+(?:\s*,\s*#?\d+)*", "", text)
    text = re.sub(r"(?i)[\[(]\s*doc(?:ument)?s?\.?\s*#?\d+\s*[\])]", "", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _is_capability(text):
    t = text.lower()
    return any(p in t for p in _CAPABILITY_PATTERNS)


def _is_notfound(text):
    t = (text or "").lower()
    return any(p in t for p in NOT_FOUND_PHRASES)


def greeting_reply(text):
    """Return a friendly reply if this is a greeting/thanks/farewell, else None."""
    t = re.sub(r"[^a-z\s']", " ", (text or "").lower())
    t = re.sub(r"\s+", " ", t).strip()
    if not t:
        return None
    words = t.split()
    if len(words) > 5:      # too long to be a pure greeting
        return None
    if any(w in _THANKS for w in words):
        return THANKS_REPLY
    if words[0] in _GREETING_WORDS:
        return GREETING_REPLY
    if any(t == p or t.startswith(p + " ") or t == p.replace("'", "") for p in _GREETING_PHRASES):
        return GREETING_REPLY
    if any(t == p or t.startswith(p + " ") for p in _FAREWELL):
        return GREETING_REPLY
    return None


def decide_reply(transcript, language_code, force_native=False):
    """Pick ONE language + style for the whole reply (so it never switches mid-answer).
    force_native=True (used when the user EXPLICITLY picks a language, e.g. the Draft
    language selector) always uses that language's own script — never romanised Hinglish."""
    base = (language_code or "en-IN").split("-")[0].lower()
    name = LANG_NAMES.get(base, language_code)
    has_devanagari = bool(re.search(r"[ऀ-ॿ]", transcript or ""))
    lower = (transcript or "").lower()
    hinglish = any(re.search(rf"\b{w}\b", lower) for w in _HINGLISH_WORDS)

    if base == "en" and (not hinglish or force_native):
        return dict(is_english=True, style_label="English", voice_lang="en-IN",
                    trans_model="mayura:v1", in_source="auto", out_target="en-IN",
                    mode=None, output_script=None)
    if base == "hi" or (base == "en" and hinglish):
        if has_devanagari or force_native:
            return dict(is_english=False, style_label="Hindi", voice_lang="hi-IN",
                        trans_model="mayura:v1", in_source="auto", out_target="hi-IN",
                        mode="modern-colloquial", output_script="fully-native")
        return dict(is_english=False, style_label="Hinglish", voice_lang="hi-IN",
                    trans_model="mayura:v1", in_source="auto", out_target="hi-IN",
                    mode="code-mixed", output_script="roman")
    if language_code in VOICE_LANGS:
        return dict(is_english=False, style_label=name, voice_lang=language_code,
                    trans_model="mayura:v1", in_source="auto", out_target=language_code,
                    mode="modern-colloquial", output_script="fully-native")
    return dict(is_english=False, style_label=name, voice_lang=None,
                trans_model="sarvam-translate:v1", in_source=language_code,
                out_target=language_code, mode=None, output_script=None)


class Assistant:
    def __init__(self):
        self.kb = KnowledgeBase()

    def _reply(self, transcript, language_code, plan, timings, answer_en,
               source=None, confidence="Low", score=0.0, escalate=False, kind="answer"):
        # Translate any non-English reply into the user's language — including short
        # decline/escalate/greeting replies — so the assistant never switches to English.
        if not plan["is_english"]:
            try:
                answer = sc.translate(answer_en, plan["out_target"], source_language_code="en-IN",
                                      model=plan["trans_model"], mode=plan["mode"],
                                      output_script=plan["output_script"])
            except Exception:
                answer = answer_en
        else:
            answer = answer_en
        if kind in ("greeting", "capability", "offtopic"):
            confidence = "—"   # not a graded answer -> no confidence pill on the dashboard
        return {
            "transcript": transcript, "language_code": language_code,
            "style_label": plan["style_label"], "query_en": "",
            "answer": answer, "answer_en": answer_en,
            "source": source, "confidence": confidence, "score": score,
            "escalate": escalate, "kind": kind,
            "tts_lang": (plan["voice_lang"] if kind in ("answer", "draft") else "en-IN"),
            "timings": timings,
        }

    def answer(self, question, language_code="en-IN", k=6, detail=False):
        timings = {}
        plan = decide_reply(question, language_code)

        # 1. Greeting / small talk (no ticket, no LLM)
        g = greeting_reply(question)
        if g:
            return self._reply(question, language_code, plan, timings, g, kind="greeting")

        # 2. "About you" / capability (no ticket, no LLM)
        if _is_capability(question):
            return self._reply(question, language_code, plan, timings, CAPABILITY_ANSWER,
                                confidence="—", kind="capability")

        # Translate the question to English for searching.
        try:
            if plan["is_english"]:
                query_en = question
            else:
                t = time.time()
                query_en = sc.translate(question, "en-IN", source_language_code=plan["in_source"],
                                        model=plan["trans_model"])
                timings["translate_in_ms"] = int((time.time() - t) * 1000)
        except Exception:
            return self._reply(question, language_code, plan, timings, POLITE_OFFTOPIC, kind="offtopic")

        if not plan["is_english"]:   # re-check meta on the translated text
            g = greeting_reply(query_en)
            if g:
                return self._reply(question, language_code, plan, timings, g, kind="greeting")
            if _is_capability(query_en):
                return self._reply(question, language_code, plan, timings, CAPABILITY_ANSWER,
                                    confidence="—", kind="capability")

        # 3. No real words -> polite off-topic.
        if not _content_terms(query_en):
            return self._reply(question, language_code, plan, timings, POLITE_OFFTOPIC, kind="offtopic")

        # 4. Search the real documents.
        t = time.time()
        hits = self.kb.search(query_en, k=k)
        timings["search_ms"] = int((time.time() - t) * 1000)
        top = hits[0] if hits else None

        # 5. Nothing relevant -> off-topic (no ticket, no LLM).
        if not top or top["score"] < NOISE_SCORE:
            return self._reply(question, language_code, plan, timings, POLITE_OFFTOPIC,
                                score=(top["score"] if top else 0.0), kind="offtopic")

        # 5b. Relevance guard: the question's own words must actually appear in the best
        # passage, otherwise we'd be answering from an unrelated document (e.g. "who is the
        # PM of India?" matching a medical doc on the word "India") -> decline, don't guess.
        content = set(_content_terms(query_en))
        present = len(content & set(_tokenize(top["text"])))
        if present < (2 if len(content) >= 3 else 1):
            return self._reply(question, language_code, plan, timings, POLITE_OFFTOPIC,
                                score=top["score"], kind="offtopic")

        # 6. Ask the LLM, strictly grounded.
        context = "\n\n".join(
            f"[Document {i + 1}: {h['label'] or h['pdf']}]\n{h['text']}"
            for i, h in enumerate(hits)
        )
        try:
            t = time.time()
            raw = sc.think(DETAIL_SYSTEM_PROMPT if detail else SYSTEM_PROMPT,
                           f"CONTEXT:\n{context}\n\nQUESTION: {query_en}",
                           max_tokens=(450 if detail else 180))
            timings["llm_ms"] = int((time.time() - t) * 1000)
        except Exception:
            return self._reply(question, language_code, plan, timings, POLITE_OFFTOPIC,
                                score=top["score"], kind="offtopic")

        # 7. Strip the citation/document tags, then decide if the model really answered.
        m = re.search(r"CITED:\s*#?(\d+)", raw, re.IGNORECASE)
        cited_idx = (int(m.group(1)) - 1) if m else None
        answer_en = _strip_tags(raw)

        # Couldn't answer from the documents -> escalate (genuine gap), never guess. A real
        # refusal is short; a long answer that merely hedges one clause is still an answer.
        up = answer_en.upper()
        if ((not raw) or len(answer_en) < 3 or up == "NO_INFO" or up.startswith("NO_INFO")
                or (len(answer_en) <= 160 and _is_notfound(answer_en))):
            return self._reply(question, language_code, plan, timings, POLITE_ESCALATE,
                                score=top["score"], escalate=True, kind="escalate")
        cited = hits[cited_idx] if (cited_idx is not None and 0 <= cited_idx < len(hits)) else top

        r = self._reply(question, language_code, plan, timings, answer_en,
                        source={"pdf": cited["pdf"], "label": cited["label"], "url": cited["url"]},
                        confidence=_confidence(cited["score"]), score=cited["score"], kind="answer")
        r["query_en"] = query_en
        return r

    def draft(self, request, language_code="en-IN", k=6):
        """Draft routine content (email / note / reply) grounded in the PNB documents.
        Unlike answer(), a draft always produces something — it never escalates — but any
        policy facts it uses come only from the retrieved passages, and it cites the source."""
        timings = {}
        plan = decide_reply(request, language_code, force_native=True)

        # Translate the request to English for searching + drafting.
        try:
            if plan["is_english"]:
                query_en = request
            else:
                t = time.time()
                query_en = sc.translate(request, "en-IN", source_language_code=plan["in_source"],
                                        model=plan["trans_model"])
                timings["translate_in_ms"] = int((time.time() - t) * 1000)
        except Exception:
            return self._reply(request, language_code, plan, timings, DRAFT_EMPTY, kind="offtopic")

        if not _content_terms(query_en):
            return self._reply(request, language_code, plan, timings, DRAFT_EMPTY, kind="offtopic")

        # Pull any relevant policy so the draft can be grounded (best-effort — a draft
        # like "an email thanking a customer" may legitimately need no policy at all).
        t = time.time()
        hits = self.kb.search(query_en, k=k)
        timings["search_ms"] = int((time.time() - t) * 1000)
        top = hits[0] if hits else None

        relevant = []
        if top and top["score"] >= NOISE_SCORE:
            content = set(_content_terms(query_en))
            need = 2 if len(content) >= 3 else 1
            relevant = [h for h in hits
                        if len(content & set(_tokenize(h["text"]))) >= need]

        context = "\n\n".join(
            f"[Document {i + 1}: {h['label'] or h['pdf']}]\n{h['text']}"
            for i, h in enumerate(relevant)
        ) or "(no specific policy context found — draft professionally without inventing policy facts)"

        try:
            t = time.time()
            raw = sc.think(DRAFT_SYSTEM_PROMPT,
                           f"CONTEXT:\n{context}\n\nDRAFTING REQUEST: {query_en}",
                           max_tokens=550)
            timings["llm_ms"] = int((time.time() - t) * 1000)
        except Exception:
            return self._reply(request, language_code, plan, timings, DRAFT_FAIL, kind="offtopic")

        if not raw or len(raw.strip()) < 3:
            return self._reply(request, language_code, plan, timings, DRAFT_FAIL, kind="offtopic")

        # Strip citation/document tags; map to the genuine source if the model used one.
        m = re.search(r"CITED:\s*#?(\d+)", raw, re.IGNORECASE)
        cited_idx = (int(m.group(1)) - 1) if m else None
        draft_en = _strip_tags(raw)
        if len(draft_en) < 3:   # nothing usable left -> don't show a blank draft
            return self._reply(request, language_code, plan, timings, DRAFT_FAIL, kind="offtopic")

        source, score = None, (top["score"] if top else 0.0)
        if relevant:
            c = relevant[cited_idx] if (cited_idx is not None and 0 <= cited_idx < len(relevant)) else relevant[0]
            source = {"pdf": c["pdf"], "label": c["label"], "url": c["url"]}
            score = c["score"]

        r = self._reply(request, language_code, plan, timings, draft_en,
                        source=source, confidence="—", score=score, kind="draft")
        r["query_en"] = query_en
        return r


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    bot = Assistant()
    for q in ["hi", "thanks", "who are you?", "what can you do?",
              "How often must pensioners submit a life certificate?",
              "who is the prime minister of india?", "what is the home loan interest rate?"]:
        r = bot.answer(q, "en-IN")
        print(f"{q[:40]:40} -> {r['kind']:10} esc={r['escalate']} src={(r['source'] or {}).get('pdf')}")
        print(f"    {r['answer'][:90]}")
