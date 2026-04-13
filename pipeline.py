"""
pipeline.py — Sentence-streaming audio pipeline for Rajeev's Voice Counsellor V1.

Flow:
  audio bytes (webm/ogg)
    → Deepgram STT  (nova-2, ~300ms)
    → Claude Sonnet (streaming, sentence-by-sentence)
    → Edge TTS      (per sentence, free, no API key needed)

The key optimization: Claude streams tokens, we detect sentence boundaries,
and fire TTS for each sentence immediately. The client starts hearing Aria
while she's still generating the rest of her response.
"""

import os
import re
import asyncio
from typing import AsyncGenerator

import anthropic
import edge_tts
from deepgram import DeepgramClient
from persona import get_system_prompt
from emotion import detect_context, should_use_premium_tts

# Optional: ElevenLabs for premium TTS (requires ELEVENLABS_API_KEY)
try:
    from elevenlabs.client import ElevenLabs
    _ELEVENLABS_AVAILABLE = True
except ImportError:
    _ELEVENLABS_AVAILABLE = False
    print("Warning: ElevenLabs not installed. Install with: pip install elevenlabs")

_RETRY_DELAYS = [1, 2, 3]  # seconds between retries on overload


# ─── Singleton clients (created once, reused) ───────────────────────────────

_deepgram: DeepgramClient | None = None
_anthropic: anthropic.AsyncAnthropic | None = None
_elevenlabs: ElevenLabs | None = None


def _get_deepgram() -> DeepgramClient:
    global _deepgram
    if _deepgram is None:
        _deepgram = DeepgramClient(api_key=os.environ["DEEPGRAM_API_KEY"])
    return _deepgram


def _get_anthropic() -> anthropic.AsyncAnthropic:
    global _anthropic
    if _anthropic is None:
        _anthropic = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _anthropic


def _get_elevenlabs() -> ElevenLabs | None:
    """Get ElevenLabs client if available and configured."""
    global _elevenlabs
    if not _ELEVENLABS_AVAILABLE:
        return None
    if _elevenlabs is None:
        api_key = os.environ.get("ELEVENLABS_API_KEY")
        if api_key:
            _elevenlabs = ElevenLabs(api_key=api_key)
        else:
            print("Warning: ELEVENLABS_API_KEY not set. Premium TTS disabled.")
    return _elevenlabs


# ─── Deepgram STT ────────────────────────────────────────────────────────────

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


async def transcribe_audio(audio_bytes: bytes, mimetype: str = "audio/webm", language: str = "hi") -> str:
    """
    Transcribe audio bytes to text using Deepgram.
    Returns empty string if no speech detected.
    """
    client = _get_deepgram()
    cfg = _STT_CONFIG.get(language, _STT_CONFIG["hi"])

    loop = asyncio.get_running_loop()
    response = await loop.run_in_executor(
        None,
        lambda: client.listen.v1.media.transcribe_file(
            request=audio_bytes,
            model=cfg["model"],
            language=cfg["language"],
            smart_format=True,
            punctuate=True,
        ),
    )

    try:
        transcript = response.results.channels[0].alternatives[0].transcript
        return transcript.strip()
    except (IndexError, AttributeError):
        return ""


# ─── Sentence boundary detection ────────────────────────────────────────────

# Matches sentence-ending punctuation for both English and Hindi (Devanagari purna viram)
_SENTENCE_END = re.compile(r'[.!?\u0964](?:\s|$)')


def _extract_sentences(buffer: str) -> tuple[list[str], str]:
    """
    Given a text buffer, extract complete sentences and return them
    along with any remaining incomplete text.
    """
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


# ─── Claude Sonnet (streaming, yields sentences) ────────────────────────────

async def stream_counselor_sentences(
    transcript: str,
    conversation_history: list[dict],
    language: str = "hi",
) -> AsyncGenerator[str, None]:
    """
    Stream Claude's response and yield complete sentences as they form.
    Retries up to 3 times on overloaded errors.
    """
    client = _get_anthropic()

    messages = conversation_history + [
        {"role": "user", "content": transcript},
    ]

    last_error = None
    for attempt, delay in enumerate([0] + _RETRY_DELAYS):
        if delay:
            print(f"Claude overloaded, retrying in {delay}s (attempt {attempt+1})...")
            await asyncio.sleep(delay)
        try:
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
            return  # success

        except anthropic.APIStatusError as e:
            if e.status_code == 529 or "overloaded" in str(e).lower():
                last_error = e
                continue
            raise
        except Exception:
            raise

    raise last_error


