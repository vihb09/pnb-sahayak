"""
sarvam_client.py  -  a small, plain "toolbox" of the four Sarvam abilities.

Each function is one web call to Sarvam, using the endpoints/model names verified
in docs/sarvam-api-reference.md. The API key is read from the private .env file
and is never printed.

  listen()    -> Saaras       : spoken audio  -> text (+ detected language)
  translate() -> Mayura       : text -> text in another language
  think()     -> sarvam-30b   : read context + question -> written answer
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
CHAT_MODEL = "sarvam-30b"   # Sarvam recommends the 30B for voice / low-latency pipelines
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


def translate(text: str, target_language_code: str, source_language_code: str = "auto") -> str:
    """Mayura translation. 'auto' source lets Sarvam detect the input language."""
    if not text.strip():
        return text
    r = requests.post(
        f"{BASE_URL}/translate",
        headers=JSON_HEADERS,
        json={
            "input": text[:1000],  # mayura:v1 limit
            "source_language_code": source_language_code,
            "target_language_code": target_language_code,
            "model": "mayura:v1",
        },
        timeout=60,
    )
    r.raise_for_status()
    return (r.json().get("translated_text") or text).strip()


def think(system_prompt: str, user_prompt: str, max_tokens: int = 400, temperature: float = 0.2,
          reasoning_effort=None) -> str:
    """sarvam-30b chat completion. Returns the assistant's text.
    reasoning_effort=None keeps replies fast (no 'thinking' pause) for the voice flow."""
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


def speak(text: str, target_language_code: str = "en-IN", speaker: str = "shubh") -> bytes:
    """Bulbul text-to-speech. Returns WAV audio bytes."""
    r = requests.post(
        f"{BASE_URL}/text-to-speech",
        headers=JSON_HEADERS,
        json={
            "text": text[:2500],  # bulbul:v3 limit
            "target_language_code": target_language_code,
            "speaker": speaker,
            "model": "bulbul:v3",
        },
        timeout=90,
    )
    r.raise_for_status()
    return base64.b64decode(r.json()["audios"][0])


# --- quick test of the two abilities we haven't exercised yet ---
if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print("1) Translate English -> Hindi:")
    hi = translate("What documents are required to open a new bank account?", "hi-IN")
    print("   ", hi)

    print("\n2) Translate that Hindi back -> English:")
    print("   ", translate(hi, "en-IN"))

    print("\n3) Ask sarvam-30b a grounded question:")
    answer = think(
        system_prompt="Answer ONLY from the context. If the answer is not in the context, say you don't know.",
        user_prompt="Context: A savings account requires a PAN card and an Aadhaar card.\n\nQuestion: What two documents are needed for a savings account?",
    )
    print("   ", answer)
