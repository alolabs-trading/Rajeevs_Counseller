# Zen Voice Counselor V2.0 — Full Duplex Edition

**Real-time voice counselor with Ola-level interaction quality.**

## 🚀 What's New in V2.0

Three major upgrades from V1.5:

### 1. ✅ Streaming STT + VAD (No Hold Button)
**Before:** User holds button → speaks → releases → waits

**Now:** User just speaks naturally → system auto-detects

### 2. ✅ Full Duplex (Auto-Interrupt)
**Before:** User clicks to manually interrupt

**Now:** User speaks → AI automatically stops

### 3. ✅ Expressive TTS Tuning
**Before:** Just routing between engines

**Now:** Emotion-based voice adjustments (rate, stability, pauses)

---

## 📁 Files Included

### Core Implementation
- **`vad.py`** — Voice Activity Detection (energy-based + Deepgram-based)
- **`pipeline_streaming.py`** — Streaming STT, LLM, and expressive TTS
- **`main_streaming.py`** — FastAPI WebSocket server with full duplex
- **`emotion.py`** — Crisis/emotion detection (from V1.5)
- **`persona.py`** — Counselor system prompts (from V1.5)

### Documentation
- **`IMPLEMENTATION_GUIDE_V2.md`** — Complete setup and configuration
- **`V1.5_VS_V2.0_COMPARISON.md`** — Feature comparison and decision matrix
- **`MIGRATION_GUIDE.md`** — How to upgrade from V1.5
- **`requirements.txt`** — Dependencies (includes numpy for VAD)
- **`.env.example`** — Environment variable template

---

## ⚡ Quick Start

### 1. Install

```bash
pip install -r requirements.txt
```

### 2. Configure

Create `.env` file:

```bash
ANTHROPIC_API_KEY=your_key
DEEPGRAM_API_KEY=your_key
ELEVENLABS_API_KEY=your_key  # Optional
```

### 3. Run

```bash
uvicorn main_streaming:app --reload --port 8000
```

### 4. Test

Open browser console and test WebSocket:

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/streaming');

ws.onopen = () => {
    // Start session
    ws.send(JSON.stringify({
        type: 'start_session',
        language: 'hi'
    }));
};

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log(data);
};
```

**Note:** Full frontend requires continuous audio streaming (see IMPLEMENTATION_GUIDE_V2.md)

---

## 🏗️ Architecture

```
User (Continuous Speech)
    ↓
Mic Stream (50-100ms chunks)
    ↓
Deepgram Live API
    ├─ Interim transcripts (real-time)
    └─ Final transcript (after 700ms silence)
    ↓
Emotion Detection
    ↓
Claude Sonnet (streaming)
    ↓
Expressive TTS Router
    ├─ Edge TTS (80%, free, rate-adjusted)
    └─ ElevenLabs (20%, premium, stability-tuned)
    ↓
Audio Playback (interruptible)

[Full Duplex Layer]
ConversationState Manager
    ├─ Tracks: User speaking? AI speaking?
    └─ Auto-interrupts AI when user speaks
```

---

## 🎯 Key Features

### Streaming STT with VAD

**How it works:**
1. Continuous mic streaming via WebSocket
2. Deepgram processes audio in real-time
3. Provides interim transcripts (partial)
4. Detects silence (700ms default)
5. Finalizes transcript → triggers AI response

**Configuration:**
```python
StreamingTranscriber(
    language="hi",
    silence_threshold_ms=700  # Adjust 500-1000ms
)
```

### Full Duplex Interruption

**Flow:**
```python
# AI is speaking
conversation_state.ai_speaking = True

# User starts speaking (detected by VAD or energy)
conversation_state.user_started_speaking()
    → Sets interrupt flag
    → Cancels AI response task
    → Stops audio playback

# Process new user input
```

### Expressive TTS

**Edge TTS Tuning:**
```python
# Crisis: -10% rate (slower, careful)
# Emotion: -5% rate (measured)
# Normal: +0% rate (default)

communicate = edge_tts.Communicate(text, voice, rate=rate)
```

**ElevenLabs Tuning:**
```python
# Crisis: stability=0.7, similarity=0.8 (stable, consistent)
# Emotion: stability=0.4, similarity=0.7 (expressive)
# Normal: stability=0.5, similarity=0.75 (balanced)

client.text_to_speech.convert(
    voice_id=voice_id,
    voice_settings={"stability": stability, ...}
)
```

**Natural Pauses:**
```python
# After questions: 150ms
if text.endswith('?'):
    await asyncio.sleep(0.15)

# Before emotional response: 200ms
if use_premium and sentence_index == 0:
    await asyncio.sleep(0.2)
```

---

## 💰 Cost Analysis

### Per 15-Minute Session

| Component | Cost |
|---|---|
| Streaming STT (Deepgram) | ₹4-6 |
| LLM (Claude Sonnet) | ₹2 |
| Hybrid TTS (Edge + ElevenLabs) | ₹15-25 |
| **Total** | **₹21-33** |

**Compared to V1.5:** +₹0-2 (marginal STT increase due to streaming)

**Still India-viable ✅** (Target: ₹20-40)

### Cost Breakdown

**Streaming STT overhead:**
- V1.5: Sends audio once (complete file)
- V2.0: Continuous stream (includes silences)
- Difference: ~0-50% more data = +₹0-2

**Worth it?** YES — UX improvement >> marginal cost

---

## 🔧 Configuration & Tuning

### 1. VAD Sensitivity

**Default:** 700ms silence = speech ended

**Faster responses (may cut off words):**
```python
silence_threshold_ms=500
```

**More patient (won't cut off):**
```python
silence_threshold_ms=1000
```

**Trade-off:** Lower = faster but risky, Higher = safer but slower

### 2. Expressiveness Parameters

**Conservative (subtle changes):**
```python
# Edge TTS
crisis_rate = "-5%"  # Not too slow
emotion_rate = "-2%"

# ElevenLabs
crisis_stability = 0.6  # Not too stable
```

**Aggressive (dramatic changes):**
```python
# Edge TTS
crisis_rate = "-15%"  # Very slow
emotion_rate = "-8%"

# ElevenLabs
crisis_stability = 0.8  # Very stable
emotion_stability = 0.3  # Very expressive
```

### 3. Pause Timing

**Subtle pauses:**
```python
question_pause = 0.10  # 100ms
emotional_pause = 0.15  # 150ms
```

**Dramatic pauses:**
```python
question_pause = 0.25  # 250ms
emotional_pause = 0.35  # 350ms
```

---

## 🧪 Testing

### Test 1: Continuous Listening

1. Start session
2. Speak naturally (no button)
3. Stop speaking
4. After 700ms → transcript should appear
5. AI responds

**Expected:** No manual triggers needed

### Test 2: Interruption

1. AI starts responding
2. Mid-response, user speaks
3. AI should stop immediately
4. User's new input processed

**Expected:** <300ms interruption delay

### Test 3: Expressiveness

**Crisis pattern:**
```
User: "I feel like ending it all"

Expected:
- Uses ElevenLabs (premium)
- Slower speaking rate
- Stable, controlled tone
- Opening pause (200ms)
```

**Normal conversation:**
```
User: "Tell me about meditation"

Expected:
- Uses Edge TTS (free)
- Normal speaking rate
- Standard tone
```

---

## 🐛 Troubleshooting

### "Deepgram connection failed"

**Causes:**
- Invalid API key
- Network issues
- SDK version mismatch

**Fix:**
```bash
# Check SDK version
pip show deepgram-sdk  # Should be 3.7.2+

# Test connection
python -c "from deepgram import DeepgramClient; print('OK')"
```

### "False speech detection"

**Causes:**
- Background noise
- VAD threshold too sensitive

**Fix:**
```python
# Increase energy threshold (SimpleVAD)
vad = SimpleVAD(energy_threshold=0.02)  # Higher = less sensitive

# Or increase silence threshold
StreamingTranscriber(silence_threshold_ms=1000)
```

### "Interruption not working"

**Debug:**
```python
# Add logging in ConversationState
def user_started_speaking(self):
    print(f"[INTERRUPT] User speaking, AI was: {self.ai_speaking}")
    if self.ai_speaking:
        print("[INTERRUPT] Cancelling AI task...")
```

### "High latency"

**Measure components:**
```python
import time

# In generate_response()
t1 = time.time()
context = detect_context(transcript)
print(f"Emotion detection: {time.time()-t1:.3f}s")

t2 = time.time()
async for sentence in stream_counselor_sentences(...):
    print(f"First token: {time.time()-t2:.3f}s")
    break
```

---

## 📊 Monitoring

### Key Metrics

1. **Interruption Rate**
   - How often users interrupt
   - Target: 10-20% (natural conversation)

2. **Premium TTS Usage**
   - % of responses using ElevenLabs
   - Target: 10-20% (cost optimization)

3. **End-to-End Latency**
   - Speech end → first audio
   - Target: <1.0s

4. **False Positive Rate**
   - Background noise triggering speech
   - Target: <5%

5. **Session Success Rate**
   - Completed without errors
   - Target: >95%

### Logging

Add to `main_streaming.py`:

```python
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# In generate_response()
logger.info(f"Response latency: {latency:.2f}s")
logger.info(f"Premium TTS: {use_premium}")
logger.info(f"Interrupted: {was_interrupted}")
```

---

## 🚢 Production Deployment

### Scaling Considerations

**Deepgram Connections:**
- 1 session = 1 persistent WebSocket
- 100 concurrent = 100 connections
- Monitor Deepgram quota

**Memory Usage:**
- Streaming buffers = ~1-2 MB per session
- 100 sessions = ~100-200 MB
- Set max concurrent sessions

**Network Bandwidth:**
- ~10-15 KB/s per session (audio streaming)
- 100 sessions = ~1-1.5 MB/s
- Plan accordingly

### Recommended Setup

```bash
# Multiple workers for load distribution
gunicorn main_streaming:app \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000
```

**Or with Uvicorn directly:**
```bash
uvicorn main_streaming:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 4
```

---

## 📈 Roadmap (V3.0)

Future improvements:

- [ ] **LLM Model Routing** — Haiku (default) + Sonnet (fallback)
- [ ] **Advanced Emotion Detection** — Embeddings vs regex
- [ ] **Multi-speaker Support** — Detect who's speaking
- [ ] **Session Analytics Dashboard** — Real-time monitoring
- [ ] **Voice Cloning** — Custom voices per language

---

## 📚 Documentation

- **IMPLEMENTATION_GUIDE_V2.md** — Complete setup guide
- **V1.5_VS_V2.0_COMPARISON.md** — Feature comparison
- **MIGRATION_GUIDE.md** — Upgrade from V1.5
- **ARCHITECTURE.md** — System design (from V1.5)

---

## ❓ FAQ

**Q: Should I use V1.5 or V2.0?**

A: V1.5 for stability, V2.0 for best UX. See comparison guide.

**Q: Does V2.0 cost more than V1.5?**

A: Marginally (+₹0-2 per session). Still ₹21-33 total.

**Q: Can I run both versions?**

A: Yes! Different ports, separate endpoints.

**Q: Is ElevenLabs required?**

A: No — works with free Edge TTS only. ElevenLabs is optional for premium emotional responses.

**Q: What's the main complexity increase?**

A: Persistent Deepgram connections + state management. Needs more testing than V1.5.

---

## 🎯 Summary

**V2.0 delivers Ola-level UX:**
- ✅ Continuous listening (no buttons)
- ✅ Automatic speech detection  
- ✅ Interrupt-anytime capability
- ✅ Expressive voice responses
- ✅ India-viable costs (₹21-33/session)

**Production-ready** with proper testing and monitoring.

**Choose V2.0 if:**
- UX differentiation matters
- Competing with best-in-class voice AI
- Can invest time in testing

**Stick with V1.5 if:**
- Stability is critical
- Current UX is acceptable
- Limited engineering time

Both are excellent choices — depends on priorities! 🚀

---

Built with insights from Ola AI Voice Assistant technical analysis.
