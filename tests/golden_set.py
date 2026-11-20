"""PNB Sahayak - golden-set evaluation harness.

A fixed set of real questions whose correct answers are verified against the actual PNB
source documents. The scorer calls Assistant.answer() directly, so it makes real Sarvam
API calls but writes NO tickets and NO dashboard entries (those live in app.py). Policy
facts are matched on the English answer (answer_en), so matching works in any reply language.

Run from the project root (needs SARVAM_API_KEY in .env and the knowledge base built -
see src/ingest/):

    py tests/golden_set.py

It prints per-case PASS/FAIL and a summary (normal vs reworded wording, off-topic handling,
and banking-gap escalation), and saves tests/golden_results.json.
"""
import json
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from assistant import Assistant

# --- acceptable source documents per question (several circulars can cover one scheme) ---
LC = {"LC_10_2019_FINAL_CIRCULAR.pdf", "CIRCULAR12_24102018.pdf", "PFPENSION102020-merged.pdf",
      "PPF132020final.pdf", "Lifecertificate.pdf"}
DOMI = {"DOMICILIARY DISEASES.pdf", "333 DATED 13.10.16.pdf", "OPERATIONAL GUIDELINES DOMICILIARY.pdf",
        "DOMI.pdf", "RETIREE 17-18 WITH DOMICILIARY.pdf",
        "395 8.1.18 OPERATIONAL GUIDELINES-RETIREES 08 01 2018.pdf", "Med_Ins_Sch.pdf"}
DECEASED = {"Deceased-Claim-cases.pdf", "CODE_OF_BANKS_COMMITMENT_TO_CUSTOMERS_ADOPTED_BY_PNB.pdf"}
WELFARE = {"ws-benifit-welfare-fund.pdf", "ws-emp-dec.pdf"}
KYC = {"KYC_AML_Documents_2015.pdf"}
RIGHTS = {"ho_cust_care_customer_rights_policy.pdf",
          "CODE_OF_BANKS_COMMITMENT_TO_CUSTOMERS_ADOPTED_BY_PNB.pdf", "Banks_Commitments_Customers.pdf"}
HOSP = {"Cir-515-2009.pdf", "Cir-124-2012.pdf", "Cir-201-2014.pdf"}

