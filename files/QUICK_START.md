# Quick Start — Zen Voice Counselor V1.5

## 🚀 Get Running in 5 Minutes

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Environment Variables

Create `.env` file:

```bash
# Required
ANTHROPIC_API_KEY=your_key_here
DEEPGRAM_API_KEY=your_key_here

# Optional (for premium emotional TTS)
ELEVENLABS_API_KEY=your_key_here
```

**Without ElevenLabs:** Works fine! System uses free Edge TTS for all responses.

### 3. Run

```bash
uvicorn main:app --reload --port 8000
```

### 4. Open Browser

```
http://localhost:8000
```

---

## ✅ What You Get

- **Real-time voice counselor** in Hindi/Marathi/English
- **Automatic emotion detection** for crisis/high-emotion
- **Hybrid TTS routing:**
  - Free Edge TTS for normal conversation (80-90%)
  - Premium ElevenLabs for emotional moments (10-20%)
- **Cost: ₹20-40 per session** (vs ₹150+ without optimization)

---

## 🎯 Key Features

### Emotion Detection

System automatically detects:
- **Crisis patterns:** "want to die", "suicide", "सब खत्म"
- **High emotion:** "very sad", "overwhelmed", "बहुत दुखी"

When detected → uses premium expressive voice (if ElevenLabs configured)

### Cost Optimization

```
Before: 100% Premium TTS = ₹150/session
After:  10-20% Premium TTS = ₹20-40/session
```

---

## 📁 Files

- `emotion.py` — Crisis/emotion detection patterns
- `pipeline.py` — Hybrid TTS routing logic  
- `persona.py` — Counselor system prompts
- `main.py` — FastAPI WebSocket server
- `index.html` — Web UI

---

## 🔧 Customization

### Add More Emotion Patterns

Edit `emotion.py`:

```python
CRISIS_PATTERNS = [
    r"want to die",
    r"your pattern here",
]
```

### Change TTS Voices

Edit `pipeline.py`:

```python
_TTS_VOICE = {
    "en": "en-US-AriaNeural",  # Edge TTS
    "hi": "hi-IN-SwaraNeural",
}

_ELEVENLABS_VOICE = {
    "en": "your_voice_id",  # ElevenLabs
}
```

---

## 📊 Monitor Costs

Check console logs to see TTS routing:

```
[FREE TTS] Normal conversation...
[PREMIUM TTS] I feel overwhelmed...
[FREE TTS] Tell me more...
```

Track premium usage % over time to estimate costs.

---

## ❓ Troubleshooting

**"ElevenLabs not available"**
→ No ELEVENLABS_API_KEY set. System uses free Edge TTS (this is fine!)

**Premium never triggers**
→ Check patterns in `emotion.py`, add debug logging

**High costs**
→ Patterns too broad, tighten in `emotion.py`

---

## 📚 Full Documentation

See `IMPLEMENTATION_GUIDE.md` for:
- Complete setup instructions
- Customization options
- Cost analysis
- Production deployment guide

See `IMPLEMENTATION_SUMMARY.md` for:
- Technical implementation details
- Alignment with PDF recommendations
- Roadmap for V2.0

---

## 🎯 Next Steps

1. **Test with real conversations** — See if emotion detection triggers appropriately
2. **Monitor premium usage %** — Should be 10-20% for optimal cost/quality
3. **Adjust patterns** — Fine-tune based on your use case
4. **Plan V2.0** — Streaming STT, full duplex, model routing

---

**Questions?** Check the implementation docs or review the code — it's well-commented!

**Ready for production?** See deployment checklist in `IMPLEMENTATION_GUIDE.md`
