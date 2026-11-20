# Evaluation — golden set

`golden_set.py` is a small, honest evaluation harness for PNB Sahayak. It is a fixed set of
**real questions whose correct answers were verified against the actual PNB source documents**,
plus a scorer that grades the live assistant automatically.

It calls `Assistant.answer()` directly, so it makes real Sarvam API calls **but writes no tickets
and no dashboard entries** (those side effects live in `app.py`). Policy facts are matched on the
English answer, so matching works whatever language the reply comes back in.

## What it measures

| Category | What it checks |
|---|---|
| **Answerable — normal wording** | Question worded like the documents → correct answer, correct cited source |
| **Answerable — reworded** | Same question paraphrased (worded *unlike* the documents) — where lexical BM25 search is weakest |
| **Off-topic** | General-knowledge / chit-chat → politely declined, **no ticket** |
| **Banking gaps** | A banking question the documents don't cover → honestly escalated to a **ticket** |

A normal-wording question counts as a pass only if it is answered **and** cites an acceptable source
**and** states the verified fact.

## Running it

```
py tests/golden_set.py
```

Requirements: `SARVAM_API_KEY` in `.env`, and the knowledge base built (see `src/ingest/`). The run
takes about a minute and prints a per-case PASS/FAIL list and a summary; it also writes
`tests/golden_results.json` (git-ignored).

## Representative result (sarvam-105b, Nov 2026)

```
  Answerable - normal wording       ~96-100%     (answered + correct source + correct fact)
  Answerable - reworded / paraphrase   ~62%      (the lexical-retrieval weakness)
  Off-topic declined (no ticket)        100%
  Banking gaps escalated (ticket)       100%
  OVERALL end-to-end                  ~92-94%
```

Exact numbers vary by a question or two between runs because the model runs at a small non-zero
temperature (0.2). The headline finding is stable: **near-perfect on well-worded questions, with
the honest weakness being paraphrases** — which is why hybrid (keyword + embedding) retrieval with a
reranker is the planned next step, not a quick lexical patch (measured: cheap title-indexing and
synonym tweaks traded a paraphrase gain for a regression elsewhere).

Growing this into the bank's own golden set (real staff questions, verified by the policy team) is
the first deliverable of a production pilot.
