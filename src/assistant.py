"""
assistant.py  -  the "answer brain".

Flow (every external call is wrapped so this NEVER crashes the request):

  question + detected language
    -> decide ONE reply language/style (locked for the whole answer)
    -> relevance gate: greetings / off-topic / no-match -> polite reply, NO LLM call
    -> translate to English (only if needed)             [Mayura]
    -> search the real PNB documents                      [BM25]
    -> LLM answers in ENGLISH, grounded, 2 short sentences [sarvam-30b]
    -> translate the ONE final answer into the locked language/style [Mayura]
    -> return answer + genuine source + confidence + per-stage timings
"""
import math
import re
import time

from knowledge_base import KnowledgeBase
import sarvam_client as sc

# The single polite reply for greetings / small talk / off-topic / no match.
POLITE = ("I can only help with questions about PNB policies, and I don't have that "
          "in my documents — I'll flag it for the team.")

# Tell the LLM to answer in English, briefly, or emit this exact token if not found.
SYSTEM_PROMPT = (
    "You are PNB Sahayak, an assistant for Punjab National Bank employees. "
    "Answer the QUESTION using ONLY the CONTEXT, which is from official PNB documents. "
    "Reply in ENGLISH, in at most 2 short sentences suitable for reading aloud. "
    "Do not invent anything not in the context. "
    "If the context does not contain the answer, reply with exactly: NO_INFO"
)

MIN_SCORE = 4.0          # below this the top match is basically noise
STOPWORDS = {
    "the", "and", "for", "are", "was", "what", "when", "how", "why", "who", "which",
    "does", "did", "can", "will", "would", "should", "you", "your", "our", "their",
    "this", "that", "these", "those", "with", "about", "from", "into", "tell", "give",
    "need", "want", "please", "there", "here", "have", "has", "had", "any", "get",
}


def _tokenize(text):
    return re.findall(r"[a-z0-9]+", text.lower())


def _content_terms(text):
    return [t for t in _tokenize(text) if len(t) >= 3 and t not in STOPWORDS]


def _confidence(score):
    return "High" if score >= 12 else ("Medium" if score >= 6 else "Low")


# Romanized-Hindi / Hinglish marker words (helps spot Hinglish typed/spoken as Latin text).
_HINGLISH_WORDS = {"kab", "hai", "kya", "kaise", "kyun", "kyon", "nahi", "mujhe", "batao",
                   "chahiye", "kitna", "kitni", "karna", "krna", "mera", "meri", "hota",
                   "hoti", "jama", "milega", "kaun", "konsa", "kitne", "sakta", "sakti"}


def decide_reply(transcript, language_code):
    """Pick ONE language + style for the whole reply. Returns dict with:
    is_english, tts_lang, style_label, mode, output_script."""
    base = (language_code or "en-IN").split("-")[0].lower()
    has_devanagari = bool(re.search(r"[ऀ-ॿ]", transcript or ""))
    lower = (transcript or "").lower()
    hinglish_markers = any(re.search(rf"\b{w}\b", lower) for w in _HINGLISH_WORDS)

    # English input with no Hindi markers -> answer in English.
    if base == "en" and not hinglish_markers:
        return {"is_english": True, "tts_lang": "en-IN", "style_label": "English",
                "mode": None, "output_script": None}

    # Hindi / Hinglish.
    if base in ("hi", "en"):  # 'en' here only reached when hinglish_markers is True
        if has_devanagari:
            return {"is_english": False, "tts_lang": "hi-IN", "style_label": "Hindi",
                    "mode": "modern-colloquial", "output_script": "fully-native"}
        return {"is_english": False, "tts_lang": "hi-IN", "style_label": "Hinglish",
                "mode": "code-mixed", "output_script": "roman"}

    # Any other Indian language -> answer natively in that language.
    return {"is_english": False, "tts_lang": language_code, "style_label": language_code,
            "mode": "modern-colloquial", "output_script": "fully-native"}


