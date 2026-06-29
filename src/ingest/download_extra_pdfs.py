"""
STEP 1b of building the knowledge base (breadth).

Downloads a curated set of additional REAL, public PNB policy documents from the
main bank website (pnbindia.in) so the assistant can answer a wider range of
employee questions (KYC, account opening, customer rights, deceased-claim
settlement, grievance redressal, service charges, NRI services). Appends them to
data/policies/source_manifest.json without disturbing the existing entries.

Run from the project root:  py src/ingest/download_extra_pdfs.py
(then re-run extract_text.py and ocr_pdfs.py)
"""
import json
import re
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests

PROJECT_DIR = Path(__file__).resolve().parents[2]
OUT = PROJECT_DIR / "data" / "policies" / "source_pdfs"
MANIFEST = PROJECT_DIR / "data" / "policies" / "source_manifest.json"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}

# (url, human-readable title) — all genuine public PNB documents.
CURATED = [
    ("https://www.pnbindia.in/document/CODE_OF_BANKS_COMMITMENT_TO_CUSTOMERS_ADOPTED_BY_PNB.pdf",
     "Code of Bank's Commitment to Customers (PNB)"),
    ("https://www.pnbindia.in/document/Banks_Commitments_Customers.pdf",
     "Bank's Commitments to Customers"),
    ("https://www.pnbindia.in/document/customer-care/ho_cust_care_customer_rights_policy.pdf",
     "Customer Rights Policy"),
    ("https://www.pnbindia.in/document/Deceased-Claim-cases.pdf",
     "Settlement of claims pertaining to deceased / missing customers"),
    ("https://www.pnbindia.in/document/Banking_ombudsman.pdf",
     "RBI Integrated Ombudsman Scheme, 2021 (grievance redressal)"),
    ("https://www.pnbindia.in/document/others/KYC_AML_Documents_2015.pdf",
     "List of KYC documents required for opening of accounts"),
    ("https://www.pnbindia.in/document/fi_e-kyc_facility.pdf",
     "Process flow for e-KYC and account opening at BC locations & branches"),
    ("https://www.pnbindia.in/document/download-form/aof_revised.pdf",
     "Account Opening Form (all branches, resident)"),
    ("https://www.pnbindia.in/document/NRIservices/FAQ_NRO_RMD.pdf",
     "FAQ on NRO accounts (NRI services)"),
    ("https://www.pnbindia.in/pnb-giftcity/download/Annexure-II_ScheduleofCharges_PNBIBUGIFTCITY.pdf",
     "Schedule of Charges (PNB IFSC Banking Unit, GIFT City)"),
]


def safe_name(url: str) -> str:
    name = unquote(urlparse(url).path.split("/")[-1])
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    return re.sub(r"\s+", " ", name).strip()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else []
    have_urls = {m["url"] for m in manifest}

    ok = skipped = failed = 0
    for url, title in CURATED:
        if url in have_urls:
            print(f"skip (already in manifest)  {title}")
            skipped += 1
            continue
        fn = safe_name(url)
        dest = OUT / fn
        try:
            resp = requests.get(url, headers=UA, timeout=90)
            resp.raise_for_status()
            dest.write_bytes(resp.content)
            manifest.append({
                "pdf": fn, "url": url, "label": title,
                "collection": "pnbindia-public", "bytes": len(resp.content),
            })
            ok += 1
            print(f"OK  {len(resp.content):>8} bytes  {fn}")
        except Exception as e:
            failed += 1
            print(f"FAIL  {fn}  -> {e}")

    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nAdded {ok}, skipped {skipped}, failed {failed}. Manifest now has {len(manifest)} entries.")
    print("Next: re-run  py src/ingest/extract_text.py  then  py src/ingest/ocr_pdfs.py")


if __name__ == "__main__":
    main()
