# pipeline_streaming.py
"""
Full-duplex streaming pipeline with VAD and automatic interruption.

This is the V2.0 pipeline that supports:
- Continuous audio streaming (no hold button)
- Real-time VAD for speech detection
- Deepgram live streaming API
- Full duplex (interrupt AI while speaking)
- Emotion-based TTS with expressiveness tuning
"""

import os
import re
import asyncio
import time
from typing import AsyncGenerator, Optional
from collections import deque

import anthropic
import edge_tts
from deepgram import (
    DeepgramClient,
    DeepgramClientOptions,
    LiveTranscriptionEvents,
    LiveOptions,
)
from persona import get_system_prompt
from emotion import detect_context, should_use_premium_tts

# Optional: ElevenLabs for premium TTS
try:
    from elevenlabs.client import ElevenLabs
    _ELEVENLABS_AVAILABLE = True
except ImportError:
    _ELEVENLABS_AVAILABLE = False


# ─── Singleton clients ───────────────────────────────────────────────────────

_anthropic: anthropic.AsyncAnthropic | None = None
_elevenlabs: ElevenLabs | None = None


def _get_anthropic() -> anthropic.AsyncAnthropic:
    global _anthropic
    if _anthropic is None:
        _anthropic = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _anthropic


def _get_elevenlabs() -> ElevenLabs | None:
    global _elevenlabs
    if not _ELEVENLABS_AVAILABLE:
        return None
    if _elevenlabs is None:
        api_key = os.environ.get("ELEVENLABS_API_KEY")
        if api_key:
            _elevenlabs = ElevenLabs(api_key=api_key)
    return _elevenlabs


# ─── Configuration ───────────────────────────────────────────────────────────

_STT_CONFIG = {
    "en": {"model": "nova-2", "language": "en"},
    "hi": {"model": "nova-2", "language": "hi"},
    "mr": {"model": "nova-3", "language": "mr"},
}

_TTS_VOICE = {
    "en": "en-US-AriaNeural",
    "hi": "hi-IN-SwaraNeural",
    "mr": "mr-IN-AarohiNeural",
}

_ELEVENLABS_VOICE = {
    "en": "EXAVITQu4vr4xnSDxMaL",  # Bella
    "hi": "pNInz6obpgDQGcFmaJgB",  # Adam (multilingual)
    "mr": "pNInz6obpgDQGcFmaJgB",
}


# ─── Sentence boundary detection ─────────────────────────────────────────────

_SENTENCE_END = re.compile(r'[.!?\u0964](?:\s|$)')


def _extract_sentences(buffer: str) -> tuple[list[str], str]:
    """Extract complete sentences from text buffer."""
    sentences = []
    while True:
        match = _SENTENCE_END.search(buffer)
        if not match:
            break
        end_pos = match.end()
        sentence = buffer[:end_pos].strip()
        if sentence:
            sentences.append(sentence)
        buffer = buffer[end_pos:]
    return sentences, buffer.strip()


# ─── Deepgram Streaming STT ──────────────────────────────────────────────────

class StreamingTranscriber:
    """
    Real-time speech-to-text with Deepgram live streaming.
    
    Maintains a persistent connection and provides interim + final transcripts.
    """
    
    def __init__(self, language: str = "hi", silence_threshold_ms: int = 700):
        self.language = language
        self.silence_threshold_ms = silence_threshold_ms
        
        # Deepgram client and connection
        config = DeepgramClientOptions(options={"keepalive": "true"})
        self.deepgram = DeepgramClient(os.environ["DEEPGRAM_API_KEY"], config)
        self.connection = None
        
        # Transcript accumulation
        self.transcript_buffer = ""
        self.last_transcript_time = None
        self.is_speaking = False
        
        # Event handlers
        self.on_transcript_callback = None
        self.on_speech_end_callback = None
        
    async def start(self):
        """Start the streaming connection."""
        cfg = _STT_CONFIG.get(self.language, _STT_CONFIG["hi"])
        
        options = LiveOptions(
            model=cfg["model"],
            language=cfg["language"],
            punctuate=True,
            smart_format=True,
            interim_results=True,
            utterance_end_ms=str(self.silence_threshold_ms),
            vad_events=True,
        )
        
        self.connection = self.deepgram.listen.live.v("1")
        
        # Set up event handlers
        self.connection.on(LiveTranscriptionEvents.Transcript, self._on_message)
        self.connection.on(LiveTranscriptionEvents.Error, self._on_error)
        
        # Start connection
        if not await self.connection.start(options):
            raise Exception("Failed to start Deepgram connection")
    
    def _on_message(self, _, result, **kwargs):
        """Handle incoming transcript."""
        try:
            # Extract transcript
            transcript = result.channel.alternatives[0].transcript
            
            if len(transcript) > 0:
                is_final = result.is_final
                speech_final = result.speech_final
                
                # Update state
                self.last_transcript_time = time.time()
                self.is_speaking = True
                
                if is_final or speech_final:
                    # Final transcript - add to buffer
                    self.transcript_buffer += " " + transcript if self.transcript_buffer else transcript
                    
                    if speech_final and self.on_speech_end_callback:
                        # Speech segment complete
                        asyncio.create_task(
                            self.on_speech_end_callback(self.transcript_buffer.strip())
                        )
                        self.transcript_buffer = ""
                        self.is_speaking = False
                
                # Notify interim transcript
                if self.on_transcript_callback:
                    asyncio.create_task(
                        self.on_transcript_callback(transcript, is_final)
                    )
        
        except Exception as e:
            print(f"Transcript processing error: {e}")
    
    def _on_error(self, _, error, **kwargs):
        """Handle errors."""
        print(f"Deepgram error: {error}")
    
    async def send_audio(self, audio_chunk: bytes):
        """Send audio chunk to Deepgram."""
        if self.connection:
            self.connection.send(audio_chunk)
    
    async def stop(self):
        """Stop the streaming connection."""
        if self.connection:
            await self.connection.finish()
            self.connection = None


