"""
STEP 2 of building the knowledge base.

Tries to read the text layer out of each downloaded PDF (fast and free).
Writes a .txt for every PDF that already has real text, and flags the rest
(scanned images) as needing OCR. Records pages/chars/needs_ocr in the manifest.

Run from the project root:  py src/ingest/extract_text.py
"""
import json
import logging
from pathlib import Path

from pypdf import PdfReader

logging.getLogger("pypdf").setLevel(logging.ERROR)

PROJECT_DIR = Path(__file__).resolve().parents[2]
POLICIES = PROJECT_DIR / "data" / "policies"
SRC = POLICIES / "source_pdfs"
MANIFEST = POLICIES / "source_manifest.json"

# A page of real text has hundreds of characters; a scanned image yields ~0.
MIN_CHARS_PER_PAGE = 100


def main():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    good = need = 0

    for m in manifest:
        pdf_path = SRC / m["pdf"]
        if not pdf_path.exists():
            m["pages"], m["chars"], m["needs_ocr"] = 0, 0, True
            continue
        try:
            reader = PdfReader(str(pdf_path))
            pages = len(reader.pages)
            parts = []
            for page in reader.pages:
                try:
                    parts.append(page.extract_text() or "")
                except Exception:
                    parts.append("")
            text = "\n".join(parts).strip()
        except Exception as e:
            m["pages"], m["chars"], m["needs_ocr"], m["extract_error"] = 0, 0, True, str(e)
            need += 1
            continue

        chars = len(text)
        cpp = (chars / pages) if pages else 0
        needs_ocr = (pages == 0) or (cpp < MIN_CHARS_PER_PAGE)
        m["pages"], m["chars"], m["needs_ocr"] = pages, chars, needs_ocr
        m.pop("extract_error", None)
        if not needs_ocr:
            txt_name = Path(m["pdf"]).stem + ".txt"
            (POLICIES / txt_name).write_text(text, encoding="utf-8")
            m["txt"] = txt_name
            good += 1
        else:
            need += 1

    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Have a usable text layer: {good}  -> saved as .txt")
    print(f"Need OCR (run step 3):    {need}")


if __name__ == "__main__":
    main()