A = "answer"
# (id, question, language, kind, variant, acceptable_sources, any_of_facts)
GOLD = [
    ("lc-month", "When must staff pensioners submit their life certificate?", "en-IN", A, "normal", LC, ["november"]),
    ("lc-branch", "Can a pensioner submit the life certificate at any branch of the bank?", "en-IN", A, "normal", LC, ["any branch", "branch"]),
    ("lc-digital", "Is a digital life certificate option available to pensioners?", "en-IN", A, "normal", LC, ["jeevan pramaan", "digital", "aadhaar", "aadhar"]),
    ("tds-dec", "By when must a pensioner submit investment proof to get the TDS rebate?", "en-IN", A, "normal", {"Investment.pdf"}, ["december", "10th"]),
    ("tds-app", "During which months can pensioners enter investment details in the mobile app?", "en-IN", A, "normal", {"Investment.pdf"}, ["october", "april"]),
    ("welf-list", "Which schemes are covered under the Staff Welfare Fund?", "en-IN", A, "normal", WELFARE, ["canteen", "scholarship", "hospitalization", "hospitalisation"]),
    ("loan-yes", "Can retirees get a loan to pay the medical insurance premium?", "en-IN", A, "normal", {"335.pdf"}, ["demand loan", "premium"]),
    ("loan-inst", "In how many instalments is the insurance-premium loan for retirees repaid?", "en-IN", A, "normal", {"335.pdf"}, ["10", "ten"]),
    ("loan-rate", "What interest rate applies to the insurance-premium loan for retirees?", "en-IN", A, "normal", {"335.pdf"}, ["mclr"]),
    ("disc-2016", "When was the old PNB Mediclaim scheme for retired employees discontinued?", "en-IN", A, "normal", {"732.pdf"}, ["2016", "01.01.2016"]),
    ("kyc-ovd", "Which officially valid documents are accepted as proof of identity and address for opening an account?", "en-IN", A, "normal", KYC, ["passport", "pan", "voter", "driving", "aadhaar", "aadhar"]),
    ("kyc-pan", "If a customer's PAN card does not show their address, what else is needed for KYC?", "en-IN", A, "normal", KYC, ["address", "another", "proof of address"]),
    ("dec-nom", "How is a deceased customer's account settled when there is a nomination?", "en-IN", A, "normal", DECEASED, ["nominee", "831"]),
    ("dec-form", "Which form does a nominee use to claim a deceased customer's deposit?", "en-IN", A, "normal", DECEASED, ["831"]),
    ("dec-noheir", "How is a deceased customer's account settled when there is no nomination or survivorship?", "en-IN", A, "normal", DECEASED, ["legal heir", "succession", "46-47", "claim form"]),
    ("dec-miss", "What is needed to settle the account of a customer missing for seven years?", "en-IN", A, "normal", DECEASED, ["fir", "court", "section 108", "evidence act"]),
    ("nro-repat", "How much can an NRI repatriate from an NRO account in a financial year?", "en-IN", A, "normal", {"FAQ_NRO_RMD.pdf"}, ["million", "usd"]),
    ("nro-curr", "In which currency is an NRO account maintained?", "en-IN", A, "normal", {"FAQ_NRO_RMD.pdf"}, ["rupee", "inr"]),
    ("domi-dis", "Which kinds of diseases are covered under domiciliary treatment?", "en-IN", A, "normal", DOMI, ["cancer", "tuberculosis", "paralysis", "59", "domiciliary"]),
    ("domi-physio", "Is physiotherapy covered under domiciliary treatment?", "en-IN", A, "normal", DOMI, ["physiotherapy"]),
    ("tpa", "Which TPA administers the IBA group medical insurance scheme for retired employees?", "en-IN", A, "normal", {"NOTICE 09 11 2017.pdf"}, ["health insurance tpa"]),
    ("lal", "Is there a tie-up with Dr Lal PathLabs, and what discount do employees get?", "en-IN", A, "normal", {"409 DT 03.5.pdf"}, ["20", "discount"]),
    ("hosp-intro", "When was the PNB Hospitalisation Contributory Benefit Scheme for retired employees introduced?", "en-IN", A, "normal", HOSP, ["2009"]),
    ("rights-list", "What are the basic rights in the PNB Customer Rights Policy?", "en-IN", A, "normal", RIGHTS, ["fair treatment", "privacy", "transparency", "suitability", "grievance"]),
    ("rights-30", "Within how many days should the bank resolve a customer complaint?", "en-IN", A, "normal", RIGHTS, ["30", "thirty"]),

    # reworded / paraphrased - the same answers, worded unlike the documents (lexical search is weak here)
    ("rw-lc", "By which month must retired staff prove they are alive to keep getting paid?", "en-IN", A, "reworded", LC, ["november"]),
    ("rw-loan", "Can the bank lend a pensioner money so they can afford the health-policy payment?", "en-IN", A, "reworded", {"335.pdf"}, ["demand loan", "premium", "loan"]),
    ("rw-kyc", "What ID papers should a new customer bring along to start banking with us?", "en-IN", A, "reworded", KYC, ["passport", "pan", "voter", "driving", "aadhaar", "aadhar"]),
    ("rw-dec", "A customer's father passed away; how does the family get the money in his account?", "en-IN", A, "reworded", DECEASED, ["nominee", "legal heir", "claim", "831", "succession"]),
    ("rw-lal", "Where can retirees get their lab tests done at a discount?", "en-IN", A, "reworded", {"409 DT 03.5.pdf", "NOTICE DATED16.06.2017.pdf"}, ["lal", "pathlab", "20"]),
    ("rw-nro", "Can someone living abroad send their rupee earnings from India overseas?", "en-IN", A, "reworded", {"FAQ_NRO_RMD.pdf"}, ["million", "usd", "repatriat"]),
    ("rw-death", "What help does the bank give the family if a staff member dies while still working?", "en-IN", A, "reworded", WELFARE, ["financial", "family", "death", "assistance"]),
    ("rw-domi", "Can a retiree claim money for treatment taken at home for a long-term illness?", "en-IN", A, "reworded", DOMI, ["domiciliary", "cancer", "home"]),

    # multilingual (facts still matched on the English answer_en)
    ("hi-lc", "पेंशनर को जीवन प्रमाण पत्र कब जमा करना है?", "hi-IN", A, "normal", LC, ["november"]),
    ("hing-lc", "pension life certificate kab jama karna hai", "en-IN", A, "normal", LC, ["november"]),

    # off-topic: must be declined, NO ticket (kind == offtopic)
    ("off-pm", "Who is the Prime Minister of India?", "en-IN", "offtopic", "-", None, None),
    ("off-weather", "What is the weather in Delhi today?", "en-IN", "offtopic", "-", None, None),
    ("off-joke", "Tell me a joke", "en-IN", "offtopic", "-", None, None),
    ("off-france", "What is the capital of France?", "en-IN", "offtopic", "-", None, None),
    ("off-ipl", "Who won the IPL this year?", "en-IN", "offtopic", "-", None, None),
    ("off-date", "What is the date today?", "en-IN", "offtopic", "-", None, None),
    ("off-movie", "Recommend a good movie to watch", "en-IN", "offtopic", "-", None, None),
    ("off-ml", "What is machine learning?", "en-IN", "offtopic", "-", None, None),
    ("off-hi-date", "आज की तारीख क्या है?", "hi-IN", "offtopic", "-", None, None),

    # banking questions NOT in the documents: must escalate (a real gap -> ticket)
    ("gap-gold", "What is the gold loan interest rate?", "en-IN", "escalate", "-", None, None),
    ("gap-home", "What is the home loan interest rate today?", "en-IN", "escalate", "-", None, None),
    ("gap-netbank", "How do I reset my net banking password?", "en-IN", "escalate", "-", None, None),
    ("gap-leave", "How many casual leaves does a clerk get in a year?", "en-IN", "escalate", "-", None, None),
    ("gap-salary", "What is the monthly salary of a branch manager?", "en-IN", "escalate", "-", None, None),
]