class Assistant:
    def __init__(self):
        self.kb = KnowledgeBase()

    def _polite(self, transcript, language_code, plan, timings, score=0.0):
        return {
            "transcript": transcript, "language_code": language_code,
            "style_label": plan["style_label"], "query_en": "",
            "answer": POLITE, "answer_en": POLITE,
            "source": None, "confidence": "Low", "score": score,
            "escalate": True, "tts_lang": "en-IN",  # polite text is English
            "timings": timings,
        }

    def answer(self, question, language_code="en-IN", k=6):
        timings = {}
        plan = decide_reply(question, language_code)

        # --- Relevance gate #1: no real words (greeting / emoji / blank) -> polite, no LLM.
        terms = _content_terms(question if plan["is_english"] else "")
        # For non-English we gate after translating to English (below); for English, gate now.
        if plan["is_english"] and not terms:
            return self._polite(question, language_code, plan, timings)

        # --- Translate the question to English for searching (only if needed).
        try:
            if plan["is_english"]:
                query_en = question
            else:
                t = time.time()
                query_en = sc.translate(question, "en-IN")
                timings["translate_in_ms"] = int((time.time() - t) * 1000)
        except Exception:
            return self._polite(question, language_code, plan, timings)

        if not _content_terms(query_en):
            return self._polite(question, language_code, plan, timings)

        # --- Search the real documents.
        t = time.time()
        hits = self.kb.search(query_en, k=k)
        timings["search_ms"] = int((time.time() - t) * 1000)
        top = hits[0] if hits else None

        # --- Relevance gate #2: is the top passage actually about the question?
        content = set(_content_terms(query_en))
        present = 0
        if top:
            passage_tokens = set(_tokenize(top["text"]))
            present = len(content & passage_tokens)
        need = 2 if len(content) >= 4 else 1
        if not top or top["score"] < MIN_SCORE or present < need:
            return self._polite(question, language_code, plan, timings,
                                score=(top["score"] if top else 0.0))

        # --- Ask the LLM (grounded, English, brief). Wrapped so it never crashes.
        context = "\n\n".join(
            f"[Document {i + 1}: {h['label'] or h['pdf']}]\n{h['text']}"
            for i, h in enumerate(hits)
        )
        try:
            t = time.time()
            answer_en = sc.think(SYSTEM_PROMPT, f"CONTEXT:\n{context}\n\nQUESTION: {query_en}",
                                 max_tokens=200)
            timings["llm_ms"] = int((time.time() - t) * 1000)
        except Exception:
            return self._polite(question, language_code, plan, timings, score=top["score"])

        # --- LLM says it isn't in the documents -> polite, no source.
        if (not answer_en) or ("NO_INFO" in answer_en.upper()):
            return self._polite(question, language_code, plan, timings, score=top["score"])

        # --- Translate the ONE final answer into the locked language/style.
        answer = answer_en
        if not plan["is_english"]:
            try:
                t = time.time()
                answer = sc.translate(answer_en, plan["tts_lang"], source_language_code="en-IN",
                                      mode=plan["mode"], output_script=plan["output_script"])
                timings["translate_out_ms"] = int((time.time() - t) * 1000)
            except Exception:
                answer = answer_en  # fall back to English rather than fail

        return {
            "transcript": question, "language_code": language_code,
            "style_label": plan["style_label"], "query_en": query_en,
            "answer": answer, "answer_en": answer_en,
            "source": {"pdf": top["pdf"], "label": top["label"], "url": top["url"]},
            "confidence": _confidence(top["score"]), "score": top["score"],
            "escalate": False,
            "tts_lang": ("en-IN" if plan["is_english"] else plan["tts_lang"]),
            "timings": timings,
        }


# --- end-to-end test with typed questions ---
if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    bot = Assistant()
    tests = [
        ("hi", "en-IN"),
        ("What is the weather in Mumbai today?", "en-IN"),
        ("How often must staff pensioners submit a life certificate?", "en-IN"),
        ("pension life certificate kab jama karna hai?", "hi-IN"),       # Hinglish
        ("मृत खाताधारक का दावा कैसे निपटाया जाता है?", "hi-IN"),          # Hindi
    ]
    for q, lang in tests:
        print("=" * 72)
        print(f"Q ({lang}): {q}")
        r = bot.answer(q, lang)
        print(f"  style    : {r['style_label']}   confidence: {r['confidence']}   escalate: {r['escalate']}")
        print(f"  answer   : {r['answer']}")
        if r["source"]:
            print(f"  source   : {r['source']['pdf']}")
        print(f"  timings  : {r['timings']}")
        print()
