"""
assistant.py  -  the "answer brain".

Ties the document search and the Sarvam toolbox together into one flow:

  question (any language)
    -> translate to English (if needed)        [Mayura]
    -> search the 56 real PNB documents         [BM25]
    -> feed the best passages to the LLM         [sarvam-30b]
    -> translate the answer back                [Mayura]
    -> return answer + the GENUINE source + a confidence

Grounding ("answer only from the documents", "say I don't know") is tightened
further in Phase 3; this Phase-2 version already answers from the real text and
always reports the source it used.
"""
from knowledge_base import KnowledgeBase
import sarvam_client as sc

SYSTEM_PROMPT = (
    "You are PNB Sahayak, a helpful assistant for Punjab National Bank employees. "
    "Answer the question using ONLY the information in the CONTEXT below, which is taken "
    "from official PNB policy documents. Be concise and factual — 2 to 4 short sentences, "
    "suitable for reading aloud. Do not invent anything that is not in the context. "
    "If the context does not contain the answer, reply exactly: "
    "\"I could not find this in the policy documents.\""
)

# A "phrase to say" when nothing relevant is found, before we even call the LLM.
NO_MATCH_REPLY = "I could not find this in the policy documents."
MIN_USEFUL_SCORE = 3.0   # below this, the search found nothing relevant


def confidence_label(score: float) -> str:
    if score >= 12:
        return "High"
    if score >= 6:
        return "Medium"
    return "Low"


class Assistant:
    def __init__(self):
        self.kb = KnowledgeBase()

    def answer(self, question: str, language_code: str = "en-IN", k: int = 6) -> dict:
        is_english = language_code.lower().startswith("en")

        # 1) Get an English version of the question for searching English documents.
        query_en = question if is_english else sc.translate(question, "en-IN")

        # 2) Search the real documents.
        hits = self.kb.search(query_en, k=k)
        top = hits[0] if hits else None

        result = {
            "question": question,
            "language_code": language_code,
            "query_en": query_en,
            "hits": hits,
        }

        # 2b) Nothing relevant -> don't guess.
        if not top or top["score"] < MIN_USEFUL_SCORE:
            reply_en = NO_MATCH_REPLY
            result.update(
                answer_en=reply_en,
                answer=reply_en if is_english else sc.translate(reply_en, language_code),
                source=None,
                confidence="Low",
                score=(top["score"] if top else 0.0),
            )
            return result

        # 3) Build grounded context from the top passages and ask the LLM.
        context = "\n\n".join(
            f"[Document {i + 1}: {h['label'] or h['pdf']}]\n{h['text']}"
            for i, h in enumerate(hits)
        )
        user_prompt = f"CONTEXT:\n{context}\n\nQUESTION: {query_en}"
        answer_en = sc.think(SYSTEM_PROMPT, user_prompt)

        # 4) Translate the answer back to the user's language if needed.
        answer = answer_en if is_english else sc.translate(answer_en, language_code)

        # If the model couldn't find it in the passages, don't show a (wrong) source.
        found = "could not find" not in answer_en.lower()
        result.update(
            answer_en=answer_en,
            answer=answer,
            source=({"pdf": top["pdf"], "label": top["label"], "url": top["url"]} if found else None),
            confidence=(confidence_label(top["score"]) if found else "Low"),
            score=top["score"],
        )
        return result


# --- end-to-end test with typed questions (no microphone yet) ---
if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    bot = Assistant()
    tests = [
        ("How often must staff pensioners submit a life certificate?", "en-IN"),
        ("What documents do I need to open a new savings account?", "en-IN"),
        ("मृत खाताधारक का दावा कैसे निपटाया जाता है?", "hi-IN"),  # deceased-claim, in Hindi
    ]
    for q, lang in tests:
        print("=" * 72)
        print(f"Q ({lang}): {q}")
        r = bot.answer(q, lang)
        print(f"\nAnswer: {r['answer']}")
        if lang != "en-IN":
            print(f"(English: {r['answer_en']})")
        if r["source"]:
            print(f"\nSource : {r['source']['label'][:80]}")
            print(f"         {r['source']['pdf']}")
            print(f"         {r['source']['url']}")
        print(f"Confidence: {r['confidence']}  (search score {r['score']})")
        print()
