"""
assistant.py  -  the "answer brain".

Flow (every external call is wrapped so this NEVER crashes the request):

  question + detected language
    -> decide ONE reply language/style (locked for the whole answer)
    -> relevance gate: greetings / off-topic -> polite reply, NO LLM, NO ticket
    -> translate to English (only if needed)              [Mayura]
    -> search the real PNB documents                       [BM25]
    -> a genuine question with no match -> escalate (ticket) instead of guessing
    -> LLM answers in ENGLISH, grounded, 2 sentences, and names the document it used [sarvam-30b]
    -> translate the ONE final answer into the locked language/style [Mayura]
    -> return answer + the GENUINE cited source + confidence + timings + escalate flag
"""
import re
import time

from knowledge_base import KnowledgeBase
import sarvam_client as sc

# Off-topic / greeting -> polite, NO ticket.
POLITE_OFFTOPIC = ("I can only help with questions about PNB policies — please ask "
                   "about a policy, procedure, or circular.")
# A genuine policy question we could not answer -> polite + escalate to the team.
POLITE_ESCALATE = ("I couldn't find this in the PNB policy documents, so I've flagged "
                   "it for the policy team to follow up.")

SYSTEM_PROMPT = (
    "You are PNB Sahayak, an assistant for Punjab National Bank employees. "
    "Answer the QUESTION using ONLY the facts in the CONTEXT, which is taken from official "
    "PNB documents. Never use outside knowledge and never guess. "
    "Reply in ENGLISH, in at most 2 short sentences suitable for reading aloud. "
    "Then, on a final separate line, write 'CITED: N' with the single Document number you used. "
    "If the CONTEXT does not contain the answer, reply with exactly NO_INFO and nothing else."
)

MIN_SCORE = 4.0          # below this the top match is basically noise
STOPWORDS = {
    "the", "and", "for", "are", "was", "what", "when", "how", "why", "who", "which",
    "does", "did", "can", "will", "would", "should", "you", "your", "our", "their",
    "this", "that", "these", "those", "with", "about", "from", "into", "tell", "give",
    "need", "want", "please", "there", "here", "have", "has", "had", "any", "get",
}
_HINGLISH_WORDS = {"kab", "hai", "kya", "kaise", "kyun", "kyon", "nahi", "mujhe", "batao",
                   "chahiye", "kitna", "kitni", "karna", "krna", "mera", "meri", "hota",
                   "hoti", "jama", "milega", "kaun", "konsa", "kitne", "sakta", "sakti"}


def _tokenize(text):
    return re.findall(r"[a-z0-9]+", text.lower())


def _content_terms(text):
    return [t for t in _tokenize(text) if len(t) >= 3 and t not in STOPWORDS]


def _confidence(score):
    return "High" if score >= 12 else ("Medium" if score >= 6 else "Low")


def decide_reply(transcript, language_code):
    """Pick ONE language + style for the whole reply (so it never switches mid-answer)."""
    base = (language_code or "en-IN").split("-")[0].lower()
    has_devanagari = bool(re.search(r"[ऀ-ॿ]", transcript or ""))
    lower = (transcript or "").lower()
    hinglish_markers = any(re.search(rf"\b{w}\b", lower) for w in _HINGLISH_WORDS)

    if base == "en" and not hinglish_markers:
        return {"is_english": True, "tts_lang": "en-IN", "style_label": "English",
                "mode": None, "output_script": None}
    if base in ("hi", "en"):
        if has_devanagari:
            return {"is_english": False, "tts_lang": "hi-IN", "style_label": "Hindi",
                    "mode": "modern-colloquial", "output_script": "fully-native"}
        return {"is_english": False, "tts_lang": "hi-IN", "style_label": "Hinglish",
                "mode": "code-mixed", "output_script": "roman"}
    return {"is_english": False, "tts_lang": language_code, "style_label": language_code,
            "mode": "modern-colloquial", "output_script": "fully-native"}


