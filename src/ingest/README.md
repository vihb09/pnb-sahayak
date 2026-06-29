# Knowledge base ingestion pipeline

These scripts build the assistant's knowledge base from **real, public PNB
documents**. The documents are copyrighted, so the downloaded PDFs and the
extracted `.txt` files are **git-ignored** — they are never committed. Anyone
can rebuild the knowledge base locally by running the three steps below.

Source page: <https://hrms.pnb.bank.in/pnb-sch.html>
(PNB staff welfare / medical insurance / pension circulars.)

## Run order (from the project root)

```
py src/ingest/download_pdfs.py    # 1. download every linked PDF -> data/policies/source_pdfs/
py src/ingest/extract_text.py     # 2. pull out the text layer -> data/policies/*.txt
py src/ingest/ocr_pdfs.py         # 3. OCR the scanned ones via Sarvam -> data/policies/*.txt
```

After step 3, `data/policies/source_manifest.json` records, for each document,
its original URL, title, page count, and whether it needed OCR. The live search
([src/knowledge_base.py](../knowledge_base.py)) reads this manifest so every
answer can cite the genuine source file.

- Steps 1 & 2 need only `requests` and `pypdf`.
- Step 3 needs `sarvamai` and a `SARVAM_API_KEY` in `.env`.
