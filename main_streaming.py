# main_streaming.py
"""
FastAPI WebSocket gateway for Zen Counselor V2.0 (Full Duplex).

This version supports:
- Continuous audio streaming (no hold button)
- Real-time VAD for automatic speech detection
- Full duplex (interrupt AI while speaking)
- Deepgram live streaming API

Run:
    uvicorn main_streaming:app --reload --port 8000

WebSocket endpoint: ws://localhost:8000/ws/streaming
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

from pipeline_streaming import (
    StreamingTranscriber,
    stream_counselor_sentences,
    expressive_tts,
    ConversationState,
)
from emotion import detect_context


# ─── App setup ───────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Zen Counselor V2.0 (Full Duplex) started")
    yield
    print("Zen Counselor V2.0 stopped")

app = FastAPI(title="Zen Counselor API V2", lifespan=lifespan)

# Serve the frontend
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
if not os.path.exists(FRONTEND_DIR):
    FRONTEND_DIR = os.path.dirname(__file__)

app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/")
async def root():
    index_path = os.path.join(FRONTEND_DIR, "index_streaming.html")
    if not os.path.exists(index_path):
        index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Zen Counselor V2.0", "endpoint": "/ws/streaming"}


# ─── Session Management ──────────────────────────────────────────────────────

class StreamingSession:
    """Manages a full-duplex streaming session."""
    
    def __init__(self, websocket: WebSocket):
        self.ws = websocket
        self.transcriber: StreamingTranscriber | None = None
        self.conversation_state = ConversationState()
        self.history: list[dict] = []
        self.language: str = "hi"
        self.is_active = False
        
    async def send(self, data: dict):
        """Send message to client."""
        try:
            await self.ws.send_json(data)
        except Exception as e:
            print(f"Send error: {e}")
    
    async def set_status(self, state: str):
        """Update session status."""
        await self.send({"type": "status", "state": state})
    
    async def on_interim_transcript(self, text: str, is_final: bool):
        """Handle interim transcript from Deepgram."""
        if is_final:
            await self.send({"type": "transcript_final", "text": text})
        else:
            await self.send({"type": "transcript_interim", "text": text})
    
    async def on_speech_ended(self, transcript: str):
        """Handle completed user utterance."""
        if not transcript.strip():
            return
        
        print(f"User said: {transcript}")
        self.conversation_state.user_stopped_speaking()
        await self.generate_response(transcript)
    
    async def generate_response(self, transcript: str):
        """Generate and stream AI response."""
        try:
            await self.set_status("thinking")
            context = detect_context(transcript)
            
            full_response = ""
            sentence_index = 0
            
            async def response_task():
                nonlocal full_response, sentence_index
                
                try:
                    async for sentence in stream_counselor_sentences(
                        transcript, self.history, self.language
                    ):
                        if self.conversation_state.should_interrupt():
                            print("Response interrupted")
                            await self.send({"type": "interrupted", "reason": "user_spoke"})
                            return
                        
                        full_response += (" " if full_response else "") + sentence
                        
                        await self.send({
                            "type": "response_text",
                            "text": sentence,
                            "index": sentence_index,
                        })
                        
                        if sentence_index == 0:
                            await self.set_status("speaking")
                        
                        audio = await expressive_tts(
                            sentence, context, self.language, sentence_index
                        )
                        
                        if self.conversation_state.should_interrupt():
                            return
                        
                        await self.send({
                            "type": "response_audio",
                            "audio": base64.b64encode(audio).decode(),
                            "index": sentence_index,
                        })
                        
                        sentence_index += 1
                    
                    if not self.conversation_state.should_interrupt():
                        self.history.append({"role": "user", "content": transcript})
                        self.history.append({"role": "assistant", "content": full_response})
                        if len(self.history) > 20:
                            self.history = self.history[-20:]
                
                finally:
                    self.conversation_state.ai_stopped_speaking()
                    if not self.conversation_state.user_speaking:
                        await self.set_status("listening")
            
            task = asyncio.create_task(response_task())
            self.conversation_state.ai_started_speaking(task)
            await task
        
        except asyncio.CancelledError:
            await self.set_status("listening")
        except Exception as e:
            print(f"Response error: {e}")
            await self.send({"type": "error", "message": str(e)})
            await self.set_status("listening")
    
    async def start_streaming(self):
        """Start the streaming transcriber."""
        self.transcriber = StreamingTranscriber(
            language=self.language,
            silence_threshold_ms=700
        )
        
        self.transcriber.on_transcript_callback = self.on_interim_transcript
        self.transcriber.on_speech_end_callback = self.on_speech_ended
        
        await self.transcriber.start()
        self.is_active = True
        print(f"Streaming started: {self.language}")
    
    async def stop_streaming(self):
        """Stop the streaming transcriber."""
        if self.transcriber:
            await self.transcriber.stop()
            self.transcriber = None
        self.is_active = False
    
    async def process_audio(self, audio_b64: str):
        """Process incoming audio stream."""
        if not self.transcriber or not self.is_active:
            return
        
        try:
            audio_bytes = base64.b64decode(audio_b64)
            
            if not self.conversation_state.user_speaking and len(audio_bytes) > 0:
                self.conversation_state.user_started_speaking()
            
            await self.transcriber.send_audio(audio_bytes)
        except Exception as e:
            print(f"Audio error: {e}")


# ─── WebSocket endpoint ──────────────────────────────────────────────────────

@app.websocket("/ws/streaming")
async def websocket_streaming(websocket: WebSocket):
    """Full-duplex streaming endpoint."""
    await websocket.accept()
    session = StreamingSession(websocket)
    
    print(f"New session: {websocket.client}")
    await session.set_status("idle")
    
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")
            
            if msg_type == "start_session":
                session.language = data.get("language", "hi")
                await session.start_streaming()
                await session.set_status("listening")
            
            elif msg_type == "audio_stream":
                audio_b64 = data.get("audio", "")
                if audio_b64:
                    await session.process_audio(audio_b64)
            
            elif msg_type == "end_session":
                await session.stop_streaming()
                await session.set_status("idle")
                break
    
    except WebSocketDisconnect:
        print(f"Disconnected: {websocket.client}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await session.stop_streaming()


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "version": "2.0.0",
        "features": ["streaming_stt", "full_duplex", "vad", "expressive_tts"]
    }
