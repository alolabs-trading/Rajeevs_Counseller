"""
main.py — FastAPI WebSocket gateway for Zen Counselor V1.

Run:
    uvicorn main:app --reload --port 8000

WebSocket endpoint: ws://localhost:8000/ws/session

Message protocol (JSON):

  Client → Server:
    { "type": "audio_chunk", "audio": "<base64 webm>", "mimetype": "audio/webm" }
    { "type": "end_session" }
    { "type": "cancel" }

  Server → Client:
    { "type": "status",         "state": "listening|transcribing|thinking|speaking|idle|error" }
    { "type": "transcript",     "text": "..." }
    { "type": "sentence_text",  "text": "...", "index": 0 }
    { "type": "sentence_audio", "audio": "<base64 mp3>", "format": "mp3", "index": 0 }
    { "type": "response_done",  "full_text": "..." }
    { "type": "error",          "message": "..." }
"""

import os
import base64
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv

load_dotenv()

from pipeline import process_turn_streaming


# ─── App setup ───────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Zen Counselor backend started")
    yield
    print("Zen Counselor backend stopped")

app = FastAPI(title="Zen Counselor API", lifespan=lifespan)

# Serve the frontend
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/")
async def root():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


# ─── Session state ───────────────────────────────────────────────────────────

class CounselorSession:
    """Holds per-connection state."""
    def __init__(self, websocket: WebSocket):
        self.ws = websocket
        self.history: list[dict] = []
        self.is_processing = False
        self.cancelled = False

    async def send(self, data: dict):
        try:
            await self.ws.send_json(data)
        except Exception:
            pass

    async def set_status(self, state: str):
        await self.send({"type": "status", "state": state})

    def append_history(self, transcript: str, response: str):
        self.history.append({"role": "user", "content": transcript})
        self.history.append({"role": "assistant", "content": response})
        # Keep last 20 turns (10 exchanges)
        if len(self.history) > 20:
            self.history = self.history[-20:]


# ─── WebSocket endpoint ───────────────────────────────────────────────────────

@app.websocket("/ws/session")
async def websocket_session(websocket: WebSocket):
    await websocket.accept()
    session = CounselorSession(websocket)

    print(f"New session connected: {websocket.client}")
    await session.set_status("listening")

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "cancel":
                session.cancelled = True
                await session.set_status("listening")
                continue

            if msg_type == "end_session":
                await session.set_status("idle")
                break

            if msg_type == "audio_chunk":
                if session.is_processing:
                    continue

                session.is_processing = True
                session.cancelled = False

                try:
                    audio_b64 = data.get("audio", "")
                    mimetype = data.get("mimetype", "audio/webm")

                    if not audio_b64:
                        await session.set_status("listening")
                        session.is_processing = False
                        continue

                    audio_bytes = base64.b64decode(audio_b64)

                    # ── Run streaming pipeline ───────────────────────
                    await session.set_status("transcribing")
                    full_text = ""
                    user_transcript = ""
                    first_audio_sent = False

                    async for event in process_turn_streaming(
                        audio_bytes, session.history, mimetype
                    ):
                        if session.cancelled:
                            await session.set_status("listening")
                            break

                        if event["event"] == "transcript":
                            user_transcript = event["text"]
                            await session.send({
                                "type": "transcript",
                                "text": event["text"],
                            })
                            await session.set_status("thinking")

                        elif event["event"] == "sentence_text":
                            await session.send({
                                "type": "sentence_text",
                                "text": event["text"],
                                "index": event["index"],
                            })

                        elif event["event"] == "sentence_audio":
                            if not first_audio_sent:
                                await session.set_status("speaking")
                                first_audio_sent = True

                            await session.send({
                                "type": "sentence_audio",
                                "audio": base64.b64encode(event["audio"]).decode(),
                                "format": "mp3",
                                "index": event["index"],
                            })

                        elif event["event"] == "done":
                            full_text = event["full_text"]
                            await session.send({
                                "type": "response_done",
                                "full_text": full_text,
                            })

                    # Update history with the complete exchange
                    if full_text and not session.cancelled:
                        session.append_history(user_transcript, full_text)

                except ValueError:
                    # No speech detected
                    await session.set_status("listening")

                except Exception as e:
                    print(f"Pipeline error: {e}")
                    err_str = str(e)
                    if "overloaded" in err_str.lower():
                        msg = "सध्या खूप रहदारी आहे, थोड्या वेळाने पुन्हा प्रयत्न करा."
                    elif "credit" in err_str.lower() or "billing" in err_str.lower():
                        msg = "API credit संपले आहेत."
                    else:
                        msg = "काहीतरी चुकलं. पुन्हा प्रयत्न करा."
                    await session.send({"type": "error", "message": msg})
                    await session.set_status("listening")

                finally:
                    session.is_processing = False

    except WebSocketDisconnect:
        print(f"Session disconnected: {websocket.client}")
    except Exception as e:
        print(f"Session error: {e}")
    finally:
        print("Session cleaned up")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "zen-counselor",
        "version": "1.1.0",
    }
