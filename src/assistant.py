"""
assistant.py  -  the "answer brain".

  question + detected language
    -> decide ONE reply language/style (locked for the whole answer)
    -> greeting/off-topic       -> polite, NO LLM, NO ticket
    -> "what can you help with?" -> a friendly list of the topics it covers
    -> translate to English (if needed), search the real PNB docs
    -> genuine question, no match -> escalate (ticket) instead of guessing
    -> LLM answers in ENGLISH, grounded, 1-2 sentences, names the doc it used
    -> translate the ONE final answer into the locked language/style
    -> return answer + genuine source + confidence + timings + flags

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
# Friendly overview of what the knowledge base actually covers.
CAPABILITY_ANSWER = (
    "I answer questions from PNB's policy documents. I can help with topics like: "
    "pension and life-certificate rules; medical insurance for retirees; the staff welfare fund; "
    "KYC and account opening; customer rights and grievance redressal; settling a deceased "
    "customer's account; service charges; and NRI/NRO accounts. Ask me about any of these."
)

SYSTEM_PROMPT = (
    "You are PNB Sahayak, an assistant for Punjab National Bank employees. "
    "Answer the QUESTION using ONLY the facts in the CONTEXT, which is taken from official "
    "PNB documents. Never use outside knowledge and never guess. "
    "Reply in ENGLISH, in 1 to 2 short sentences suitable for reading aloud. "
    "Then, on a final separate line, write 'CITED: N' with the single Document number you used. "
    "If the CONTEXT does not contain the answer, reply with exactly NO_INFO and nothing else."
)

MIN_SCORE = 4.0
STOPWORDS = {
    "the", "and", "for", "are", "was", "what", "when", "how", "why", "who", "which",
    "does", "did", "can", "will", "would", "should", "you", "your", "our", "their",
    "this", "that", "these", "those", "with", "about", "from", "into", "tell", "give",
    "need", "want", "please", "there", "here", "have", "has", "had", "any", "get",
}
_HINGLISH_WORDS = {"kab", "hai", "kya", "kaise", "kyun", "kyon", "nahi", "mujhe", "batao",
                   "chahiye", "kitna", "kitni", "karna", "krna", "mera", "meri", "hota",
                   "hoti", "jama", "milega", "kaun", "konsa", "kitne", "sakta", "sakti"}

# Phrases that mean "what can this assistant do?" (checked on the English version).
_CAPABILITY_PATTERNS = [
    "what can you help", "what all can you", "what do you do", "what can you do",
    "what are you able", "what policies can you", "which policies can you",
    "what all policies", "what topics", "what areas", "what questions can",
    "what can i ask", "what kind of questions", "list of policies", "list the policies",
    "what information can you", "how can you help", "what do you know", "what are you",
]

# Languages Sarvam's voice (Bulbul) can speak; the other 9 + Hindi use Mayura + voice.
VOICE_LANGS = {"bn-IN", "en-IN", "gu-IN", "hi-IN", "kn-IN", "ml-IN", "mr-IN",
               "od-IN", "pa-IN", "ta-IN", "te-IN"}
LANG_NAMES = {
    "hi": "Hindi", "en": "English", "bn": "Bengali", "gu": "Gujarati", "kn": "Kannada",
    "ml": "Malayalam", "mr": "Marathi", "od": "Odia", "pa": "Punjabi", "ta": "Tamil",
    "te": "Telugu", "as": "Assamese", "ur": "Urdu", "ne": "Nepali", "sa": "Sanskrit",
    "kok": "Konkani", "mai": "Maithili", "doi": "Dogri", "ks": "Kashmiri", "sd": "Sindhi",
    "mni": "Manipuri", "sat": "Santali", "brx": "Bodo",
}


def _tokenize(text):
    return re.findall(r"[a-z0-9]+", text.lower())


def _content_terms(text):
    return [t for t in _tokenize(text) if len(t) >= 3 and t not in STOPWORDS]


def _confidence(score):
    return "High" if score >= 12 else ("Medium" if score >= 6 else "Low")


def _is_capability(text):
    t = text.lower()
    return any(p in t for p in _CAPABILITY_PATTERNS)


def decide_reply(transcript, language_code):
    """Pick ONE language + style for the whole reply (so it never switches mid-answer)."""
    base = (language_code or "en-IN").split("-")[0].lower()
    name = LANG_NAMES.get(base, language_code)
    has_devanagari = bool(re.search(r"[ऀ-ॿ]", transcript or ""))
    lower = (transcript or "").lower()
    hinglish = any(re.search(rf"\b{w}\b", lower) for w in _HINGLISH_WORDS)

    if base == "en" and not hinglish:
        return dict(is_english=True, style_label="English", voice_lang="en-IN",
                    trans_model="mayura:v1", in_source="auto", out_target="en-IN",
                    mode=None, output_script=None)
    if base == "hi" or (base == "en" and hinglish):
        if has_devanagari:
            return dict(is_english=False, style_label="Hindi", voice_lang="hi-IN",
                        trans_model="mayura:v1", in_source="auto", out_target="hi-IN",
                        mode="modern-colloquial", output_script="fully-native")
        return dict(is_english=False, style_label="Hinglish", voice_lang="hi-IN",
                    trans_model="mayura:v1", in_source="auto", out_target="hi-IN",
                    mode="code-mixed", output_script="roman")
    if language_code in VOICE_LANGS:   # other 9 languages Bulbul can speak
        return dict(is_english=False, style_label=name, voice_lang=language_code,
                    trans_model="mayura:v1", in_source="auto", out_target=language_code,
                    mode="modern-colloquial", output_script="fully-native")
    # extended languages: understand + answer in text (no Bulbul voice)
    return dict(is_english=False, style_label=name, voice_lang=None,
                trans_model="sarvam-translate:v1", in_source=language_code,
                out_target=language_code, mode=None, output_script=None)


class Assistant:
    def __init__(self):
        self.kb = KnowledgeBase()

    def _to_user_lang(self, text_en, plan):
        if plan["is_english"]:
            return text_en
        try:
            return sc.translate(text_en, plan["out_target"], source_language_code="en-IN",
                                model=plan["trans_model"], mode=plan["mode"],
                                output_script=plan["output_script"])
        except Exception:
            return text_en

    def _reply(self, transcript, language_code, plan, timings, answer_en,
               source=None, confidence="Low", score=0.0, escalate=False, kind="answer"):
        return {
            "transcript": transcript, "language_code": language_code,
            "style_label": plan["style_label"], "query_en": "",
            "answer": self._to_user_lang(answer_en, plan), "answer_en": answer_en,
            "source": source, "confidence": confidence, "score": score,
            "escalate": escalate, "kind": kind,
            "tts_lang": (plan["voice_lang"] if not escalate and kind != "offtopic" else "en-IN"),
            "timings": timings,
        }

    def answer(self, question, language_code="en-IN", k=6):
        timings = {}
        plan = decide_reply(question, language_code)

        # Gate #1: no real words (greeting / emoji / blank) -> polite, NO ticket.
        if plan["is_english"] and not _content_terms(question):
            return self._reply(question, language_code, plan, timings, POLITE_OFFTOPIC,
                               escalate=False, kind="offtopic")

        # Translate the question to English for searching (only if needed).
        try:
            if plan["is_english"]:
                query_en = question
            else:
                t = time.time()
                query_en = sc.translate(question, "en-IN", source_language_code=plan["in_source"],
                                        model=plan["trans_model"])
                timings["translate_in_ms"] = int((time.time() - t) * 1000)
        except Exception:
            return self._reply(question, language_code, plan, timings, POLITE_OFFTOPIC,
                               escalate=False, kind="offtopic")

        # "What can you help with?" -> friendly capabilities answer (not an escalation).
        if _is_capability(query_en):
            r = self._reply(question, language_code, plan, timings, CAPABILITY_ANSWER,
                            confidence="—", kind="capability")
            return r

        if not _content_terms(query_en):
            return self._reply(question, language_code, plan, timings, POLITE_OFFTOPIC,
                               escalate=False, kind="offtopic")

        # Search the real documents.
        t = time.time()
        hits = self.kb.search(query_en, k=k)
        timings["search_ms"] = int((time.time() - t) * 1000)
        top = hits[0] if hits else None

        # Gate #2: a genuine question with no relevant passage -> escalate (ticket).
        content = set(_content_terms(query_en))
        present = len(content & set(_tokenize(top["text"]))) if top else 0
        need = 2 if len(content) >= 4 else 1
        if not top or top["score"] < MIN_SCORE or present < need:
            return self._reply(question, language_code, plan, timings, POLITE_ESCALATE,
                               score=(top["score"] if top else 0.0), escalate=True, kind="escalate")

        # Ask the LLM (grounded, English, brief, names the document it used).
        context = "\n\n".join(
            f"[Document {i + 1}: {h['label'] or h['pdf']}]\n{h['text']}"
            for i, h in enumerate(hits)
        )
        try:
            t = time.time()
            raw = sc.think(SYSTEM_PROMPT, f"CONTEXT:\n{context}\n\nQUESTION: {query_en}", max_tokens=160)
            timings["llm_ms"] = int((time.time() - t) * 1000)
        except Exception:
            return self._reply(question, language_code, plan, timings, POLITE_OFFTOPIC,
                               score=top["score"], escalate=False, kind="offtopic")

        if (not raw) or ("NO_INFO" in raw.upper()):
            return self._reply(question, language_code, plan, timings, POLITE_ESCALATE,
                               score=top["score"], escalate=True, kind="escalate")

        # Which document did the LLM actually use? (accurate citation). Strip the tag
        # wherever it appears — the model sometimes writes it inline, not on its own line.
        m = re.search(r"CITED:\s*#?(\d+)", raw, re.IGNORECASE)
        cited_idx = (int(m.group(1)) - 1) if m else None
        answer_en = re.sub(r"CITED:\s*#?\d+", "", raw, flags=re.IGNORECASE).strip()
        cited = hits[cited_idx] if (cited_idx is not None and 0 <= cited_idx < len(hits)) else top

        t = time.time()
        result = self._reply(
            question, language_code, plan, timings, answer_en,
            source={"pdf": cited["pdf"], "label": cited["label"], "url": cited["url"]},
            confidence=_confidence(cited["score"]), score=cited["score"], kind="answer")
        if not plan["is_english"]:
            timings["translate_out_ms"] = int((time.time() - t) * 1000)
        result["query_en"] = query_en
        return result


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    bot = Assistant()
    for q, lang in [("what all policies can you help me with?", "en-IN"),
                    ("hi", "en-IN"),
                    ("How often must pensioners submit a life certificate?", "en-IN"),
                    ("What is the gold loan interest rate?", "en-IN")]:
        r = bot.answer(q, lang)
        print(f"Q: {q}\n  kind={r['kind']} escalate={r['escalate']} conf={r['confidence']} "
              f"src={(r['source'] or {}).get('pdf')}\n  answer={r['answer'][:160]}\n")
