"""
sarvam_check.py  —  Sarvam connection test.

Proves two things in one round-trip:
  1. Bulbul (text-to-speech): we send a sentence, Sarvam sends back spoken audio.
  2. Saaras (speech-to-text): we send that audio back, Sarvam writes it as text.

If the text that comes back resembles what we sent, the key works and both
Sarvam tools are reachable. Your API key is read from the private .env file and
is never printed.
"""

import base64
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

# ---- Setup -----------------------------------------------------------------
PROJECT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_DIR / ".env")

API_KEY = os.getenv("SARVAM_API_KEY")
BASE_URL = "https://api.sarvam.ai"
AUTH_HEADER = {"api-subscription-key": API_KEY or ""}

SAMPLE_TEXT = "Hello Sarvam. The PNB voice assistant is now connected."
AUDIO_FILE = PROJECT_DIR / "data" / "sarvam_check.wav"


def fail(message, response=None):
    """Print a friendly error and stop."""
    print("\n[X] " + message)
    if response is not None:
        print(f"    HTTP status code : {response.status_code}")
        print(f"    Server response  : {response.text[:600]}")
    raise SystemExit(1)


def main():
    print("=" * 64)
    print(" HELLO SARVAM  -  Phase 1 connection test")
    print("=" * 64)

    # Guard: make sure a real key is present.
    if not API_KEY or API_KEY == "your_sarvam_api_key_here":
        fail("No real Sarvam API key found in the .env file.")
    print(f"\n[1/3] API key loaded from .env (kept secret; {len(API_KEY)} characters).")

    # ---- Bulbul: text -> speech -------------------------------------------
    print("\n[2/3] Asking Bulbul (text-to-speech) to speak this sentence:")
    print(f'      "{SAMPLE_TEXT}"')
    try:
        tts = requests.post(
            f"{BASE_URL}/text-to-speech",
            headers={**AUTH_HEADER, "Content-Type": "application/json"},
            json={
                "text": SAMPLE_TEXT,
                "target_language_code": "en-IN",
                "speaker": "shubh",
                "model": "bulbul:v3",
            },
            timeout=60,
        )
    except requests.exceptions.RequestException as e:
        fail(f"Could not reach Sarvam for text-to-speech (network problem): {e}")

    if tts.status_code != 200:
        fail("Bulbul (text-to-speech) call was rejected.", tts)

    audios = tts.json().get("audios")
    if not audios:
        fail(f"Bulbul returned no audio. Full response: {tts.json()}")

    AUDIO_FILE.parent.mkdir(parents=True, exist_ok=True)
    AUDIO_FILE.write_bytes(base64.b64decode(audios[0]))
    print(f"      [OK] Received spoken audio and saved it to:")
    print(f"           {AUDIO_FILE}")
    print(f"           (Double-click that file to hear it.)")

    # ---- Saaras: speech -> text -------------------------------------------
    print("\n[3/3] Sending that audio to Saaras (speech-to-text) to write it back...")
    try:
        with open(AUDIO_FILE, "rb") as audio:
            stt = requests.post(
                f"{BASE_URL}/speech-to-text",
                headers=AUTH_HEADER,
                files={"file": ("sarvam_check.wav", audio, "audio/wav")},
                data={"model": "saaras:v3"},
                timeout=60,
            )
    except requests.exceptions.RequestException as e:
        fail(f"Could not reach Sarvam for speech-to-text (network problem): {e}")

    if stt.status_code != 200:
        fail("Saaras (speech-to-text) call was rejected.", stt)

    result = stt.json()
    transcript = (result.get("transcript") or result.get("text") or "").strip()
    if not transcript:
        fail(f"Saaras returned no text. Full response: {result}")
    print(f'      [OK] Saaras heard: "{transcript}"')

    # ---- Verdict -----------------------------------------------------------
    print("\n" + "=" * 64)
    print(" SUCCESS  -  your Sarvam key works and both tools responded:")
    print("   * Bulbul turned text into speech")
    print("   * Saaras turned that speech back into text")
    print("=" * 64)


if __name__ == "__main__":
    main()
