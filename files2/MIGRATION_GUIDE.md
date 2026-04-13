# Quick Migration Guide — V1.5 → V2.0

## TL;DR

**V2.0 adds 3 major features:**
1. **Streaming STT + VAD** — No hold button, continuous listening
2. **Full duplex** — Auto-interrupt when user speaks
3. **Expressive TTS** — Emotion-based voice tuning

**What you need to do:**
1. Update dependencies (`pip install -r requirements.txt`)
2. Run new backend (`uvicorn main_streaming:app --port 8000`)
3. Update frontend to use continuous audio streaming

---

## Step-by-Step Migration

### Step 1: Update Dependencies

```bash
pip install -r requirements.txt
```

**New dependency:** `numpy` (for VAD)

### Step 2: Choose Deployment Strategy

**Option A: Run Both (Recommended)**
```bash
# V1.5 on port 8000 (existing users)
uvicorn main:app --port 8000

# V2.0 on port 8001 (beta testing)
uvicorn main_streaming:app --port 8001
```

**Option B: Replace V1.5**
```bash
# Switch completely to V2.0
uvicorn main_streaming:app --port 8000
```

### Step 3: Update Frontend

**V1.5 Frontend (Hold Button):**
```javascript
// Start recording on mousedown/touchstart
orb.addEventListener('mousedown', startRecording);

// Stop and send on mouseup/touchend
orb.addEventListener('mouseup', async () => {
    const audioBlob = await stopRecording();
    sendAudio(audioBlob);
});
```

**V2.0 Frontend (Continuous Stream):**
```javascript
// Start continuous streaming on session start
async function startSession() {
    const stream = await navigator.mediaDevices.getUserMedia({audio: true});
    const mediaRecorder = new MediaRecorder(stream);
    
    mediaRecorder.ondataavailable = (event) => {
        // Send audio chunks continuously
        sendAudioChunk(event.data);
    };
    
    mediaRecorder.start(100); // Send chunk every 100ms
}

// Handle interim transcripts
socket.addEventListener('message', (event) => {
    const data = JSON.parse(event.data);
    
    if (data.type === 'transcript_interim') {
        showInterimTranscript(data.text);
    } else if (data.type === 'transcript_final') {
        showFinalTranscript(data.text);
    }
});
```

### Step 4: Update WebSocket Protocol

**V1.5 Messages:**
```json
// Client → Server
{"type": "audio_chunk", "audio": "<base64 webm>"}

// Server → Client
{"type": "transcript", "text": "..."}
{"type": "sentence_audio", "audio": "<base64>", "index": 0}
```

**V2.0 Messages:**
```json
// Client → Server
{"type": "start_session", "language": "hi"}
{"type": "audio_stream", "audio": "<base64 PCM>", "sample_rate": 16000}
{"type": "end_session"}

// Server → Client
{"type": "transcript_interim", "text": "..."}
{"type": "transcript_final", "text": "..."}
{"type": "response_audio", "audio": "<base64>", "index": 0}
{"type": "interrupted", "reason": "user_spoke"}
```

---

## Configuration Differences

### V1.5 Configuration
```python
# pipeline.py

# TTS Voice
_TTS_VOICE = {
    "hi": "hi-IN-SwaraNeural",
}

# Hybrid routing only
if use_premium:
    audio = await elevenlabs_tts(text)
else:
    audio = await edge_tts(text)
```

### V2.0 Configuration
```python
# pipeline_streaming.py

# Same TTS voices
_TTS_VOICE = {
    "hi": "hi-IN-SwaraNeural",
}

# Plus expressiveness tuning
async def expressive_tts(text, context, language, sentence_index):
    if use_premium:
        # Adjust stability based on emotion
        audio = await elevenlabs_tts_tuned(
            text,
            stability=0.7 if context["crisis"] else 0.4,
        )
    else:
        # Adjust rate based on emotion
        audio = await edge_tts_tuned(
            text,
            rate="-10%" if context["crisis"] else "+0%",
        )
    
    # Add natural pauses
    if text.endswith('?'):
        await asyncio.sleep(0.15)
```