def main():
    bot = Assistant()
    print(f"Index: {bot.kb.num_documents} documents, {len(bot.kb.chunks)} passages\n")

    def run(q, lang):
        for _ in range(2):
            try:
                r = bot.answer(q, lang)
                return r["kind"], (r.get("source") or {}).get("pdf"), r.get("answer_en", "") or r.get("answer", "")
            except Exception as e:
                err = f"ERROR {e!r}"
                time.sleep(1)
        return "ERROR", None, err

    rows = []
    t0 = time.time()
    for cid, q, lang, kind, variant, srcs, facts in GOLD:
        got_kind, got_pdf, ans = run(q, lang)
        al = ans.lower()
        source_ok = bool(srcs) and got_pdf in srcs
        fact_ok = bool(facts) and any(f in al for f in facts)
        if kind == A:
            ok = (got_kind == "answer") and source_ok and fact_ok
        elif kind == "offtopic":
            ok = got_kind == "offtopic"
        else:
            ok = got_kind == "escalate"
        rows.append({"id": cid, "want": kind, "variant": variant, "got": got_kind,
                     "source_ok": source_ok, "fact_ok": fact_ok, "pass": ok, "pdf": got_pdf,
                     "q": q, "answer_en": ans[:160]})
        print(f"  {'PASS' if ok else 'FAIL'}  [{variant:8}] {cid:12} want={kind:9} got={got_kind:9}")

    def pct(sel):
        s = [r for r in rows if sel(r)]
        p = sum(r["pass"] for r in s)
        return p, len(s), (100 * p / len(s) if s else 0)

    print("\n" + "=" * 60)
    print(f"GOLDEN SET  ({len(rows)} cases, {time.time() - t0:.0f}s)")
    for label, sel in [
        ("Answerable - overall", lambda r: r["want"] == A),
        ("   normal wording", lambda r: r["want"] == A and r["variant"] == "normal"),
        ("   reworded / paraphrased", lambda r: r["want"] == A and r["variant"] == "reworded"),
        ("Off-topic declined (no ticket)", lambda r: r["want"] == "offtopic"),
        ("Banking gaps escalated (ticket)", lambda r: r["want"] == "escalate"),
    ]:
        p, n, pc = pct(sel)
        print(f"  {label:34} {p:2}/{n:2}  ({pc:.0f}%)")
    overall = sum(r["pass"] for r in rows)
    print(f"\n  OVERALL end-to-end: {overall}/{len(rows)} ({100 * overall / len(rows):.0f}%)")
    (Path(__file__).with_name("golden_results.json")).write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