# ─── LLM Streaming ───────────────────────────────────────────────────────────

async def stream_counselor_sentences(
    transcript: str,
    conversation_history: list[dict],
    language: str = "hi",
) -> AsyncGenerator[str, None]:
    """Stream Claude's response sentence by sentence."""
    client = _get_anthropic()
    
    messages = conversation_history + [{"role": "user", "content": transcript}]
    
    buffer = ""
    async with client.messages.stream(
        model="claude-sonnet-4-6",
        max_tokens=250,
        system=get_system_prompt(language),
        messages=messages,
        temperature=0.7,
        timeout=10.0,
    ) as stream:
        async for chunk in stream.text_stream:
            buffer += chunk
            sentences, buffer = _extract_sentences(buffer)
            for sentence in sentences:
                yield sentence
    
    remaining = buffer.strip()
    if remaining:
        yield remaining


# ─── TTS with Expressiveness Tuning ──────────────────────────────────────────

async def expressive_tts(
    text: str,
    context: dict,
    language: str = "hi",
    sentence_index: int = 0,
) -> bytes:
    """
    Generate TTS with emotion-based expressiveness tuning.
    
    Args:
        text: Text to synthesize
        context: Emotion context from detect_context()
        language: Language code
        sentence_index: Position in response (0 = first sentence)
        
    Returns:
        Audio bytes (MP3)
    """
    use_premium = should_use_premium_tts(context)
    
    if use_premium and _get_elevenlabs():
        # Premium TTS with emotion tuning
        audio = await _elevenlabs_tts_tuned(text, context, language)
        
        # Add natural pause for first sentence in emotional response
        if sentence_index == 0:
            await asyncio.sleep(0.2)
    else:
        # Free TTS with basic tuning
        audio = await _edge_tts_tuned(text, context, language)
    
    # Add pause after questions
    if text.rstrip().endswith(('?', '।')):  # Question mark or Hindi danda
        await asyncio.sleep(0.15)
    
    return audio


async def _edge_tts_tuned(text: str, context: dict, language: str) -> bytes:
    """Edge TTS with rate/pitch adjustments based on emotion."""
    voice = _TTS_VOICE.get(language, _TTS_VOICE["hi"])
    
    # Adjust speaking rate based on emotion
    rate = "+0%"  # Default
    if context.get("crisis"):
        rate = "-10%"  # Slower for crisis
    elif context.get("high_emotion"):
        rate = "-5%"  # Slightly slower for emotion
    
    # Build communicate with SSML adjustments
    communicate = edge_tts.Communicate(text, voice, rate=rate)
    
    audio_data = b""
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_data += chunk["data"]
    
    return audio_data


async def _elevenlabs_tts_tuned(text: str, context: dict, language: str) -> bytes:
    """ElevenLabs TTS with stability/similarity adjustments."""
    client = _get_elevenlabs()
    if not client:
        return await _edge_tts_tuned(text, context, language)
    
    try:
        voice_id = _ELEVENLABS_VOICE.get(language, _ELEVENLABS_VOICE["hi"])
        
        # Emotion-based voice settings
        stability = 0.5  # Default
        similarity_boost = 0.75  # Default
        
        if context.get("crisis"):
            stability = 0.7  # More stable for crisis
            similarity_boost = 0.8  # More consistent
        elif context.get("high_emotion"):
            stability = 0.4  # More expressive
            similarity_boost = 0.7  # Slight variation OK
        
        # Run in executor to avoid blocking
        loop = asyncio.get_running_loop()
        audio_generator = await loop.run_in_executor(
            None,
            lambda: client.text_to_speech.convert(
                voice_id=voice_id,
                model_id="eleven_multilingual_v2",
                text=text,
                voice_settings={
                    "stability": stability,
                    "similarity_boost": similarity_boost,
                },
            )
        )
        
        return b"".join(audio_generator)
    
    except Exception as e:
        print(f"ElevenLabs error: {e}, falling back to Edge")
        return await _edge_tts_tuned(text, context, language)


# ─── Full-Duplex Conversation Manager ────────────────────────────────────────

class ConversationState:
    """
    Manages full-duplex conversation state.
    
    Handles:
    - User speaking while AI is responding
    - Automatic interruption detection
    - Clean cancellation of in-progress streams
    """
    
    def __init__(self):
        self.user_speaking = False
        self.ai_speaking = False
        self.ai_stream_task: Optional[asyncio.Task] = None
        self.interrupted = False
    
    def user_started_speaking(self):
        """User started speaking."""
        self.user_speaking = True
        
        # If AI is speaking, interrupt it
        if self.ai_speaking:
            self.interrupted = True
            if self.ai_stream_task and not self.ai_stream_task.done():
                self.ai_stream_task.cancel()
    
    def user_stopped_speaking(self):
        """User stopped speaking."""
        self.user_speaking = False
    
    def ai_started_speaking(self, task: asyncio.Task):
        """AI started speaking."""
        self.ai_speaking = True
        self.ai_stream_task = task
        self.interrupted = False
    
    def ai_stopped_speaking(self):
        """AI finished speaking."""
        self.ai_speaking = False
        self.ai_stream_task = None
        self.interrupted = False
    
    def should_interrupt(self) -> bool:
        """Check if AI should be interrupted."""
        return self.interrupted
