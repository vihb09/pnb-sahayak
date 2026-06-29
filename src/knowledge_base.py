"""
knowledge_base.py  -  the assistant's document search.

Loads the real PNB policy text (extracted into data/policies/*.txt), splits each
document into small passages, and builds a BM25 keyword index over them. BM25 is
a classic search method that ranks passages by how well their words match the
question. Every passage remembers which genuine source PDF it came from, so the
assistant can always cite the real document.
"""
import json
import re
from pathlib import Path

from rank_bm25 import BM25Okapi

PROJECT_DIR = Path(__file__).resolve().parent.parent
POLICIES_DIR = PROJECT_DIR / "data" / "policies"
MANIFEST = POLICIES_DIR / "source_manifest.json"

CHUNK_SIZE = 1000      # characters per passage (roughly a few paragraphs)
CHUNK_OVERLAP = 150    # characters shared between neighbouring passages


def _clean(text: str) -> str:
    """Strip HTML/markdown table tags and tidy whitespace."""
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("&nbsp;", " ").replace("|", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _chunk(text: str) -> list[str]:
    """Split text into ~CHUNK_SIZE passages, packing whole paragraphs together."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks, current = [], ""
    for p in paras:
        if len(current) + len(p) + 1 <= CHUNK_SIZE:
            current = (current + "\n" + p).strip()
        else:
            if current:
                chunks.append(current)
            if len(p) <= CHUNK_SIZE:
                current = p
            else:  # a single very long block (e.g. a big table): hard-split it
                step = CHUNK_SIZE - CHUNK_OVERLAP
                for i in range(0, len(p), step):
                    chunks.append(p[i:i + CHUNK_SIZE])
                current = ""
    if current:
        chunks.append(current)
    return chunks


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


class KnowledgeBase:
    def __init__(self):
        self.chunks = []   # list of dicts: text, pdf, label, url
        self._load()
        self._bm25 = BM25Okapi([_tokenize(c["text"]) for c in self.chunks])

    def _load(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        for m in manifest:
            txt_name = m.get("txt")
            if not txt_name:
                continue
            txt_path = POLICIES_DIR / txt_name
            if not txt_path.exists():
                continue
            cleaned = _clean(txt_path.read_text(encoding="utf-8"))
            for passage in _chunk(cleaned):
                self.chunks.append({
                    "text": passage,
                    "pdf": m["pdf"],
                    "label": m.get("label", ""),
                    "url": m.get("url", ""),
                })

    @property
    def num_documents(self) -> int:
        return len({c["pdf"] for c in self.chunks})

    def search(self, query: str, k: int = 5) -> list[dict]:
        """Return the top-k passages with their source and a relevance score."""
        scores = self._bm25.get_scores(_tokenize(query))
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        results = []
        for i in ranked[:k]:
            full_text = " ".join(self.chunks[i]["text"].split())
            results.append({
                "score": round(float(scores[i]), 2),
                "pdf": self.chunks[i]["pdf"],
                "label": self.chunks[i]["label"],
                "url": self.chunks[i]["url"],
                "text": full_text,             # the full passage, for the LLM to read
                "snippet": full_text[:300],    # a short preview, for the screen
            })
        return results


# --- quick self-test: ask a few real questions and show the genuine source ---
if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # clean output on Windows

    kb = KnowledgeBase()
    print(f"Loaded {kb.num_documents} documents -> {len(kb.chunks)} searchable passages\n")

    questions = [
        "How often must staff pensioners submit a life certificate?",
        "What documents are required to open a new bank account (KYC)?",
        "How is a claim settled when an account holder has died?",
        "How can a customer file a complaint or grievance with the bank?",
        "What schemes are covered under the Staff Welfare Fund?",
    ]
    for q in questions:
        print("=" * 70)
        print("Q:", q)
        top = kb.search(q, k=1)[0]
        print(f"  Best source : {top['pdf']}  (score {top['score']})")
        print(f"  Document    : {top['label'][:90]}")
        print(f"  Real URL    : {top['url']}")
        print(f"  Snippet     : {top['snippet'][:220]}...")
        print()
