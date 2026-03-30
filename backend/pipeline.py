"""
pipeline.py — Sentence-streaming audio pipeline for Zen Counselor V1.

Flow:
  audio bytes (webm/ogg)
    → Deepgram STT  (nova-2, ~300ms)
    → Claude Sonnet (streaming, sentence-by-sentence)
    → ElevenLabs TTS (per sentence, ~200ms each)

The key optimization: Claude streams tokens, we detect sentence boundaries,
and fire TTS for each sentence immediately. The client starts hearing Aria
while she's still generating the rest of her response.
"""

import os
import re
import asyncio
from typing import AsyncGenerator

import anthropic
from deepgram import DeepgramClient
from elevenlabs.client import ElevenLabs
from elevenlabs import VoiceSettings
from persona import COUNSELOR_SYSTEM_PROMPT


# ─── Singleton clients (created once, reused) ───────────────────────────────

_deepgram: DeepgramClient | None = None
_elevenlabs: ElevenLabs | None = None
_anthropic: anthropic.AsyncAnthropic | None = None


def _get_deepgram() -> DeepgramClient:
    global _deepgram
    if _deepgram is None:
        _deepgram = DeepgramClient(api_key=os.environ["DEEPGRAM_API_KEY"])
    return _deepgram


def _get_elevenlabs() -> ElevenLabs:
    global _elevenlabs
    if _elevenlabs is None:
        _elevenlabs = ElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"])
    return _elevenlabs


def _get_anthropic() -> anthropic.AsyncAnthropic:
    global _anthropic
    if _anthropic is None:
        _anthropic = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _anthropic


# ─── Deepgram STT ────────────────────────────────────────────────────────────

async def transcribe_audio(audio_bytes: bytes, mimetype: str = "audio/webm") -> str:
    """
    Transcribe audio bytes to text using Deepgram nova-2.
    Uses the v6 SDK REST API (listen.v1.media.transcribe_file).
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

# Matches end of a sentence: . or ? or ! followed by whitespace or end-of-string.
# Avoids splitting on things like "Dr." or "3.5" by requiring the sentence-ender
# to follow a letter or closing quote.
_SENTENCE_END = re.compile(r'(?<=[a-zA-Z\"\'\u2019\u201D])[.!?](?:\s|$)')


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
        # Split at the end of the matched punctuation
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
    This lets us fire TTS per-sentence instead of waiting for the full response.
    """
    client = _get_anthropic()

    messages = conversation_history + [
        {"role": "user", "content": transcript},
    ]

    buffer = ""
    async with client.messages.stream(
        model="claude-sonnet-4-6",
        max_tokens=250,
        system=COUNSELOR_SYSTEM_PROMPT,
        messages=messages,
        temperature=0.7,
    ) as stream:
        async for chunk in stream.text_stream:
            buffer += chunk
            sentences, buffer = _extract_sentences(buffer)
            for sentence in sentences:
                yield sentence

    # Yield any remaining text as the final sentence
    remaining = buffer.strip()
    if remaining:
        yield remaining


# ─── ElevenLabs TTS ──────────────────────────────────────────────────────────

VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"  # George — free-tier default, calm male voice


async def text_to_speech(text: str) -> bytes:
    """
    Convert a sentence to MP3 audio using ElevenLabs.
    Uses multilingual_v2 which is available on free tier.
    Returns raw MP3 bytes.
    """
    client = _get_elevenlabs()
    loop = asyncio.get_running_loop()

    def _convert():
        audio_stream = client.text_to_speech.convert(
            text=text,
            voice_id=VOICE_ID,
            model_id="eleven_multilingual_v2",
            output_format="mp3_44100_128",
        )
        return b"".join(audio_stream)

    return await loop.run_in_executor(None, _convert)


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
    # Stage 1: STT
    transcript = await transcribe_audio(audio_bytes, mimetype)
    if not transcript:
        raise ValueError("No speech detected in audio")

    yield {"event": "transcript", "text": transcript}

    # Stage 2+3: Stream sentences from Claude, TTS each one immediately
    full_response = ""
    sentence_index = 0

    async for sentence in stream_counselor_sentences(transcript, conversation_history):
        full_response += (" " if full_response else "") + sentence

        yield {"event": "sentence_text", "text": sentence, "index": sentence_index}

        # TTS this sentence immediately — don't wait for the rest
        audio = await text_to_speech(sentence)
        yield {"event": "sentence_audio", "audio": audio, "index": sentence_index}

        sentence_index += 1

    yield {"event": "done", "full_text": full_response.strip()}
