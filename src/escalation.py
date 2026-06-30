"""
escalation.py  -  the agentic escalation step (Phase 4).

When the assistant can't answer a genuine policy question, this:
  1. creates a follow-up ticket and appends it to logs/escalations.jsonl
     (a local "ticket queue" — works with zero setup), and
  2. if N8N_WEBHOOK_URL is set in .env, also POSTs the ticket to your n8n
     workflow (the visual no-code automation), fire-and-forget.

Nothing here ever raises — escalation must not break the assistant.
"""
import json
import os
import secrets
import threading
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

PROJECT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_DIR / ".env")

ESC_DIR = PROJECT_DIR / "logs"
ESC_FILE = ESC_DIR / "escalations.jsonl"


def _ticket_id() -> str:
    return f"PNB-{time.strftime('%Y%m%d')}-{secrets.token_hex(2).upper()}"


def send_escalation(result: dict, channel: str) -> dict:
    """Create a ticket for an unanswered question; log it and forward to n8n."""
    ticket = {
        "ticket_id": _ticket_id(),
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "status": "open",
        "channel": channel,                       # "voice" or "text"
        "question": result.get("transcript", ""),
        "language": result.get("style_label"),
        "confidence": result.get("confidence"),
        "reason": "No matching PNB policy document found",
        "assigned_to": "Policy Team",
    }

    # 1) local ticket queue (always)
    try:
        ESC_DIR.mkdir(exist_ok=True)
        with open(ESC_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(ticket, ensure_ascii=False) + "\n")
    except Exception:
        pass

    # 2) n8n webhook (only if configured) — fire in a background thread so the
    #    user's reply is never delayed by the webhook round-trip.
    url = os.getenv("N8N_WEBHOOK_URL")
    if url:
        def _post():
            try:
                requests.post(url, json=ticket, timeout=10)
            except Exception:
                pass
        threading.Thread(target=_post, daemon=True).start()

    return ticket
