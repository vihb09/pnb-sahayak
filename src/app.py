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
import asyncio
import base64
import json
import os
import re
import time
import urllib.parse
from collections import Counter

from fastapi import FastAPI, File, Form, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from pathlib import Path

from sarvamai import AsyncSarvamAI

import sarvam_client as sc
from assistant import Assistant, POLITE_OFFTOPIC, VOICE_LANGS
from interaction_log import log_interaction, LOG_FILE
from escalation import send_escalation
from emailer import send_email


def _truthy(v):
    return str(v).lower() in ("1", "true", "yes", "on")

WEB_DIR = Path(__file__).resolve().parent / "web"

app = FastAPI(title="PNB Sahayak")
bot = Assistant()   # builds the document search index once, at startup
# Separate async client just for the optional live-streaming demo (Phase 7).
_async_sarvam = AsyncSarvamAI(api_subscription_key=os.getenv("SARVAM_API_KEY") or "")


def _guess_language(text: str) -> str:
    return "hi-IN" if re.search(r"[ऀ-ॿ]", text) else "en-IN"


def _empty_reply(transcript: str, language_code: str) -> dict:
    return {
        "transcript": transcript, "language_code": language_code, "style_label": "—",
        "query_en": "", "answer": POLITE_OFFTOPIC, "answer_en": POLITE_OFFTOPIC, "source": None,
        "confidence": "Low", "score": 0.0, "escalate": False, "kind": "offtopic",
        "tts_lang": "en-IN", "timings": {},
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
async def ask(audio: UploadFile = File(...), detail: str = Form("")):
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

        result = bot.answer(transcript, heard["language_code"], detail=_truthy(detail))
        result["timings"]["listen_ms"] = listen_ms
        return JSONResponse(_finalize(result, "voice"))
    except Exception as e:
        print("ERROR in /api/ask:", repr(e))
        return JSONResponse(_empty_reply("", "en-IN"))


@app.post("/api/ask_text")
async def ask_text(question: str = Form(""), language_code: str = Form(""), detail: str = Form("")):
    try:
        if not question.strip():
            return JSONResponse(_empty_reply(question, language_code or "en-IN"))
        language_code = language_code or _guess_language(question)
        result = bot.answer(question, language_code, detail=_truthy(detail))
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


@app.post("/api/email")
async def email(to: str = Form(...), text: str = Form(...), question: str = Form(""),
                source_label: str = Form(""), source_url: str = Form(""),
                language_code: str = Form("en-IN")):
    """Email an answer, translated into the chosen language. Sends via SMTP if
    configured, otherwise returns a mailto link for the browser to open."""
    try:
        # Assemble the full English email first, then translate the WHOLE thing so the
        # subject AND body share one language. (The source URL is added afterwards,
        # untranslated, so the link stays intact.)
        en_lines = []
        if question:
            en_lines.append(f"Question: {question}")
        en_lines.append(text)
        if source_label:
            en_lines.append(f"Source: {source_label}")
        en_lines.append("Sent via PNB Sahayak. Answers are grounded in official PNB documents.")
        en_body = "\n\n".join(en_lines)
        subject_phrase = "Answer to your question"

        if (language_code or "en").lower().startswith("en"):
            body = en_body
            subject = f"PNB Sahayak — {subject_phrase}"
        else:
            model = "mayura:v1" if language_code in VOICE_LANGS else "sarvam-translate:v1"
            try:
                body = sc.translate(en_body, language_code, source_language_code="en-IN", model=model)
            except Exception:
                body = en_body
            try:
                subj_local = sc.translate(subject_phrase, language_code, source_language_code="en-IN", model=model)
            except Exception:
                subj_local = subject_phrase
            subject = f"PNB Sahayak — {subj_local}"

        if source_url:
            body = body + "\n" + source_url

        ok, info = send_email(to, subject, body)
        resp = {"sent": ok, "info": info}
        if not ok:
            resp["mailto"] = ("mailto:" + urllib.parse.quote(to) + "?subject="
                              + urllib.parse.quote(subject) + "&body=" + urllib.parse.quote(body))
        return JSONResponse(resp)
    except Exception as e:
        print("ERROR in /api/email:", repr(e))
        return JSONResponse({"sent": False, "info": "error"})


def _read_log():
    records = []
    if LOG_FILE.exists():
        for line in LOG_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except Exception:
                pass
    return records


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    return (WEB_DIR / "dashboard.html").read_text(encoding="utf-8")


@app.get("/api/stats")
def stats():
    recs = _read_log()
    total = len(recs)
    answered = sum(1 for r in recs if r.get("answered"))
    escalated = sum(1 for r in recs if r.get("escalated"))
    langs = Counter((r.get("style") or r.get("language_code") or "—") for r in recs)
    conf = Counter((r.get("confidence") or "—") for r in recs if r.get("answered"))
    chan = Counter((r.get("channel") or "—") for r in recs)

    def pick(r, keys):
        return {k: r.get(k) for k in keys}

    keys = ("ts", "question", "style", "language_code", "confidence", "source_pdf",
            "escalated", "ticket_id")
    recent = [pick(r, keys) for r in recs[-12:]][::-1]
    escalations = [pick(r, ("ts", "question", "style", "ticket_id"))
                   for r in recs if r.get("escalated")][::-1][:12]

    return {
        "total": total,
        "answered": answered,
        "escalated": escalated,
        "answer_rate": round(100 * answered / total) if total else 0,
        "by_confidence": {k: conf.get(k, 0) for k in ("High", "Medium", "Low")},
        "by_language": sorted(({"name": k, "count": v} for k, v in langs.items()),
                              key=lambda x: -x["count"]),
        "by_channel": {"voice": chan.get("voice", 0), "text": chan.get("text", 0)},
        "recent": recent,
        "escalations": escalations,
    }


# ---------------------------------------------------------------------------
# Phase 7 (optional): live real-time streaming demo. Fully separate from the
# turn-by-turn assistant above — if it hiccups, nothing else is affected.
# ---------------------------------------------------------------------------
@app.get("/stream", response_class=HTMLResponse)
def stream_page():
    return (WEB_DIR / "stream.html").read_text(encoding="utf-8")


@app.websocket("/ws/transcribe")
async def ws_transcribe(browser: WebSocket):
    """Relay the browser's microphone PCM to Sarvam's streaming STT and send live
    transcripts back. The API key stays on the server."""
    await browser.accept()
    try:
        async with _async_sarvam.speech_to_text_streaming.connect(
            model="saaras:v3", mode="transcribe", language_code="unknown",  # auto-detect any language
            input_audio_codec="pcm_s16le", sample_rate="16000", high_vad_sensitivity="true",
        ) as sarvam_ws:

            async def to_sarvam():
                try:
                    while True:
                        chunk = await browser.receive_bytes()
                        await sarvam_ws.transcribe(audio=base64.b64encode(chunk).decode())
                except WebSocketDisconnect:
                    pass
                except Exception as e:
                    print("stream to_sarvam:", repr(e))
                finally:
                    try:
                        await sarvam_ws.flush()
                    except Exception:
                        pass

            async def to_browser():
                try:
                    async for msg in sarvam_ws:
                        data = getattr(msg, "data", None)
                        tr = getattr(data, "transcript", None) if data is not None else None
                        sig = getattr(data, "signal_type", None) if data is not None else None
                        if tr:
                            await browser.send_json({"type": "transcript", "text": tr})
                        elif sig:
                            await browser.send_json({"type": "signal", "signal": sig})
                except Exception as e:
                    print("stream to_browser:", repr(e))

            t1 = asyncio.create_task(to_sarvam())
            t2 = asyncio.create_task(to_browser())
            _done, pending = await asyncio.wait({t1, t2}, return_when=asyncio.FIRST_COMPLETED)
            for t in pending:
                t.cancel()
    except Exception as e:
        print("ws_transcribe error:", repr(e))
    finally:
        try:
            await browser.close()
        except Exception:
            pass


if __name__ == "__main__":
    import uvicorn
    print("PNB Sahayak is starting...  open  http://127.0.0.1:8000  in your browser.")
    uvicorn.run(app, host="127.0.0.1", port=8000)
