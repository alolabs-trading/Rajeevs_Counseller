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
from persona import COUNSELOR_SYSTEM_PROMPT

_RETRY_DELAYS = [1, 2, 3]  # seconds between retries on overload


# ─── Singleton clients (created once, reused) ───────────────────────────────

_deepgram: DeepgramClient | None = None
_anthropic: anthropic.AsyncAnthropic | None = None


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


# ─── Deepgram STT ────────────────────────────────────────────────────────────

async def transcribe_audio(audio_bytes: bytes, mimetype: str = "audio/webm") -> str:
    """
    Transcribe audio bytes to text using Deepgram nova-2.
    Returns empty string if no speech detected.
    """
    client = _get_deepgram()

    loop = asyncio.get_running_loop()
    response = await loop.run_in_executor(
        None,
        lambda: client.listen.v1.media.transcribe_file(
            request=audio_bytes,
            model="nova-2",
            language="hi",
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
                system=COUNSELOR_SYSTEM_PROMPT,
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

# Hindi voices available in Edge TTS:
#   hi-IN-SwaraNeural   — female, warm
#   hi-IN-MadhurNeural  — male, calm
EDGE_VOICE = "hi-IN-SwaraNeural"  # Female voice for Saraswati


async def text_to_speech(text: str) -> bytes:
    """
    Convert text to MP3 audio using Edge TTS (Microsoft).
    Completely free, no API key needed. Supports Hindi natively.
    """
    communicate = edge_tts.Communicate(text, EDGE_VOICE)
    audio_data = b""
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_data += chunk["data"]
    return audio_data


# ─── Streaming pipeline ─────────────────────────────────────────────────────

async def process_turn_streaming(
    audio_bytes: bytes,
    conversation_history: list[dict],
    mimetype: str = "audio/webm",
) -> AsyncGenerator[dict, None]:
    """
    Full pipeline for one user turn, yielding events as they happen:

      {"event": "transcript",      "text": "..."}
      {"event": "sentence_text",   "text": "...", "index": 0}
      {"event": "sentence_audio",  "audio": b"...", "index": 0}
      {"event": "done",            "full_text": "..."}

    Raises ValueError if no speech detected.
    """
    transcript = await transcribe_audio(audio_bytes, mimetype)
    if not transcript:
        raise ValueError("No speech detected in audio")

    yield {"event": "transcript", "text": transcript}

    full_response = ""
    sentence_index = 0

    async for sentence in stream_counselor_sentences(transcript, conversation_history):
        full_response += (" " if full_response else "") + sentence

        yield {"event": "sentence_text", "text": sentence, "index": sentence_index}

        audio = await text_to_speech(sentence)
        yield {"event": "sentence_audio", "audio": audio, "index": sentence_index}

        sentence_index += 1

    yield {"event": "done", "full_text": full_response.strip()}
