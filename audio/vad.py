"""
Voice Activity Detection (VAD).
RMS enerjisine bakar, eşik üstündeyse 'konuşma var' der.
Konuşma başladıktan sonra SILENCE_HANGOVER kadar sessizlik olunca cümle biter.
"""
from dataclasses import dataclass, field
import numpy as np

from config import settings
from audio.noise import rms


@dataclass
class VADState:
    """VAD durum makinesi."""
    threshold: float
    sample_rate: int = settings.SAMPLE_RATE
    in_speech: bool = False
    silence_blocks: int = 0
    block_duration: float = settings.BLOCK_DURATION
    collected: list = field(default_factory=list)
    speech_started_at: float = 0.0

    @property
    def silence_hangover_blocks(self) -> int:
        return int(settings.SILENCE_HANGOVER / self.block_duration)

    @property
    def max_blocks(self) -> int:
        return int(settings.MAX_UTTERANCE_DURATION / self.block_duration)

    def process_block(self, block: np.ndarray) -> dict:
        """
        Bir ses bloğunu işler.
        Döndürür:
          {"event": "start"|"end"|"continue"|"idle",
           "utterance": np.ndarray|None,
           "rms": float}
        """
        block_rms = rms(block)
        event = "idle"
        utterance = None

        if block_rms > self.threshold:
            # konuşma var
            if not self.in_speech:
                self.in_speech = True
                self.collected = []
                event = "start"
            self.collected.append(block)
            self.silence_blocks = 0
        else:
            if self.in_speech:
                # Sessiz blok ama konuşmanın içinde — hangover say
                self.collected.append(block)
                self.silence_blocks += 1
                if self.silence_blocks >= self.silence_hangover_blocks:
                    # Cümle bitti
                    utterance = np.concatenate(self.collected, axis=0).flatten()
                    duration = len(utterance) / self.sample_rate
                    if duration >= settings.MIN_UTTERANCE_DURATION:
                        event = "end"
                    else:
                        event = "idle"   # çok kısa, at
                        utterance = None
                    self.in_speech = False
                    self.silence_blocks = 0
                    self.collected = []
                else:
                    event = "continue"

        # Güvenlik: maks. uzunluğu aşarsa kes
        if self.in_speech and len(self.collected) >= self.max_blocks:
            utterance = np.concatenate(self.collected, axis=0).flatten()
            event = "end"
            self.in_speech = False
            self.silence_blocks = 0
            self.collected = []

        return {"event": event, "utterance": utterance, "rms": block_rms}
