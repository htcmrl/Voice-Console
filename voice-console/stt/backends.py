"""
STT (speech-to-text) backend'leri.

Soyut arayüz:
    backend.load() -> None       # modeli belleğe al
    backend.transcribe(audio, language) -> {"text", "segments", "language"}

İki implementasyon:
  - OpenAIWhisperBackend : Resmi openai-whisper paketi
  - FasterWhisperBackend : CTranslate2 tabanlı, CPU'da 3-4x daha hızlı,
                            daha az RAM (int8 quantization)

Hangisinin kullanılacağı settings.STT_BACKEND ile seçilir.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
import numpy as np

from config import settings


class STTBackend(ABC):
    name: str

    @abstractmethod
    def load(self) -> None: ...

    @abstractmethod
    def transcribe(self, audio: np.ndarray,
                   language: str = settings.WHISPER_LANGUAGE) -> dict: ...


# ---------- openai-whisper (mevcut) ----------

class OpenAIWhisperBackend(STTBackend):
    name = "whisper"

    def __init__(self):
        self._model = None

    def load(self) -> None:
        if self._model is not None:
            return
        import whisper
        print(f"[stt:whisper] Model yükleniyor: {settings.WHISPER_MODEL}")
        self._model = whisper.load_model(settings.WHISPER_MODEL)
        print("[stt:whisper] Hazır.")

    def transcribe(self, audio: np.ndarray,
                   language: str = settings.WHISPER_LANGUAGE) -> dict:
        self.load()
        audio = audio.astype(np.float32)
        peak = float(np.max(np.abs(audio))) if audio.size else 0.0
        if peak > 1.0:
            audio = audio / peak

        result = self._model.transcribe(
            audio,
            language=language,
            fp16=settings.WHISPER_FP16,
            no_speech_threshold=0.6,
            condition_on_previous_text=False,
        )
        return {
            "text": result.get("text", "").strip(),
            "segments": result.get("segments", []),
            "language": result.get("language", language),
        }


# ---------- faster-whisper (hızlı) ----------

class FasterWhisperBackend(STTBackend):
    """
    CTranslate2 tabanlı re-implementation.
    - CPU'da int8 quantization → ~4x hız, yarı RAM
    - GPU'da float16 desteği
    - Aynı model isimleri (tiny/base/small/medium/large)
    """
    name = "faster_whisper"

    def __init__(self):
        self._model = None

    def load(self) -> None:
        if self._model is not None:
            return
        try:
            from faster_whisper import WhisperModel
        except ImportError as e:
            raise RuntimeError(
                "faster-whisper kurulu değil. `pip install faster-whisper`"
            ) from e

        device = settings.FASTER_WHISPER_DEVICE      # "cpu" / "cuda" / "auto"
        compute = settings.FASTER_WHISPER_COMPUTE    # "int8" / "float16" / "float32"
        print(f"[stt:faster_whisper] Model yükleniyor: "
              f"{settings.WHISPER_MODEL} ({device}/{compute})")
        self._model = WhisperModel(settings.WHISPER_MODEL,
                                   device=device,
                                   compute_type=compute)
        print("[stt:faster_whisper] Hazır.")

    def transcribe(self, audio: np.ndarray,
                   language: str = settings.WHISPER_LANGUAGE) -> dict:
        self.load()
        audio = audio.astype(np.float32)
        peak = float(np.max(np.abs(audio))) if audio.size else 0.0
        if peak > 1.0:
            audio = audio / peak

        # faster-whisper bir generator döndürür — listeye çevir
        segments, info = self._model.transcribe(
            audio,
            language=language,
            beam_size=5,
            vad_filter=settings.FASTER_WHISPER_VAD_FILTER,  # dahili VAD
            condition_on_previous_text=False,
            no_speech_threshold=0.6,
        )
        seg_list = []
        full_text_parts = []
        for s in segments:
            seg_list.append({
                "start": s.start,
                "end": s.end,
                "text": s.text,
            })
            full_text_parts.append(s.text)

        return {
            "text": "".join(full_text_parts).strip(),
            "segments": seg_list,
            "language": info.language if hasattr(info, "language") else language,
        }


# ---------- Factory ----------

_REGISTRY = {
    "whisper": OpenAIWhisperBackend,
    "faster_whisper": FasterWhisperBackend,
}

_instance: STTBackend | None = None


def get_backend(name: str | None = None) -> STTBackend:
    global _instance
    name = name or settings.STT_BACKEND
    if _instance is None or _instance.name != name:
        if name not in _REGISTRY:
            raise ValueError(f"Bilinmeyen STT backend: {name}. "
                             f"Seçenekler: {list(_REGISTRY)}")
        _instance = _REGISTRY[name]()
    return _instance
