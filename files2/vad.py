# vad.py
"""
Voice Activity Detection (VAD) for real-time speech detection.

This module provides simple energy-based VAD for detecting when a user
starts and stops speaking in a continuous audio stream.
"""

import numpy as np
from collections import deque


class SimpleVAD:
    """
    Simple energy-based Voice Activity Detection.
    
    Detects speech by monitoring audio energy levels and applying
    smoothing to avoid false triggers from noise.
    """
    
    def __init__(
        self,
        sample_rate: int = 16000,
        frame_duration_ms: int = 30,
        energy_threshold: float = 0.01,
        speech_pad_ms: int = 300,
        silence_duration_ms: int = 700,
    ):
        """
        Initialize VAD detector.
        
        Args:
            sample_rate: Audio sample rate in Hz
            frame_duration_ms: Frame size in milliseconds
            energy_threshold: RMS energy threshold for speech detection
            speech_pad_ms: Padding before/after speech to avoid cutting words
            silence_duration_ms: How long silence before considering speech ended
        """
        self.sample_rate = sample_rate
        self.frame_duration_ms = frame_duration_ms
        self.energy_threshold = energy_threshold
        self.speech_pad_ms = speech_pad_ms
        self.silence_duration_ms = silence_duration_ms
        
        # Calculate frame size in samples
        self.frame_size = int(sample_rate * frame_duration_ms / 1000)
        
        # Calculate silence threshold in frames
        self.silence_frames = int(silence_duration_ms / frame_duration_ms)
        
        # State tracking
        self.is_speech = False
        self.silence_counter = 0
        self.speech_frames = deque(maxlen=100)  # Keep recent history
        
    def calculate_energy(self, audio_chunk: bytes) -> float:
        """
        Calculate RMS energy of audio chunk.
        
        Args:
            audio_chunk: Raw audio bytes (16-bit PCM)
            
        Returns:
            RMS energy value
        """
        # Convert bytes to numpy array (assuming 16-bit PCM)
        try:
            audio_data = np.frombuffer(audio_chunk, dtype=np.int16)
            if len(audio_data) == 0:
                return 0.0
            
            # Calculate RMS energy
            energy = np.sqrt(np.mean(audio_data.astype(np.float32) ** 2))
            # Normalize to 0-1 range
            normalized_energy = energy / 32768.0  # Max value for int16
            
            return normalized_energy
        except Exception as e:
            print(f"VAD energy calculation error: {e}")
            return 0.0
    
    def process_frame(self, audio_chunk: bytes) -> dict:
        """
        Process audio frame and detect speech activity.
        
        Args:
            audio_chunk: Raw audio bytes
            
        Returns:
            dict with:
                - is_speech: bool - whether speech is currently detected
                - speech_started: bool - whether speech just started this frame
                - speech_ended: bool - whether speech just ended this frame
                - energy: float - current frame energy
        """
        energy = self.calculate_energy(audio_chunk)
        
        speech_detected = energy > self.energy_threshold
        speech_started = False
        speech_ended = False
        
        if speech_detected:
            # Speech detected
            self.silence_counter = 0
            
            if not self.is_speech:
                # Speech just started
                self.is_speech = True
                speech_started = True
            
            self.speech_frames.append(True)
            
        else:
            # No speech detected
            if self.is_speech:
                self.silence_counter += 1
                
                if self.silence_counter >= self.silence_frames:
                    # Silence threshold exceeded - speech ended
                    self.is_speech = False
                    speech_ended = True
                    self.silence_counter = 0
            
            self.speech_frames.append(False)
        
        return {
            "is_speech": self.is_speech,
            "speech_started": speech_started,
            "speech_ended": speech_ended,
            "energy": energy,
        }
    
    def reset(self):
        """Reset VAD state."""
        self.is_speech = False
        self.silence_counter = 0
        self.speech_frames.clear()


class DeepgramVAD:
    """
    Wrapper for Deepgram's built-in VAD.
    
    Uses Deepgram's interim results to detect speech boundaries,
    which is more reliable than energy-based VAD.
    """
    
    def __init__(self, silence_duration_ms: int = 700):
        """
        Initialize Deepgram VAD wrapper.
        
        Args:
            silence_duration_ms: How long to wait after last interim result
        """
        self.silence_duration_ms = silence_duration_ms
        self.last_interim_time = None
        self.is_speech = False
        
    def process_deepgram_result(self, result: dict, current_time: float) -> dict:
        """
        Process Deepgram streaming result.
        
        Args:
            result: Deepgram result dictionary
            current_time: Current timestamp
            
        Returns:
            dict with speech detection status
        """
        # Check if this is an interim result with speech
        is_final = result.get("is_final", False)
        speech_final = result.get("speech_final", False)
        
        has_transcript = False
        try:
            transcript = result.get("channel", {}).get("alternatives", [{}])[0].get("transcript", "")
            has_transcript = len(transcript.strip()) > 0
        except (IndexError, KeyError, AttributeError):
            pass
        
        speech_started = False
        speech_ended = False
        
        if has_transcript:
            # Update last activity time
            self.last_interim_time = current_time
            
            if not self.is_speech:
                # Speech just started
                self.is_speech = True
                speech_started = True
        
        # Check for speech end
        if self.is_speech and self.last_interim_time:
            silence_duration = (current_time - self.last_interim_time) * 1000  # ms
            
            if silence_duration >= self.silence_duration_ms or speech_final:
                # Speech ended
                self.is_speech = False
                speech_ended = True
        
        return {
            "is_speech": self.is_speech,
            "speech_started": speech_started,
            "speech_ended": speech_ended,
            "is_final": is_final or speech_final,
        }
    
    def reset(self):
        """Reset VAD state."""
        self.is_speech = False
        self.last_interim_time = None
