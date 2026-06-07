"""
Konuşmacı temsil (embedding) backend'leri.

Soyut arayüz:
    backend.embed(audio) -> np.ndarray
    backend.similarity(emb_a, emb_b) -> float [-1..1]
    backend.default_threshold -> float

İki implementasyon:
  - MFCCBackend         : librosa MFCC mean+std, hızlı ama orta doğrulukta
  - ResemblyzerBackend  : GE2E ile eğitilmiş 256-d sinir ağı embedding, daha güçlü

Hangisinin kullanılacağı settings.SPEAKER_BACKEND ile seçilir.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
import numpy as np

from config import settings


class SpeakerBackend(ABC):
    name: str
    default_threshold: float

    @abstractmethod
    def embed(self, audio: np.ndarray) -> np.ndarray:
        """Bir ses dizisinden konuşmacı imzası (embedding) çıkarır."""

    @abstractmethod
    def similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """İki embedding arasındaki benzerlik (-1..1)."""


# ---------- MFCC backend (mevcut, hafif) ----------

class MFCCBackend(SpeakerBackend):
    name = "mfcc"
    default_threshold = 0.75

    def embed(self, audio: np.ndarray) -> np.ndarray:
        # Lazy import — librosa zaten kurulu olmalı
        from speaker.features import build_voiceprint
        return build_voiceprint(audio).astype(np.float32)

    def similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        from speaker.features import cosine_similarity
        return cosine_similarity(a, b)


# ---------- Resemblyzer backend (sinir ağı, daha güçlü) ----------

class ResemblyzerBackend(SpeakerBackend):
    """
    Resemblyzer = pretrained GE2E speaker encoder (256-d, L2 normalized).
    İlk yüklemede ~17 MB model otomatik iner.
    """
    name = "resemblyzer"
    default_threshold = 0.70   # GE2E için tipik eşik

    def __init__(self):
        self._encoder = None

    @property
    def encoder(self):
        if self._encoder is None:
            try:
                from resemblyzer import VoiceEncoder
            except ImportError as e:
                raise RuntimeError(
                    "resemblyzer kurulu değil. `pip install resemblyzer`"
                ) from e
            print("[speaker] Resemblyzer VoiceEncoder yükleniyor...")
            self._encoder = VoiceEncoder(verbose=False)
            print("[speaker] Resemblyzer hazır.")
        return self._encoder

    def embed(self, audio: np.ndarray) -> np.ndarray:
        from resemblyzer import preprocess_wav
        audio = audio.astype(np.float32)
        # preprocess_wav 16 kHz'e resample + VAD + normalize yapar
        wav = preprocess_wav(audio, source_sr=settings.SAMPLE_RATE)
        return self.encoder.embed_utterance(wav).astype(np.float32)

    def similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        # L2 normalize edilmiş embedding'lerde inner product = cosine sim
        an = np.linalg.norm(a)
        bn = np.linalg.norm(b)
        if an < 1e-9 or bn < 1e-9:
            return 0.0
        return float(np.dot(a, b) / (an * bn))


# ---------- Factory ----------

_REGISTRY = {
    "mfcc": MFCCBackend,
    "resemblyzer": ResemblyzerBackend,
}

_instance: SpeakerBackend | None = None


def get_backend(name: str | None = None) -> SpeakerBackend:
    """Tekil (singleton) backend örneğini döndürür."""
    global _instance
    name = name or settings.SPEAKER_BACKEND
    if _instance is None or _instance.name != name:
        if name not in _REGISTRY:
            raise ValueError(f"Bilinmeyen backend: {name}. "
                             f"Seçenekler: {list(_REGISTRY)}")
        _instance = _REGISTRY[name]()
    return _instance


def get_threshold() -> float:
    """Aktif backend için settings'ten ya da default'tan eşik döndür."""
    backend = get_backend()
    custom = settings.SPEAKER_SIMILARITY_THRESHOLDS.get(backend.name)
    return custom if custom is not None else backend.default_threshold
