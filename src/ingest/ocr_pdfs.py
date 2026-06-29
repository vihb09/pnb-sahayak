"""
STEP 3 of building the knowledge base.

OCRs the scanned PDFs flagged by step 2 (needs_ocr=True) using Sarvam's
Document Digitization API (the sarvam-vision model). Files longer than 10 pages
are split into <=10-page chunks (Sarvam's per-job limit) and re-joined.

Needs SARVAM_API_KEY in the .env file.
Run from the project root:  py src/ingest/ocr_pdfs.py
"""
import json
import os
import zipfile
from pathlib import Path

from dotenv import load_dotenv
from pypdf import PdfReader, PdfWriter
from sarvamai import SarvamAI

PROJECT_DIR = Path(__file__).resolve().parents[2]
POLICIES = PROJECT_DIR / "data" / "policies"
SRC = POLICIES / "source_pdfs"
MANIFEST = POLICIES / "source_manifest.json"
WORK = POLICIES / "_ocr_work"          # temporary chunk/zip files (git-ignored)

MAX_PAGES = 10
LANGUAGE = "en-IN"                       # these PNB circulars are in English

load_dotenv(PROJECT_DIR / ".env")
client = SarvamAI(api_subscription_key=os.getenv("SARVAM_API_KEY"))


def split_pdf(pdf_path: Path):
    """Return a list of <=MAX_PAGES-page chunk PDFs (just [pdf_path] if small)."""
    reader = PdfReader(str(pdf_path))
    n = len(reader.pages)
    if n <= MAX_PAGES:
        return [pdf_path]
    WORK.mkdir(parents=True, exist_ok=True)
    chunks = []
    for start in range(0, n, MAX_PAGES):
        end = min(start + MAX_PAGES, n)
        writer = PdfWriter()
        for i in range(start, end):
            writer.add_page(reader.pages[i])
        out = WORK / f"{pdf_path.stem}__p{start + 1}-{end}.pdf"
        with open(out, "wb") as f:
            writer.write(f)
        chunks.append(out)
    return chunks


def ocr_one_file(pdf_path: Path) -> str:
    """Run one Sarvam Document Digitization job; return the extracted markdown."""
    WORK.mkdir(parents=True, exist_ok=True)
    job = client.document_intelligence.create_job(language=LANGUAGE, output_format="md")
    print(f"      job {job.job_id}: uploading {pdf_path.name} ...")
    job.upload_file(str(pdf_path))
    job.start()
    status = job.wait_until_complete(poll_interval=3.0, timeout=900)
    print(f"      job state: {getattr(status, 'job_state', status)}")
    zip_out = WORK / f"{pdf_path.stem}__out.zip"
    job.download_output(str(zip_out))

    texts = []
    with zipfile.ZipFile(zip_out) as z:
        for name in sorted(n for n in z.namelist() if n.lower().endswith(".md")):
            texts.append(z.read(name).decode("utf-8", errors="replace"))
    return "\n\n".join(texts).strip()


def main():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    todo = [m for m in manifest if m.get("needs_ocr")]
    print(f"Documents needing OCR: {len(todo)}\n")

    for m in todo:
        pdf_path = SRC / m["pdf"]
        print(f"-> OCR: {m['pdf']}")
        try:
            chunks = split_pdf(pdf_path)
            if len(chunks) > 1:
                print(f"   split into {len(chunks)} chunks (>{MAX_PAGES} pages)")
            text = "\n\n".join(t for t in (ocr_one_file(c) for c in chunks) if t).strip()
        except Exception as e:
            print(f"   FAILED: {e}\n")
            m["ocr_error"] = str(e)
            continue
        if not text:
            print("   WARNING: OCR returned empty text.\n")
            m["ocr_error"] = "empty OCR result"
            continue

        txt_name = Path(m["pdf"]).stem + ".txt"
        (POLICIES / txt_name).write_text(text, encoding="utf-8")
        m.update(txt=txt_name, ocr=True,
                 ocr_method="Sarvam Document Digitization (sarvam-vision)", chars=len(text))
        m.pop("ocr_error", None)
        print(f"   OK -> {txt_name}  ({len(text)} chars)\n")

    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print("Manifest updated.")


if __name__ == "__main__":
    main()
