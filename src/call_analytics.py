"""
call_analytics.py  -  Phase 6: offline post-call analytics.

Takes a recorded conversation and produces:
  1. a diarised transcript (who said what, with timestamps)   [Saaras batch STT + diarization]
  2. per-speaker speaking time
  3. an LLM summary: topics, sentiment, resolution, follow-ups [sarvam-30b]

This runs OFFLINE and is fully separate from the live app, so it can never affect
the demo. For convenience it can synthesise a sample 2-speaker PNB call with Bulbul.

Run from the project root:   py src/call_analytics.py
"""
import io
import json
import os
import sys
import wave
from pathlib import Path

from dotenv import load_dotenv
from sarvamai import SarvamAI

PROJECT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_DIR / ".env")
sys.path.insert(0, str(PROJECT_DIR / "src"))
import sarvam_client as sc  # noqa: E402

CALLS_DIR = PROJECT_DIR / "data" / "calls"
client = SarvamAI(api_subscription_key=os.getenv("SARVAM_API_KEY"))

# A short sample call: customer (priya) <-> bank agent (shubh).
DIALOGUE = [
    ("priya", "Hello, I am a retired employee of the bank. When do I need to submit my life certificate?"),
    ("shubh", "Hello madam. You must submit your life certificate every November to keep your pension active."),
    ("priya", "I will be travelling in November. Can I get a little more time?"),
    ("shubh", "Yes, there was an extension allowing submission up to December. Please check the latest circular."),
    ("priya", "Also, can retirees take a loan to pay the medical insurance premium?"),
    ("shubh", "Yes, retirees can take a personal loan to pay the IBA group medical insurance premium."),
    ("priya", "That is very helpful. Thank you so much."),
    ("shubh", "You are welcome. Have a good day."),
]


def make_sample_call(path: Path) -> Path:
    print("Synthesising a sample 2-speaker call with Bulbul...")
    clips = [sc.speak(line, "en-IN", speaker=spk) for spk, line in DIALOGUE]
    params, frames = None, []
    for wb in clips:
        with wave.open(io.BytesIO(wb)) as w:
            if params is None:
                params = w.getparams()
            frames.append(w.readframes(w.getnframes()))
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as out:
        out.setparams(params)
        for f in frames:
            out.writeframes(f)
    print(f"  saved {path}")
    return path


def transcribe_diarized(audio_path: Path, num_speakers: int = 2):
    job = client.speech_to_text_job.create_job(
        model="saaras:v3", mode="transcribe",
        with_diarization=True, with_timestamps=True,
        num_speakers=num_speakers, language_code="en-IN",
    )
    print(f"STT batch job {job.job_id}: uploading + processing (diarization on)...")
    job.upload_files([str(audio_path)])
    job.start()
    status = job.wait_until_complete(poll_interval=5, timeout=600)
    print("  job state:", getattr(status, "job_state", status))

    out_dir = CALLS_DIR / "stt_out"
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.json"):
        old.unlink()
    job.download_outputs(str(out_dir))
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(out_dir.glob("*.json"))]


def parse_entries(json_objs: list):
    """Pull diarised lines from the downloaded result JSON. Dumps raw shape if unrecognised."""
    entries = []
    for res in json_objs:
        for r in (res if isinstance(res, list) else [res]):
            if not isinstance(r, dict):
                continue
            dt = r.get("diarized_transcript") or {}
            ent = dt.get("entries") or r.get("entries") or []
            for e in ent:
                entries.append({
                    "speaker": e.get("speaker_id") or e.get("speaker") or "?",
                    "text": (e.get("transcript") or e.get("text") or "").strip(),
                    "start": e.get("start_time_seconds"),
                    "end": e.get("end_time_seconds"),
                })
            if not ent and r.get("transcript"):
                entries.append({"speaker": "?", "text": r["transcript"].strip(),
                                "start": None, "end": None})
    if not entries and json_objs:
        print("\n[debug] could not find diarised entries; raw first output JSON:")
        print(json.dumps(json_objs[0], indent=2, ensure_ascii=False)[:3000])
    return entries


def summarise(transcript_text: str) -> str:
    system = ("You analyse a recorded bank call between a customer and a PNB staff member. "
              "Be concise and factual.")
    user = (f"CALL TRANSCRIPT:\n{transcript_text}\n\n"
            "Give a short analysis with these headings:\n"
            "1. Topics discussed\n2. Customer sentiment\n3. Resolution / outcome\n"
            "4. Follow-up actions (if any)")
    return sc.think(system, user, max_tokens=400)


def main():
    audio = CALLS_DIR / "sample_call.wav"
    if not audio.exists():
        make_sample_call(audio)

    results = transcribe_diarized(audio, num_speakers=2)
    entries = parse_entries(results)

    # Build a readable transcript + per-speaker speaking time.
    lines, talk_time = [], {}
    for e in entries:
        tag = str(e["speaker"])
        stamp = ""
        if e["start"] is not None and e["end"] is not None:
            stamp = f"[{e['start']:.1f}-{e['end']:.1f}s] "
            talk_time[tag] = talk_time.get(tag, 0.0) + (e["end"] - e["start"])
        lines.append(f"{stamp}Speaker {tag}: {e['text']}")
    transcript_text = "\n".join(lines)

    print("\n===== DIARISED TRANSCRIPT =====")
    print(transcript_text or "(no transcript)")
    print("\n===== SPEAKING TIME =====")
    for spk, secs in talk_time.items():
        print(f"  Speaker {spk}: {secs:.1f}s")

    print("\n===== LLM SUMMARY =====")
    summary = summarise(transcript_text) if transcript_text else "(no transcript to summarise)"
    print(summary)

    # Save a report.
    report = (f"# Post-call analysis — {audio.name}\n\n## Diarised transcript\n\n```\n{transcript_text}\n```\n\n"
              f"## Speaking time\n\n" + "".join(f"- Speaker {s}: {t:.1f}s\n" for s, t in talk_time.items())
              + f"\n## Summary\n\n{summary}\n")
    (CALLS_DIR / "sample_call_report.md").write_text(report, encoding="utf-8")
    print(f"\nReport saved to {CALLS_DIR / 'sample_call_report.md'}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
