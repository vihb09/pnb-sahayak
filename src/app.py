"""
app.py  -  the web server for PNB Sahayak (the voice assistant).

Two-phase for speed: the answer text + source come back first (fast), then the
browser asks for the spoken audio separately so you SEE the answer right away.

  POST /api/ask       : microphone audio (WAV) -> transcript + answer + timings
  POST /api/ask_text  : typed question         -> answer + timings
  POST /api/speak     : text + language        -> spoken audio (base64 WAV)
  GET  /api/info      : status + how many real documents are loaded

Run from the project root:   py src/app.py    ->   http://127.0.0.1:8000
"""
import base64
import re
import time

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from pathlib import Path

import sarvam_client as sc
from assistant import Assistant, POLITE_OFFTOPIC
from interaction_log import log_interaction
from escalation import send_escalation

WEB_DIR = Path(__file__).resolve().parent / "web"

app = FastAPI(title="PNB Sahayak")
bot = Assistant()   # builds the document search index once, at startup


def _guess_language(text: str) -> str:
    return "hi-IN" if re.search(r"[ऀ-ॿ]", text) else "en-IN"


def _empty_reply(transcript: str, language_code: str) -> dict:
    return {
        "transcript": transcript, "language_code": language_code, "style_label": "—",
        "query_en": "", "answer": POLITE_OFFTOPIC, "answer_en": POLITE_OFFTOPIC, "source": None,
        "confidence": "Low", "score": 0.0, "escalate": False, "tts_lang": "en-IN",
        "timings": {},
    }


def _finalize(result: dict, channel: str) -> dict:
    """Create a ticket if escalating, then log the interaction."""
    if result.get("escalate"):
        ticket = send_escalation(result, channel)
        result["ticket_id"] = ticket["ticket_id"]
    log_interaction(result, channel)
    return result


@app.get("/", response_class=HTMLResponse)
def index():
    return (WEB_DIR / "index.html").read_text(encoding="utf-8")


@app.get("/api/info")
def info():
    return {"status": "ready", "num_documents": bot.kb.num_documents,
            "num_passages": len(bot.kb.chunks)}


@app.post("/api/ask")
async def ask(audio: UploadFile = File(...)):
    try:
        audio_bytes = await audio.read()
        t = time.time()
        heard = sc.listen(audio_bytes, filename=audio.filename or "recording.wav",
                          content_type=audio.content_type or "audio/wav")
        listen_ms = int((time.time() - t) * 1000)

        transcript = heard["transcript"]
        if not transcript:
            r = _empty_reply("", heard["language_code"])
            r["answer"] = r["answer_en"] = "Sorry, I could not hear any speech. Please try again."
            r["timings"] = {"listen_ms": listen_ms}
            return JSONResponse(r)

        result = bot.answer(transcript, heard["language_code"])
        result["timings"]["listen_ms"] = listen_ms
        return JSONResponse(_finalize(result, "voice"))
    except Exception as e:
        print("ERROR in /api/ask:", repr(e))
        return JSONResponse(_empty_reply("", "en-IN"))


@app.post("/api/ask_text")
async def ask_text(question: str = Form(""), language_code: str = Form("")):
    try:
        if not question.strip():
            return JSONResponse(_empty_reply(question, language_code or "en-IN"))
        language_code = language_code or _guess_language(question)
        result = bot.answer(question, language_code)
        return JSONResponse(_finalize(result, "text"))
    except Exception as e:
        print("ERROR in /api/ask_text:", repr(e))
        return JSONResponse(_empty_reply(question, "en-IN"))


@app.post("/api/speak")
async def speak(text: str = Form(...), language_code: str = Form("en-IN")):
    try:
        t = time.time()
        wav = sc.speak(text, language_code)
        return JSONResponse({"audio_base64": base64.b64encode(wav).decode(),
                             "speak_ms": int((time.time() - t) * 1000)})
    except Exception as e:
        print("ERROR in /api/speak:", repr(e))
        return JSONResponse({"audio_base64": "", "speak_ms": 0})


if __name__ == "__main__":
    import uvicorn
    print("PNB Sahayak is starting...  open  http://127.0.0.1:8000  in your browser.")
    uvicorn.run(app, host="127.0.0.1", port=8000)
