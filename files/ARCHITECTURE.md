# System Architecture — Zen Voice Counselor V1.5

## High-Level Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                          USER                                    │
│                    (Browser/Mobile)                              │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                    Audio WebSocket
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                   FastAPI Backend                                │
│                      (main.py)                                   │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                Processing Pipeline                               │
│                   (pipeline.py)                                  │
│                                                                  │
│  ┌────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │ Deepgram   │───▶│ Claude       │───▶│ Emotion      │       │
│  │ STT        │    │ Sonnet       │    │ Detection    │       │
│  │ (Speech→   │    │ (Generate    │    │ (Crisis?     │       │
│  │  Text)     │    │  Response)   │    │  Emotion?)   │       │
│  └────────────┘    └──────────────┘    └──────┬───────┘       │
│                                                 │               │
│                                                 ▼               │
│                                        ┌────────────────┐       │
│                                        │ TTS Router     │       │
│                                        │ (adaptive_tts) │       │
│                                        └────┬───────┬───┘       │
│                                             │       │           │
│                                 ┌───────────┘       └─────────┐ │
│                                 ▼                             ▼ │
│                        ┌─────────────────┐       ┌──────────────┐
│                        │ Edge TTS        │       │ ElevenLabs  │
│                        │ (FREE)          │       │ (Premium)   │
│                        │ 80-90% usage    │       │ 10-20% usage│
│                        └─────────────────┘       └──────────────┘
└─────────────────────────────────────────────────────────────────┘
```

## Emotion-Based Routing

```
User Input: "I feel overwhelmed"
     │
     ▼
┌─────────────────┐
│ Emotion         │
│ Detection       │──▶ HIGH_EMOTION detected ✓
│ (emotion.py)    │
└─────────────────┘
     │
     ▼
┌─────────────────┐
│ TTS Router      │──▶ Route to Premium TTS
│ (pipeline.py)   │
└─────────────────┘
     │
     ▼
┌─────────────────┐
│ ElevenLabs TTS  │──▶ Expressive voice response
│ (Premium)       │
└─────────────────┘
```

```
User Input: "Tell me about meditation"
     │
     ▼
┌─────────────────┐
│ Emotion         │
│ Detection       │──▶ No crisis/emotion ✗
│ (emotion.py)    │
└─────────────────┘
     │
     ▼
┌─────────────────┐
│ TTS Router      │──▶ Route to Free TTS
│ (pipeline.py)   │
└─────────────────┘
     │
     ▼
┌─────────────────┐
│ Edge TTS        │──▶ Standard voice response
│ (Free)          │
└─────────────────┘
```

## Cost Breakdown by Component

```
Per 15-minute Session
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STT (Deepgram)
├─ ~15 min audio
└─ Cost: ₹4

LLM (Claude Sonnet)
├─ ~10 turns × 200 tokens
└─ Cost: ₹2

TTS (HYBRID) ⭐
├─ Edge TTS (80%)
│  └─ Cost: ₹0 (FREE)
├─ ElevenLabs (20%)
│  └─ Cost: ₹15-25
└─ Total TTS: ₹15-25

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TOTAL: ₹21-31 per session ✅

vs. Premium-only: ₹150+ ❌
Savings: 70-90%
```

## File Dependencies

```
main.py
  │
  ├─▶ pipeline.py
  │     │
  │     ├─▶ emotion.py
  │     ├─▶ persona.py
  │     ├─▶ deepgram-sdk
  │     ├─▶ anthropic
  │     ├─▶ edge-tts
  │     └─▶ elevenlabs (optional)
  │
  └─▶ index.html (frontend)
```

## Deployment Architecture

```
┌─────────────────────────────────────────┐
│         Production Server               │
│                                         │
│  ┌──────────────────────────────────┐  │
│  │   Uvicorn (ASGI Server)          │  │
│  │   Port 8000                      │  │
│  └─────────────┬────────────────────┘  │
│                │                        │
│  ┌─────────────▼────────────────────┐  │
│  │   FastAPI Application            │  │
│  │   - WebSocket gateway            │  │
│  │   - Session management           │  │
│  └─────────────┬────────────────────┘  │
│                │                        │
│  ┌─────────────▼────────────────────┐  │
│  │   Processing Pipeline            │  │
│  │   - Emotion detection            │  │
│  │   - Hybrid TTS routing           │  │
│  └──────────────────────────────────┘  │
└─────────────────────────────────────────┘
           │
           │ External API Calls
           │
    ┌──────┴───────┬───────────┬─────────────┐
    ▼              ▼           ▼             ▼
┌─────────┐  ┌──────────┐  ┌────────┐  ┌──────────┐
│Deepgram│  │ Anthropic│  │ Edge   │  │ElevenLabs│
│   STT   │  │  Claude  │  │  TTS   │  │   TTS    │
│         │  │          │  │ (Free) │  │ (Premium)│
└─────────┘  └──────────┘  └────────┘  └──────────┘
```

## Security & Privacy

```
User Audio
    │
    ├─▶ Encrypted WebSocket (WSS)
    │
    ▼
Server
    │
    ├─▶ API calls over HTTPS
    ├─▶ No audio storage
    ├─▶ Session-only memory (max 10 turns)
    └─▶ Environment variables for keys
```

---

**Legend:**
- ✓ = Feature enabled
- ✗ = Feature disabled
- ⭐ = Key innovation
- ▶ = Data flow
- ─ = Connection