class Assistant:
    def __init__(self):
        self.kb = KnowledgeBase()

    def _polite(self, transcript, language_code, plan, timings, score=0.0, escalate=True):
        msg = POLITE_ESCALATE if escalate else POLITE_OFFTOPIC
        return {
            "transcript": transcript, "language_code": language_code,
            "style_label": plan["style_label"], "query_en": "",
            "answer": msg, "answer_en": msg,
            "source": None, "confidence": "Low", "score": score,
            "escalate": escalate, "tts_lang": "en-IN",   # polite text is English
            "timings": timings,
        }

    def answer(self, question, language_code="en-IN", k=6):
        timings = {}
        plan = decide_reply(question, language_code)

        # Gate #1: no real words (greeting / emoji / blank) -> polite, NO ticket.
        if plan["is_english"] and not _content_terms(question):
            return self._polite(question, language_code, plan, timings, escalate=False)

        # Translate the question to English for searching (only if needed).
        try:
            if plan["is_english"]:
                query_en = question
            else:
                t = time.time()
                query_en = sc.translate(question, "en-IN")
                timings["translate_in_ms"] = int((time.time() - t) * 1000)
        except Exception:
            return self._polite(question, language_code, plan, timings, escalate=False)

        if not _content_terms(query_en):
            return self._polite(question, language_code, plan, timings, escalate=False)

        # Search the real documents.
        t = time.time()
        hits = self.kb.search(query_en, k=k)
        timings["search_ms"] = int((time.time() - t) * 1000)
        top = hits[0] if hits else None

        # Gate #2: a genuine question with no relevant passage -> escalate (ticket), don't guess.
        content = set(_content_terms(query_en))
        present = len(content & set(_tokenize(top["text"]))) if top else 0
        need = 2 if len(content) >= 4 else 1
        if not top or top["score"] < MIN_SCORE or present < need:
            return self._polite(question, language_code, plan, timings,
                                score=(top["score"] if top else 0.0), escalate=True)

        # Ask the LLM (grounded, English, brief, names the document it used).
        context = "\n\n".join(
            f"[Document {i + 1}: {h['label'] or h['pdf']}]\n{h['text']}"
            for i, h in enumerate(hits)
        )
        try:
            t = time.time()
            raw = sc.think(SYSTEM_PROMPT, f"CONTEXT:\n{context}\n\nQUESTION: {query_en}", max_tokens=220)
            timings["llm_ms"] = int((time.time() - t) * 1000)
        except Exception:
            # transient service error (not a policy gap) -> polite, no ticket.
            return self._polite(question, language_code, plan, timings, score=top["score"], escalate=False)

        # LLM says it isn't in the documents -> escalate (genuine gap).
        if (not raw) or ("NO_INFO" in raw.upper()):
            return self._polite(question, language_code, plan, timings, score=top["score"], escalate=True)

        # Pull out which document the LLM actually used, for an accurate citation.
        cited_idx, kept = None, []
        for ln in raw.splitlines():
            m = re.match(r"\s*CITED:\s*#?(\d+)", ln, re.IGNORECASE)
            if m:
                cited_idx = int(m.group(1)) - 1
            else:
                kept.append(ln)
        answer_en = "\n".join(kept).strip()
        cited = hits[cited_idx] if (cited_idx is not None and 0 <= cited_idx < len(hits)) else top

        # Translate the ONE final answer into the locked language/style.
        answer = answer_en
        if not plan["is_english"]:
            try:
                t = time.time()
                answer = sc.translate(answer_en, plan["tts_lang"], source_language_code="en-IN",
                                      mode=plan["mode"], output_script=plan["output_script"])
                timings["translate_out_ms"] = int((time.time() - t) * 1000)
            except Exception:
                answer = answer_en

        return {
            "transcript": question, "language_code": language_code,
            "style_label": plan["style_label"], "query_en": query_en,
            "answer": answer, "answer_en": answer_en,
            "source": {"pdf": cited["pdf"], "label": cited["label"], "url": cited["url"]},
            "confidence": _confidence(cited["score"]), "score": cited["score"],
            "escalate": False,
            "tts_lang": ("en-IN" if plan["is_english"] else plan["tts_lang"]),
            "timings": timings,
        }


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    bot = Assistant()
    for q, lang in [("hi", "en-IN"),
                    ("What is the current RBI repo rate?", "en-IN"),
                    ("How often must staff pensioners submit a life certificate?", "en-IN")]:
        r = bot.answer(q, lang)
        print(f"Q: {q}\n  escalate={r['escalate']} conf={r['confidence']} "
              f"source={(r['source'] or {}).get('pdf')}\n  answer={r['answer'][:120]}\n")
