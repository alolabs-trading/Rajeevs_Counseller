# emotion.py
"""
Emotion and crisis detection for adaptive TTS routing.

This module detects emotional intensity and crisis patterns in user speech
to determine when to use premium TTS (ElevenLabs) vs free TTS (Edge).
"""

import re


# --- Crisis patterns (require immediate premium voice) ---
CRISIS_PATTERNS = [
    r"want to die",
    r"end my life",
    r"kill myself",
    r"suicide",
    r"everything should end",
    r"sab khatam",
    r"mar jaana",
    r"khatam kar",
    r"जीना नहीं",
    r"मर जाना",
    r"आत्महत्या",
]

# --- High emotion patterns (benefit from expressive voice) ---
HIGH_EMOTION_PATTERNS = [
    r"very sad",
    r"depressed",
    r"can't handle",
    r"overwhelmed",
    r"exhausted",
    r"broken",
    r"hopeless",
    r"desperate",
    r"खूप वाईट",
    r"अत्यंत दुःखी",
    r"थकल",
    r"बहुत दुखी",
    r"टूट गया",
]


def detect_context(text: str) -> dict:
    """
    Detect emotional context in text.
    
    Args:
        text: Combined user transcript and AI response text
        
    Returns:
        dict with:
            - crisis: bool - whether crisis patterns detected
            - high_emotion: bool - whether high emotion patterns detected
    """
    if not text:
        return {"crisis": False, "high_emotion": False}
    
    text_lower = text.lower()
    
    # Check for crisis patterns
    crisis = any(re.search(pattern, text_lower) for pattern in CRISIS_PATTERNS)
    
    # Check for high emotion patterns
    high_emotion = any(re.search(pattern, text_lower) for pattern in HIGH_EMOTION_PATTERNS)
    
    return {
        "crisis": crisis,
        "high_emotion": high_emotion,
    }


def should_use_premium_tts(context: dict) -> bool:
    """
    Determine if premium TTS should be used based on context.
    
    Args:
        context: Output from detect_context()
        
    Returns:
        bool: True if premium TTS should be used
    """
    return context.get("crisis", False) or context.get("high_emotion", False)
