"""
sarvam_client.py  -  a small, plain "toolbox" of the four Sarvam abilities.

Each function is one web call to Sarvam, using the endpoints/model names verified
in docs/sarvam-api-reference.md. The API key is read from the private .env file
and is never printed.

  listen()    -> Saaras       : spoken audio  -> text (+ detected language)
  translate() -> Mayura       : text -> text in another language
  think()     -> sarvam-105b  : read context + question -> written answer
  speak()     -> Bulbul       : text -> spoken audio
"""
import base64
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

PROJECT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_DIR / ".env")

API_KEY = os.getenv("SARVAM_API_KEY")
BASE_URL = "https://api.sarvam.ai"
CHAT_MODEL = "sarvam-105b"   # migrated from sarvam-30b (deprecated 26 Jul 2026); same API
AUTH = {"api-subscription-key": API_KEY or ""}
JSON_HEADERS = {**AUTH, "Content-Type": "application/json"}


def listen(audio_bytes: bytes, filename: str = "audio.wav", content_type: str = "audio/wav") -> dict:
    """Saaras speech-to-text. Returns {'transcript', 'language_code'}."""
    r = requests.post(
        f"{BASE_URL}/speech-to-text",
        headers=AUTH,
        files={"file": (filename, audio_bytes, content_type)},
        data={"model": "saaras:v3"},
        timeout=90,
    )
    r.raise_for_status()
    data = r.json()
    return {
        "transcript": (data.get("transcript") or "").strip(),
        "language_code": data.get("language_code") or "en-IN",
    }


def _chunks(text: str, limit: int):
    """Split text into pieces under `limit` chars, preferring line boundaries so bullets
    and paragraphs stay intact (a single over-long line is hard-split as a last resort)."""
    out, cur = [], ""
    for ln in text.split("\n"):
        if len(ln) > limit:
            if cur:
                out.append(cur); cur = ""
            for i in range(0, len(ln), limit):
                out.append(ln[i:i + limit])
            continue
        if cur and len(cur) + len(ln) + 1 > limit:
            out.append(cur); cur = ln
        else:
            cur = (cur + "\n" + ln) if cur else ln
    if cur:
        out.append(cur)
    return out


def translate(text: str, target_language_code: str, source_language_code: str = "auto",
              model: str = "mayura:v1", mode: str | None = None,
              output_script: str | None = None) -> str:
    """Translate text. model 'mayura:v1' covers 11 languages and supports style
    (mode/output_script, e.g. code-mixed + roman for Hinglish); 'sarvam-translate:v1'
    covers the wider 22-language set (no style options). Text longer than the model's
    character limit is translated in chunks so nothing is silently truncated."""
    if not text.strip():
        return text
    is_mayura = model.startswith("mayura")
    limit = 1000 if is_mayura else 2000

    def _one(seg: str) -> str:
        body = {
            "input": seg,
            "source_language_code": source_language_code,
            "target_language_code": target_language_code,
            "model": model,
        }
        if is_mayura:
            if mode:
                body["mode"] = mode
            if output_script:
                body["output_script"] = output_script
        r = requests.post(f"{BASE_URL}/translate", headers=JSON_HEADERS, json=body, timeout=45)
        r.raise_for_status()
        return (r.json().get("translated_text") or seg).strip()

    if len(text) <= limit:
        return _one(text)
    return "\n".join(_one(c) for c in _chunks(text, limit))


def think(system_prompt: str, user_prompt: str, max_tokens: int = 400, temperature: float = 0.2,
          reasoning_effort=None) -> str:
    """sarvam-105b chat completion. Returns the assistant's text.

    reasoning_effort=None disables the model's 'thinking' step -> fast, direct answer.
    IMPORTANT: this None must be SENT as JSON null (which it is below); it is the ONLY
    way to switch reasoning off. Measured on sarvam-105b (Jul 2026): omitting the field,
    or any of 'low'/'medium'/'high', turns reasoning ON -> ~2x latency (1.5s -> 2.5-3.3s)
    and ~3x output tokens, and with our small max_tokens the thinking eats the whole
    budget so message.content comes back empty. Keep this None for the voice flow."""
    r = requests.post(
        f"{BASE_URL}/v1/chat/completions",
        headers=JSON_HEADERS,
        json={
            "model": CHAT_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "reasoning_effort": reasoning_effort,  # None = no 'thinking' -> fast direct answer
        },
        timeout=120,
    )
    r.raise_for_status()
    message = r.json()["choices"][0]["message"]
    return (message.get("content") or message.get("reasoning_content") or "").strip()


def speak(text: str, target_language_code: str = "en-IN", speaker: str = "shubh",
          pace: float = 0.95) -> bytes:
    """Bulbul text-to-speech. Returns WAV audio bytes.

    enable_preprocessing makes Bulbul read numbers, dates and mixed-language text the way a
    person would (a big part of sounding natural), and a slightly gentler pace is less robotic.
    (pitch/loudness are not supported on bulbul:v3.)

    Resilience: TTS is the slowest step and Sarvam occasionally hangs/times out when the
    service is busy (not language-specific — measured Aug 2026). We use a short per-attempt
    timeout and retry ONCE so a brief slowdown self-heals instead of returning silent audio.
    Only transient failures are retried (timeout, connection drop, 5xx); a 4xx such as an
    invalid speaker is raised immediately since a retry cannot help."""
    body = {
        "text": text[:2500],  # bulbul:v3 limit
        "target_language_code": target_language_code,
        "speaker": speaker,
        "model": "bulbul:v3",
        "pace": pace,
        "enable_preprocessing": True,
        "speech_sample_rate": 16000,   # smaller WAV -> quicker to stream over a tunnel
    }
    last_err = None
    for attempt in range(2):   # 1 try + 1 retry
        try:
            r = requests.post(f"{BASE_URL}/text-to-speech", headers=JSON_HEADERS,
                              json=body, timeout=20)   # fail fast, then retry (was a single 90s wait)
        except requests.RequestException as e:         # timeout / connection error -> retry
            last_err = e
            continue
        if r.status_code < 300:
            return base64.b64decode(r.json()["audios"][0])
        if r.status_code < 500:                        # client error (e.g. bad speaker) -> no retry
            r.raise_for_status()
        last_err = f"HTTP {r.status_code}: {r.text[:120]}"   # 5xx -> loop and retry
    raise RuntimeError(f"text-to-speech failed after retry: {last_err}")


# --- quick test of the two abilities we haven't exercised yet ---
if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print("1) Translate English -> Hindi:")
    hi = translate("What documents are required to open a new bank account?", "hi-IN")
    print("   ", hi)

    print("\n2) Translate that Hindi back -> English:")
    print("   ", translate(hi, "en-IN"))

    print("\n3) Ask sarvam-105b a grounded question:")
    answer = think(
        system_prompt="Answer ONLY from the context. If the answer is not in the context, say you don't know.",
        user_prompt="Context: A savings account requires a PAN card and an Aadhaar card.\n\nQuestion: What two documents are needed for a savings account?",
    )
    print("   ", answer)
