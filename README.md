# Zen Voice Counselor — V1

A real-time voice-to-voice counselor app. You speak, it listens, responds as a calm
empathetic counselor named Aria. No chat box. No keyboard. Just a conversation.

**Stack:** Deepgram STT → Claude Sonnet → ElevenLabs TTS → FastAPI WebSocket → Browser

---

## Setup (5 minutes)

### 1. Get API keys

| Service | Free tier | Link |
|---|---|---|
| Anthropic | Pay-per-use | https://console.anthropic.com |
| Deepgram | 200 hrs/month free | https://console.deepgram.com |
| ElevenLabs | 10k chars/month free | https://elevenlabs.io |

### 2. Install dependencies

```bash
cd zen-counselor
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Set environment variables

```bash
cp .env.example .env
# Edit .env and paste your API keys
```

### 4. Run the backend

```bash
cd backend
uvicorn main:app --reload --port 8000
```

### 5. Open the app

Navigate to: http://localhost:8000

---

## How to use

1. Click **Start Session**
2. **Hold** the orb → speak → **release** to send
3. Wait ~1–2 seconds for Aria to respond
4. **Click** the orb while Aria is speaking to interrupt her
5. Click **End Session** when done

---

## Latency breakdown (typical)

| Stage | Time |
|---|---|
| Deepgram STT (nova-2) | ~300ms |
| Claude Sonnet (TTFT) | ~500–700ms |
| ElevenLabs turbo_v2 | ~200ms |
| **Total to first audio** | **~1.0–1.2 seconds** |

---

## Architecture

```
Browser (hold-to-talk)
  │  audio/webm (base64, WebSocket)
  ▼
FastAPI WebSocket gateway  (main.py)
  │
  ├── Deepgram nova-2 STT  →  transcript text
  │
  ├── Claude Sonnet        →  counselor response (≤250 tokens)
  │   (counselor persona from persona.py)
  │
  └── ElevenLabs turbo_v2  →  MP3 audio bytes
  │
  ▼
Browser plays audio response
```

---

## Customising the persona

Edit `backend/persona.py` to change Aria's personality, focus area, or response style.

Key parameters in `pipeline.py`:
- `max_tokens=250` — keep low for voice (longer = slower + unnatural)
- `temperature=0.7` — lower for more consistent tone
- `VOICE_ID` — swap for a different ElevenLabs voice

---

## V2 roadmap (not in this version)

- [ ] Long-term memory (Qdrant vector DB + session summaries)
- [ ] Streaming TTS (chunks played as they arrive, not after full response)
- [ ] Real-time VAD (no hold button — automatic speech detection)
- [ ] Multi-language support (Deepgram + ElevenLabs both support it)
- [ ] Session history dashboard

---

## Cost estimate (V1, per session)

Typical 20-minute session (10 exchanges, avg 30 words in / 40 words out):

| | Cost |
|---|---|
| Deepgram (~2 min audio) | ~$0.013 |
| Claude Sonnet (10 turns) | ~$0.008 |
| ElevenLabs (~400 words) | ~$0.006 |
| **Total** | **~$0.027 per session** |

---

Built by ALOLABS.
