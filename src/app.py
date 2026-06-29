"""
app.py  -  the web server for PNB Sahayak (the voice assistant).

Serves one web page (the mic + "show the work" panel) and connects it to the
answer brain:

  POST /api/ask       : microphone audio -> listen -> answer -> speak -> JSON
  POST /api/ask_text  : typed question   ->        answer -> speak -> JSON
  GET  /api/info      : how many real documents are loaded

Run it from the project root with:   py src/app.py
Then open http://127.0.0.1:8000 in your browser.
"""
import base64
import re
import time
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse

import sarvam_client as sc
from assistant import Assistant

WEB_DIR = Path(__file__).resolve().parent / "web"

app = FastAPI(title="PNB Sahayak")
bot = Assistant()   # builds the document search index once, at startup


def _guess_language(text: str) -> str:
    """Very simple: any Devanagari letter -> Hindi, otherwise English."""
    return "hi-IN" if re.search(r"[ऀ-ॿ]", text) else "en-IN"


def _speak_safe(text: str, language_code: str) -> str:
    """Turn the answer into speech (base64 WAV). Returns '' if TTS fails."""
    try:
        wav = sc.speak(text, language_code)
        return base64.b64encode(wav).decode()
    except Exception:
        return ""


def _package(result: dict, transcript: str, language_code: str, timings: dict) -> dict:
    t = time.time()
    audio_b64 = _speak_safe(result["answer"], language_code)
    timings["speak_ms"] = int((time.time() - t) * 1000)
    return {
        "transcript": transcript,
        "language_code": language_code,
        "query_en": result.get("query_en", ""),
        "answer": result["answer"],
        "answer_en": result.get("answer_en", ""),
        "source": result.get("source"),
        "confidence": result.get("confidence"),
        "score": result.get("score"),
        "audio_base64": audio_b64,
        "timings": timings,
    }


@app.get("/", response_class=HTMLResponse)
def index():
    return (WEB_DIR / "index.html").read_text(encoding="utf-8")


@app.get("/api/info")
def info():
    return {"num_documents": bot.kb.num_documents, "num_passages": len(bot.kb.chunks)}


@app.post("/api/ask")
async def ask(audio: UploadFile = File(...)):
    audio_bytes = await audio.read()
    timings = {}

    t = time.time()
    heard = sc.listen(
        audio_bytes,
        filename=audio.filename or "recording.webm",
        content_type=audio.content_type or "audio/webm",
    )
    timings["listen_ms"] = int((time.time() - t) * 1000)

    transcript = heard["transcript"]
    language_code = heard["language_code"]
    if not transcript:
        return JSONResponse({
            "transcript": "",
            "answer": "Sorry, I could not hear any speech. Please try again.",
            "source": None, "confidence": None, "audio_base64": "",
            "language_code": language_code, "timings": timings,
        })

    t = time.time()
    result = bot.answer(transcript, language_code)
    timings["think_ms"] = int((time.time() - t) * 1000)
    return JSONResponse(_package(result, transcript, language_code, timings))


@app.post("/api/ask_text")
async def ask_text(question: str = Form(...), language_code: str = Form("")):
    language_code = language_code or _guess_language(question)
    timings = {}
    t = time.time()
    result = bot.answer(question, language_code)
    timings["think_ms"] = int((time.time() - t) * 1000)
    return JSONResponse(_package(result, question, language_code, timings))


if __name__ == "__main__":
    import uvicorn
    print("PNB Sahayak is starting...  open  http://127.0.0.1:8000  in your browser.")
    uvicorn.run(app, host="127.0.0.1", port=8000)
