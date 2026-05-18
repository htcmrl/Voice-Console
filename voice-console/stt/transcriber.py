"""
STT facade — settings.STT_BACKEND ile seçilen backend'i çağırır.
Geriye dönük uyumlulukta `transcribe()` ve `get_model()` aynı isimlerle var.
"""
import numpy as np

from config import settings
from stt.backends import get_backend


def get_model():
    """Modeli yükle (lazy)."""
    backend = get_backend()
    backend.load()
    return backend


def transcribe(audio: np.ndarray,
               language: str = settings.WHISPER_LANGUAGE) -> dict:
    return get_backend().transcribe(audio, language=language)
