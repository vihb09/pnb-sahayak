"""
interaction_log.py  -  a simple append-only record of every question asked.

Each line in logs/interactions.jsonl is one interaction (question, language,
confidence, source, whether it was answered or escalated). This "prepares to
escalate" (Phase 4 reads the escalated ones) and feeds the Phase 5 dashboard.
Writing never raises — logging must not break the assistant.
"""
import json
import time
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_FILE = LOG_DIR / "interactions.jsonl"


def log_interaction(result: dict, channel: str) -> None:
    try:
        LOG_DIR.mkdir(exist_ok=True)
        source = result.get("source") or {}
        record = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "channel": channel,                       # "voice" or "text"
            "question": result.get("transcript", ""),
            "language_code": result.get("language_code"),
            "style": result.get("style_label"),
            "confidence": result.get("confidence"),
            "score": result.get("score"),
            "source_pdf": source.get("pdf"),
            "source_url": source.get("url"),
            "answered": bool(source.get("pdf")),   # a real answer always has a source
            "escalated": bool(result.get("escalate", False)),
            "ticket_id": result.get("ticket_id"),
        }
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass
