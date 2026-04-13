# Zen Voice Counselor — V2.0 (Full Duplex with Streaming STT)

Real-time voice counselor with **Ola-level interaction**: continuous listening, automatic speech detection, and interrupt-anytime capability.

**Major Upgrades from V1.5:**
- ✅ **Streaming STT + VAD** — No hold button, continuous listening
- ✅ **Full Duplex** — Automatic interruption when user speaks
- ✅ **Expressive TTS Tuning** — Emotion-based voice adjustments (rate, stability, pauses)
- ✅ **Cost-Optimized** — Hybrid TTS routing (₹20-40/session)

---

## What's New in V2.0

### 🎯 Streaming STT with Auto-VAD

**Before (V1.5):**
```
User: Hold button → Speak → Release → Wait for processing
```

**Now (V2.0):**
```
User: Just speak naturally → System automatically detects speech
```

**How it works:**
- Continuous mic streaming via WebSocket
- Deepgram live API provides real-time transcription
- Built-in VAD detects when user stops speaking (700ms silence)
- No button presses needed!

### 🔄 Full Duplex (True Interrupt)

**Before (V1.5):**
```
User clicks "cancel" → AI stops
```

**Now (V2.0):**
```
User starts speaking → AI automatically stops
```

**Architecture:**
```
AI Speaking
    ↓
User Speaks (detected by VAD)
    ↓
AI Response Cancelled
    ↓
Switches to Listening Mode
    ↓
User's Input Processed
```

### 🎭 TTS Expressiveness Tuning

Beyond just switching engines, V2.0 adjusts voice parameters based on emotion:

**Edge TTS (Free):**
- Normal: 0% rate adjustment
- Emotional: -5% rate (slower, more measured)
- Crisis: -10% rate (very slow, careful)

**ElevenLabs (Premium):**
- Normal: stability=0.5, similarity=0.75
- Emotional: stability=0.4 (more expressive), similarity=0.7
- Crisis: stability=0.7 (more controlled), similarity=0.8

**Plus:**
- Natural pauses after questions (150ms)
- Opening pause for emotional responses (200ms)
- Smoother pacing overall

---

## Architecture Changes

### V1.5 Architecture (Batch Mode)
```
User → Hold Button → Record → Release → Upload
    ↓
Deepgram (Batch) → Full audio file
    ↓
Claude Streaming → Sentence by sentence
    ↓
TTS → Audio response
```

### V2.0 Architecture (Streaming Mode)
```
User → Continuous Mic Stream
    ↓
Deepgram Live API ← Audio chunks (50-100ms)
    ↓
VAD Detection → Speech start/end
    ↓
Interim Transcripts → Real-time feedback
    ↓
Final Transcript → Trigger AI response
    ↓
Claude Streaming → Sentence by sentence
    ↓
Expressive TTS → Emotion-tuned audio
    ↓
Playback (interruptible)
```

**Full Duplex Layer:**
```
ConversationState Manager
    ├─ User Speaking?
    ├─ AI Speaking?
    └─ Interrupt Flag
         ↓
    If User + AI both active
         ↓
    Cancel AI stream
    Process User input
```

---

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

**New in V2.0:** `numpy` for VAD energy calculations

### 2. Environment Variables

Same as V1.5:

```bash
ANTHROPIC_API_KEY=your_key
DEEPGRAM_API_KEY=your_key
ELEVENLABS_API_KEY=your_key  # Optional
```

### 3. Run V2.0

```bash
uvicorn main_streaming:app --reload --port 8000
```

**Note:** This is a separate file (`main_streaming.py`) so you can run V1.5 or V2.0:

```bash
# V1.5 (batch mode with hold button)
uvicorn main:app --reload --port 8000

# V2.0 (streaming mode, full duplex)
uvicorn main_streaming:app --reload --port 8000
```

### 4. Frontend

V2.0 requires a new frontend that:
- Continuously streams audio (no hold button)
- Handles interim transcripts
- Supports automatic interruption

See `index_streaming.html` (needs to be created or adapted from V1.5)

---

## Key Components

### 1. VAD Module (`vad.py`)

Two VAD implementations:

**SimpleVAD** — Energy-based
- Monitors audio RMS energy
- Configurable threshold
- Good for simple use cases

**DeepgramVAD** — Transcript-based (recommended)
- Uses Deepgram's interim results
- More reliable than energy
- Handles different accents/languages better

### 2. Streaming Pipeline (`pipeline_streaming.py`)

**StreamingTranscriber:**
- Manages Deepgram live connection
- Accumulates transcripts
- Detects speech boundaries
- Callbacks for interim/final results

**ConversationState:**
- Tracks who is speaking (user/AI)
- Manages interruption flags
- Cancels tasks when needed

**Expressive TTS Functions:**
- `expressive_tts()` — Main router with tuning
- `_edge_tts_tuned()` — Adjusts rate based on emotion
- `_elevenlabs_tts_tuned()` — Adjusts stability/similarity

### 3. Main Server (`main_streaming.py`)

**StreamingSession:**
- Manages per-connection state
- Handles audio streaming
- Coordinates transcription → response → TTS
- Implements full duplex logic

**WebSocket Protocol:**

Client → Server:
```json
{"type": "start_session", "language": "hi"}
{"type": "audio_stream", "audio": "<base64>", "sample_rate": 16000}
{"type": "end_session"}
```

Server → Client:
```json
{"type": "status", "state": "listening"}
{"type": "transcript_interim", "text": "..."}
{"type": "transcript_final", "text": "..."}
{"type": "response_text", "text": "...", "index": 0}
{"type": "response_audio", "audio": "<base64>", "index": 0}
{"type": "interrupted", "reason": "user_spoke"}
```

---

## Configuration & Tuning

### VAD Sensitivity

In `StreamingTranscriber.__init__()`:

```python
silence_threshold_ms=700  # How long to wait after speech

# More sensitive (faster responses, might cut off words):
silence_threshold_ms=500

# Less sensitive (slower, but won't cut off):
silence_threshold_ms=1000
```

### Expressiveness Parameters

In `pipeline_streaming.py`:

**Edge TTS Tuning:**
```python
# Crisis: slower speaking
rate = "-10%"

# Emotional: slightly slower
rate = "-5%"

# Normal: default
rate = "+0%"
```

**ElevenLabs Tuning:**
```python
# Crisis: stable, consistent
stability = 0.7
similarity_boost = 0.8

# Emotional: more expressive
stability = 0.4
similarity_boost = 0.7

# Normal: balanced
stability = 0.5
similarity_boost = 0.75
```

### Pause Timing

```python
# After questions
if text.endswith('?'):
    await asyncio.sleep(0.15)  # Adjust 0.10-0.20

# Before emotional response
if use_premium and sentence_index == 0:
    await asyncio.sleep(0.2)  # Adjust 0.15-0.30
```

---

## Cost Analysis (V2.0)

### Streaming STT Impact

**Before (Batch):**
- Upload complete audio → process once
- Cost: ~₹4 per 15-min session

**After (Streaming):**
- Continuous streaming → slightly more data
- Cost: ~₹4-6 per 15-min session (+0-50%)

**Why?** Streaming sends more audio (includes silences), but difference is marginal.

### Full Duplex Impact

**Cost:** Neutral (same processing, just better UX)

### Expressive TTS Impact

**Cost:** Same as V1.5 (hybrid routing still active)
- Free Edge TTS: 80-90%
- Premium ElevenLabs: 10-20%
- Total: ₹15-25 per session

### Total Cost (V2.0)

| Component | Cost |
|---|---|
| Streaming STT | ₹4-6 |
| LLM | ₹2 |
| Hybrid TTS | ₹15-25 |
| **Total** | **₹21-33** |

**Still India-viable ✅** (Target: ₹20-40)

---

## Testing

### 1. Test Continuous Listening

Expected behavior:
1. Start session
2. Speak naturally (no button)
3. Stop speaking
4. After 700ms → transcript appears
5. AI responds

### 2. Test Interruption

Expected behavior:
1. AI starts responding
2. User starts speaking mid-response
3. AI immediately stops
4. User's new input processed

### 3. Test Expressiveness

**Test Crisis Pattern:**
```
User: "I feel like ending everything"
Expected: 
- Premium TTS used
- Slower speaking rate
- More stable tone
```