**New tuning parameters you can adjust:**
- `silence_threshold_ms` — How long to wait after speech (default: 700ms)
- `stability` — ElevenLabs voice stability (0.4-0.7)
- `similarity_boost` — Voice consistency (0.7-0.8)
- `rate` — Speaking speed adjustment (-10% to +10%)

---

## Testing Checklist

After migration, test these scenarios:

### ✅ Basic Functionality
- [ ] Start session without errors
- [ ] Speak and get transcribed correctly
- [ ] AI responds with audio
- [ ] End session cleanly

### ✅ Streaming Features
- [ ] No hold button needed
- [ ] Speech auto-detected after 700ms silence
- [ ] Interim transcripts show during speaking

### ✅ Full Duplex
- [ ] Interrupt AI by speaking
- [ ] AI stops immediately
- [ ] New input processed correctly

### ✅ Expressiveness
- [ ] Normal speech uses Edge TTS
- [ ] Emotional phrases use ElevenLabs (if configured)
- [ ] Natural pauses after questions

### ✅ Error Handling
- [ ] Background noise doesn't trigger false detection
- [ ] Network interruption handled gracefully
- [ ] Long silence doesn't freeze session

---

## Rollback Plan

If V2.0 has issues:

```bash
# Stop V2.0
pkill -f main_streaming

# Restart V1.5
uvicorn main:app --port 8000
```

No data loss — sessions are independent.

---

## Common Issues & Fixes

### Issue: "Deepgram connection failed"

**Cause:** Streaming API requires different SDK calls

**Fix:** Check Deepgram SDK version
```bash
pip show deepgram-sdk
# Should be 3.7.2 or higher
```

### Issue: "Audio chunks not processed"

**Cause:** Wrong audio format (V2.0 expects PCM, not WebM)

**Fix:** Convert in frontend
```javascript
// Use AudioContext to get PCM
const audioContext = new AudioContext();
const source = audioContext.createMediaStreamSource(stream);
const processor = audioContext.createScriptProcessor(4096, 1, 1);

processor.onaudioprocess = (e) => {
    const pcmData = e.inputBuffer.getChannelData(0);
    // Convert to Int16Array and send
    sendPCM(pcmData);
};
```

### Issue: "High latency"

**Cause:** VAD silence threshold too long

**Fix:** Reduce threshold
```python
StreamingTranscriber(
    language="hi",
    silence_threshold_ms=500  # Reduced from 700ms
)
```

### Issue: "Interruption not working"

**Cause:** ConversationState not detecting user speech

**Fix:** Add logging
```python
def user_started_speaking(self):
    print(f"[DEBUG] User speech detected, AI speaking: {self.ai_speaking}")
    # ...
```

---

## Performance Comparison

Run both versions and measure:

| Metric | V1.5 | V2.0 | Target |
|---|---|---|---|
| First audio latency | 1.2s | 0.8s | <1.0s |
| Interruption delay | N/A | <200ms | <300ms |
| False VAD triggers | 0% | <5% | <10% |
| Session stability | 99%+ | >95% | >95% |

---

## Recommended Migration Timeline

### Week 1: Setup & Internal Testing
- Deploy V2.0 on test environment
- Test all features thoroughly
- Fix critical bugs

### Week 2: Beta Testing
- Release to 10-20 beta users
- Monitor logs closely
- Gather feedback

### Week 3: Gradual Rollout
- Offer V2.0 as opt-in
- Monitor adoption rate
- Compare metrics (latency, satisfaction)

### Week 4: Decision
- If V2.0 metrics better → make it default
- If V2.0 has issues → keep V1.5 as default
- Or maintain both permanently

---

## Summary

**Migration is optional** — V1.5 continues to work perfectly.

**Choose V2.0 if:**
- ✅ You want best-in-class UX
- ✅ Can invest time in testing
- ✅ Differentiation matters

**Stick with V1.5 if:**
- ✅ Current UX is acceptable
- ✅ Stability is critical
- ✅ Limited engineering time

Both versions are India-viable (₹20-40/session) ✅
