"""
STEP 1 of building the knowledge base.

Downloads every PDF linked on the PNB staff-schemes page into
data/policies/source_pdfs/ and records each file's original URL and title in
data/policies/source_manifest.json.

Run from the project root:  py src/ingest/download_pdfs.py
"""
import json
import re
from pathlib import Path
from urllib.parse import urljoin, unquote, urlparse
from html.parser import HTMLParser

import requests

PROJECT_DIR = Path(__file__).resolve().parents[2]
PAGE = "https://hrms.pnb.bank.in/pnb-sch.html"
OUT = PROJECT_DIR / "data" / "policies" / "source_pdfs"
MANIFEST = PROJECT_DIR / "data" / "policies" / "source_manifest.json"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self._href = None
        self._text = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            self.links.append((self._href, "".join(self._text)))
            self._href = None
            self._text = []


def safe_name(url: str) -> str:
    name = unquote(urlparse(url).path.split("/")[-1])
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    return re.sub(r"\s+", " ", name).strip()


def clean_label(s: str) -> str:
    return " ".join(s.replace("�", " ").split())


def main():
    r = requests.get(PAGE, headers=UA, timeout=30)
    r.raise_for_status()
    r.encoding = "utf-8"   # the page is UTF-8 (smart quotes, dashes, etc.)

    parser = LinkParser()
    parser.feed(r.text)
    pdfs, seen = [], set()
    for href, label in parser.links:
        if href and ".pdf" in href.lower():
            full = urljoin(PAGE, href)
            if full not in seen:
                seen.add(full)
                pdfs.append((full, clean_label(label)))

    OUT.mkdir(parents=True, exist_ok=True)
    print(f"Found {len(pdfs)} PDF links. Downloading into:\n  {OUT}\n")

    manifest, ok, skipped, failed = [], 0, 0, 0
    for i, (url, label) in enumerate(pdfs, 1):
        fn = safe_name(url)
        dest = OUT / fn
        entry = {"pdf": fn, "url": url, "label": label}
        if dest.exists() and dest.stat().st_size > 0:
            entry["bytes"] = dest.stat().st_size
            manifest.append(entry)
            skipped += 1
            print(f"[{i:>2}/{len(pdfs)}] skip (already have)  {fn}")
            continue
        try:
            resp = requests.get(url, headers=UA, timeout=90)
            resp.raise_for_status()
            dest.write_bytes(resp.content)
            entry["bytes"] = len(resp.content)
            manifest.append(entry)
            ok += 1
            print(f"[{i:>2}/{len(pdfs)}] OK  {len(resp.content):>8} bytes  {fn}")
        except Exception as e:
            entry["error"] = str(e)
            manifest.append(entry)
            failed += 1
            print(f"[{i:>2}/{len(pdfs)}] FAIL  {fn}  -> {e}")

    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSummary: downloaded {ok}, already had {skipped}, failed {failed}")
    print(f"Manifest: {MANIFEST}")


if __name__ == "__main__":
    main()
