# Zen Voice Counselor — V1.5 (Cost-Optimized with Hybrid TTS)

A real-time voice-to-voice counselor app with **adaptive emotion-based TTS routing** that significantly reduces costs while maintaining quality for emotional moments.

**Key Improvement:** Hybrid TTS system that uses free Edge TTS by default and premium ElevenLabs only for crisis/emotional situations, reducing cost from ₹150/session to ₹20-40/session.

---

## What's New in V1.5

### 🎯 Hybrid TTS Router with Emotion Detection

The system now intelligently routes TTS requests based on emotional context:

- **Normal conversation (80-90%)** → Edge TTS (FREE)
- **Crisis/high-emotion (10-20%)** → ElevenLabs (Premium)

This achieves:
- ✅ **70-90% cost reduction** vs always using premium TTS
- ✅ **Same perceived quality** (premium voice where it matters)
- ✅ **Automatic crisis detection** for safety-critical moments

### Architecture Changes

```
User Audio
  ↓
Deepgram STT
  ↓
Emotion Detection ←────┐
  ↓                     │
Claude Sonnet          │
  ↓                     │
Hybrid TTS Router      │
  ├─→ Edge TTS (80%)   │
  └─→ ElevenLabs (20%) ← Crisis/Emotion detected
  ↓
Audio Response
```

---

## Setup

### 1. Get API keys

| Service | Free tier | Required? | Link |
|---|---|---|---|
| Anthropic | Pay-per-use | **Required** | https://console.anthropic.com |
| Deepgram | 200 hrs/month free | **Required** | https://console.deepgram.com |
| ElevenLabs | 10k chars/month free | **Optional** | https://elevenlabs.io |

**Note:** ElevenLabs is optional. Without it, the system will use Edge TTS for all responses (still works great, just less expressive for emotional moments).

### 2. Install dependencies

```bash
cd zen-counselor
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Set environment variables

Create a `.env` file:

```bash
# Required
ANTHROPIC_API_KEY=your_anthropic_key
DEEPGRAM_API_KEY=your_deepgram_key

# Optional (enables premium TTS for emotional moments)
ELEVENLABS_API_KEY=your_elevenlabs_key
```

**Without ElevenLabs:** The system will automatically fall back to Edge TTS for all responses.

### 4. Run the backend

```bash
uvicorn main:app --reload --port 8000
```

### 5. Open the app

Navigate to: http://localhost:8000

---

## How It Works

### Emotion Detection

The system uses pattern-based detection to identify:

**Crisis patterns:**
- "want to die", "suicide", "end my life"
- "सब खत्म", "मर जाना" (Hindi)
- Marathi equivalents

**High emotion patterns:**
- "very sad", "depressed", "overwhelmed"
- "बहुत दुखी", "थकल" (Hindi/Marathi)

See `emotion.py` for the full list.

### TTS Routing Logic

```python
# Simplified logic
if crisis_detected or high_emotion_detected:
    use_premium_tts()  # ElevenLabs (if available)
else:
    use_free_tts()     # Edge TTS
```

### Cost Breakdown (15-min session)

| Component | Cost |
|---|---|
| STT (Deepgram) | ₹4 |
| LLM (Claude) | ₹2 |
| **TTS (Hybrid)** | **₹15-25** |
| **Total** | **₹21-31** |

vs. premium-only TTS: ₹150+

---

## Customization

### Adjusting Emotion Patterns

Edit `emotion.py` to add/remove trigger patterns:

```python
# Add more crisis patterns
CRISIS_PATTERNS = [
    r"want to die",
    r"your custom pattern",
    # ...
]

# Add more emotion patterns
HIGH_EMOTION_PATTERNS = [
    r"very sad",
    r"your custom pattern",
    # ...
]
```

### Changing TTS Voices

Edit voice IDs in `pipeline.py`:

```python
# For Edge TTS (free)
_TTS_VOICE = {
    "en": "en-US-AriaNeural",
    "hi": "hi-IN-SwaraNeural",
    "mr": "mr-IN-AarohiNeural",
}

# For ElevenLabs (premium)
_ELEVENLABS_VOICE = {
    "en": "your_voice_id",
    "hi": "your_voice_id",
    "mr": "your_voice_id",
}
```

Get ElevenLabs voice IDs from: https://elevenlabs.io/docs/voices/voice-library

### Adjusting Premium Usage

To use premium TTS more/less frequently, modify the patterns in `emotion.py` or change the routing logic in `pipeline.py`:

```python
# More conservative (less premium usage)
def should_use_premium_tts(context: dict) -> bool:
    return context.get("crisis", False)  # Only for crisis

# More liberal (more premium usage)
def should_use_premium_tts(context: dict) -> bool:
    return (context.get("crisis", False) or 
            context.get("high_emotion", False) or
            len(text) > 100)  # Also for long responses
```

---

## File Structure

```
zen-counselor/
├── emotion.py          # NEW: Crisis/emotion detection
├── pipeline.py         # UPDATED: Hybrid TTS routing
├── persona.py          # Counselor system prompts
├── main.py            # FastAPI WebSocket server
├── requirements.txt   # Python dependencies
└── frontend/
    └── index.html     # Web UI
```

---

## Testing Emotion Detection

**Should trigger premium TTS:**
```
User: "I feel like everything should end"
System: [Uses ElevenLabs for emotional response]
```

**Should use free TTS:**
```
User: "I had a normal day"
System: [Uses Edge TTS for normal response]
```

---

## Cost Monitoring

Add logging to track TTS usage:

```python
# In pipeline.py
async def adaptive_tts(...):
    if use_premium:
        print(f"[PREMIUM TTS] {text[:50]}...")
    else:
        print(f"[FREE TTS] {text[:50]}...")
```

Run for a week and check premium usage percentage to estimate real costs.

---

## Roadmap (V2)

Future improvements discussed in the PDF analysis:

- [ ] **Streaming STT + VAD** — Remove hold button, continuous listening
- [ ] **Full duplex** — True interruption support
- [ ] **Model routing** — Haiku (default) + Sonnet (fallback)
- [ ] **Improved emotion detection** — Embedding-based vs keyword
- [ ] **Session management** — 10-15 min soft caps

---

## Production Deployment

For production use:

1. **Add monitoring** — Track TTS routing decisions and costs
2. **Tune patterns** — Adjust emotion triggers based on real usage
3. **Set rate limits** — Prevent cost spikes from abuse
4. **Add analytics** — Understand when/why premium TTS is triggered

---

## Troubleshooting

**"ElevenLabs not available" warning:**
- ElevenLabs API key not set → System will use Edge TTS for all responses
- This is fine for testing; add key later when ready

**Premium TTS never triggers:**
- Check emotion patterns in `emotion.py`
- Add debug logging to see detection results
- Verify user input contains trigger keywords

**All TTS uses premium (high costs):**
- Patterns too broad → Tighten in `emotion.py`
- Check logs to see why premium is triggering

---

## License & Credits

Built following the technical analysis and cost optimization strategies from the Ola AI Voice Assistant study.

Key improvements:
- Hybrid TTS routing (70-90% cost reduction)
- Emotion-based quality adaptation
- Production-ready cost architecture for India market

---

## Support

For questions or issues:
1. Check emotion detection patterns in `emotion.py`
2. Review TTS routing logic in `pipeline.py`
3. Monitor costs via logging

**India-viable target:** ₹20-40 per 15-min session ✅