# ─── Edge TTS (free, no API key) ────────────────────────────────────────────

async def text_to_speech(text: str, language: str = "hi") -> bytes:
    """
    Convert text to MP3 audio using Edge TTS (Microsoft).
    Completely free, no API key needed.
    """
    voice = _TTS_VOICE.get(language, _TTS_VOICE["hi"])
    communicate = edge_tts.Communicate(text, voice)
    audio_data = b""
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_data += chunk["data"]
    return audio_data


# ─── ElevenLabs TTS (premium, requires API key) ─────────────────────────────

# Voice IDs for different languages (update with your preferred voices)
_ELEVENLABS_VOICE = {
    "en": "EXAVITQu4vr4xnSDxMaL",  # Bella (expressive female)
    "hi": "pNInz6obpgDQGcFmaJgB",  # Adam (multilingual)
    "mr": "pNInz6obpgDQGcFmaJgB",  # Adam (multilingual)
}


async def elevenlabs_tts(text: str, language: str = "hi") -> bytes:
    """
    Convert text to MP3 audio using ElevenLabs premium TTS.
    Requires ELEVENLABS_API_KEY environment variable.
    Returns empty bytes if not available.
    """
    client = _get_elevenlabs()
    if not client:
        # Fallback to Edge TTS if ElevenLabs not available
        return await text_to_speech(text, language)
    
    try:
        voice_id = _ELEVENLABS_VOICE.get(language, _ELEVENLABS_VOICE["hi"])
        
        # Run synchronous ElevenLabs call in executor to avoid blocking
        loop = asyncio.get_running_loop()
        audio_generator = await loop.run_in_executor(
            None,
            lambda: client.text_to_speech.convert(
                voice_id=voice_id,
                model_id="eleven_multilingual_v2",
                text=text,
            )
        )
        
        # Collect audio chunks
        audio_data = b"".join(audio_generator)
        return audio_data
        
    except Exception as e:
        print(f"ElevenLabs TTS error: {e}, falling back to Edge TTS")
        return await text_to_speech(text, language)


# ─── Hybrid TTS Router ──────────────────────────────────────────────────────

async def adaptive_tts(
    text: str, 
    context: dict, 
    language: str = "hi",
    add_pause: bool = False
) -> bytes:
    """
    Route TTS request to appropriate engine based on emotional context.
    
    Args:
        text: Text to synthesize
        context: Emotion detection result from detect_context()
        language: Language code
        add_pause: Add slight pause before audio (for premium voice)
        
    Returns:
        Audio bytes (MP3 format)
    """
    # Determine if premium TTS should be used
    use_premium = should_use_premium_tts(context)
    
    if use_premium and _get_elevenlabs():
        # Use premium TTS for emotional/crisis moments
        audio = await elevenlabs_tts(text, language)
        
        # Optional: Add natural pause for emphasis
        if add_pause:
            await asyncio.sleep(0.15)
    else:
        # Use free Edge TTS for normal conversation
        audio = await text_to_speech(text, language)
    
    return audio


# ─── Streaming pipeline ─────────────────────────────────────────────────────

async def process_turn_streaming(
    audio_bytes: bytes,
    conversation_history: list[dict],
    mimetype: str = "audio/webm",
    language: str = "hi",
) -> AsyncGenerator[dict, None]:
    """
    Full pipeline for one user turn, yielding events as they happen:

      {"event": "transcript",      "text": "..."}
      {"event": "sentence_text",   "text": "...", "index": 0}
      {"event": "sentence_audio",  "audio": b"...", "index": 0}
      {"event": "done",            "full_text": "..."}

    Raises ValueError if no speech detected.
    """
    transcript = await transcribe_audio(audio_bytes, mimetype, language)
    if not transcript:
        raise ValueError("No speech detected in audio")

    yield {"event": "transcript", "text": transcript}

    # Detect emotional context from user's input
    # This determines TTS routing for the entire response
    context = detect_context(transcript)
    
    full_response = ""
    sentence_index = 0

    async for sentence in stream_counselor_sentences(transcript, conversation_history, language):
        full_response += (" " if full_response else "") + sentence

        yield {"event": "sentence_text", "text": sentence, "index": sentence_index}

        # Use hybrid TTS router based on emotional context
        audio = await adaptive_tts(
            text=sentence,
            context=context,
            language=language,
            add_pause=(sentence_index == 0 and should_use_premium_tts(context))
        )
        
        yield {"event": "sentence_audio", "audio": audio, "index": sentence_index}

        sentence_index += 1

    yield {"event": "done", "full_text": full_response.strip()}