**Test Normal:**
```
User: "Tell me about meditation"
Expected:
- Free Edge TTS used
- Normal speaking rate
```

### 4. Monitor Latency

**Key Metrics:**
- Time from speech end → first AI audio
- Target: <1 second
- V2.0 should be faster than V1.5 (streaming starts LLM earlier)

---

## Migration from V1.5

### Option 1: Run Both

```bash
# V1.5 on port 8000
uvicorn main:app --port 8000

# V2.0 on port 8001
uvicorn main_streaming:app --port 8001
```

### Option 2: Switch Completely

1. Update frontend to use continuous streaming
2. Replace WebSocket protocol
3. Test thoroughly
4. Deploy V2.0

### Backward Compatibility

V2.0 includes `/ws/session` endpoint that returns deprecation message.
Existing V1.5 clients will get clear error.

---

## Troubleshooting

### "Deepgram connection failed"

**Causes:**
- Invalid API key
- Network issues
- Quota exceeded

**Solution:**
```bash
# Check key
echo $DEEPGRAM_API_KEY

# Check network
curl -I https://api.deepgram.com

# Check quota at console.deepgram.com
```

### "Audio chunks not being processed"

**Causes:**
- Wrong audio format (must be PCM 16-bit)
- Base64 encoding issues
- WebSocket connection dropped

**Debug:**
```python
# Add logging in StreamingSession.process_audio()
print(f"Audio chunk size: {len(audio_bytes)} bytes")
```

### "Interruption not working"

**Causes:**
- VAD not detecting user speech
- ConversationState not updated
- Task cancellation failing

**Debug:**
```python
# Add logging in ConversationState
def user_started_speaking(self):
    print(f"User speaking detected, AI speaking: {self.ai_speaking}")
    # ...
```

### "High latency"

**Possible causes:**
- STT threshold too long (reduce from 700ms to 500ms)
- LLM taking too long (check Claude API status)
- TTS generation slow (check network to ElevenLabs)

**Measure:**
```python
import time

start = time.time()
# ... processing ...
print(f"Latency: {time.time() - start:.2f}s")
```

---

## Production Deployment

### Scaling Considerations

**Deepgram Connections:**
- Each session = 1 persistent WebSocket to Deepgram
- Monitor concurrent connections
- Consider connection pooling if needed

**Memory Usage:**
- Streaming buffers require more memory
- Monitor per-session memory
- Set max concurrent sessions

**Network Bandwidth:**
- Continuous audio streaming = higher bandwidth
- Estimate: ~10-15 KB/s per session
- 100 sessions = ~1-1.5 MB/s

### Recommended Deployment

```
Load Balancer
    ↓
Multiple Uvicorn Workers
    ├─ Worker 1 (handles 10-20 sessions)
    ├─ Worker 2
    └─ Worker 3
    
Each with:
- Persistent Deepgram connections
- Session state management
- TTS routing logic
```

### Monitoring

Key metrics to track:
1. **Interruption rate** — How often users interrupt
2. **Premium TTS usage** — Should stay 10-20%
3. **Latency** — Speech end → first audio
4. **Error rate** — Failed transcriptions, TTS errors
5. **Session duration** — Helps estimate costs

---

## Roadmap (V3.0)

Future improvements:

- [ ] **LLM Model Routing** — Haiku (default) + Sonnet (fallback)
- [ ] **Advanced Emotion Detection** — Embedding-based vs regex
- [ ] **Multi-speaker Support** — Detect different speakers
- [ ] **Session Recording** — Optional conversation logs
- [ ] **Real-time Analytics** — Live monitoring dashboard

---

## Summary

**V2.0 delivers Ola-level UX:**
- ✅ Continuous listening (no buttons)
- ✅ Automatic speech detection
- ✅ Interrupt-anytime capability
- ✅ Expressive voice responses
- ✅ Cost-optimized (₹21-33/session)

**Technology Stack:**
- Deepgram live streaming (STT)
- Built-in VAD for speech boundaries
- Claude Sonnet (LLM)
- Hybrid TTS (Edge + ElevenLabs)
- Full duplex conversation management

**Ready for production** with proper monitoring and scaling.

---

Built with insights from Ola AI Voice Assistant technical analysis.
