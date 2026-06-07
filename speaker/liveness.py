"""
Liveness / İnsan sesi tespiti.

Gelen sesin gerçek bir insan konuşması olup olmadığını basit istatistiklerle değerlendirir:
  1) Konuşma hızı (hece/saniye) — kabaca onset/syllable nucleus tespitiyle
  2) Pitch (F0) varyasyonu — düz/robotik sentetik seslerde çok düşük
  3) Spektral düzlük (flatness) — gürültüde yüksek, konuşmada düşük

Üç testten en az ikisi geçerse "muhtemelen insan" denir.
Üretim için DNN tabanlı anti-spoof (RawNet2 vb.) tavsiye edilir.
"""
import numpy as np
import librosa

from config import settings


def estimate_speech_rate(audio: np.ndarray, sr: int) -> float:
    """Onset oranını hece/sn yaklaşımı olarak kullanır."""
    duration = len(audio) / sr
    if duration < 0.3:
        return 0.0
    onset_env = librosa.onset.onset_strength(y=audio, sr=sr,
                                             hop_length=settings.HOP_LENGTH)
    # Onsetleri ayıkla
    onsets = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr,
                                        hop_length=settings.HOP_LENGTH,
                                        units="time")
    return len(onsets) / duration


def estimate_pitch_variation(audio: np.ndarray, sr: int) -> float:
    """F0'ın standart sapması (Hz). Konuşmada genelde 15-50 Hz."""
    try:
        f0, voiced_flag, _ = librosa.pyin(audio,
                                          fmin=70, fmax=400,
                                          sr=sr,
                                          hop_length=settings.HOP_LENGTH)
        f0_voiced = f0[voiced_flag] if voiced_flag is not None else f0
        f0_voiced = f0_voiced[~np.isnan(f0_voiced)]
        if len(f0_voiced) < 5:
            return 0.0
        return float(np.std(f0_voiced))
    except Exception:
        return 0.0


def estimate_spectral_flatness(audio: np.ndarray) -> float:
    """Ortalama spektral düzlük. Beyaz gürültü ~1, konuşma ~0.1-0.3."""
    flatness = librosa.feature.spectral_flatness(y=audio,
                                                 hop_length=settings.HOP_LENGTH,
                                                 n_fft=settings.N_FFT)
    return float(np.mean(flatness))


def is_human(audio: np.ndarray,
             sr: int = settings.SAMPLE_RATE) -> dict:
    """
    Üç sinyali değerlendirir, en az 2/3 geçerse insan kabul.
    """
    audio = audio.astype(np.float32)

    rate = estimate_speech_rate(audio, sr)
    pitch_var = estimate_pitch_variation(audio, sr)
    flatness = estimate_spectral_flatness(audio)

    checks = {
        "speech_rate_ok": settings.SPEECH_RATE_MIN <= rate <= settings.SPEECH_RATE_MAX,
        "pitch_var_ok": pitch_var >= settings.PITCH_VAR_MIN,
        "flatness_ok": flatness <= settings.SPECTRAL_FLATNESS_MAX,
    }
    passed = sum(checks.values())
    verdict = passed >= 2

    return {
        "is_human": verdict,
        "passed": passed,
        "metrics": {
            "speech_rate_hz": rate,
            "pitch_variation_hz": pitch_var,
            "spectral_flatness": flatness,
        },
        "checks": checks,
    }
