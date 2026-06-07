"""Ortam gürültüsünü ölçer ve konuşma eşiği hesaplar."""
import numpy as np
import sounddevice as sd

from config import settings


def rms(audio: np.ndarray) -> float:
    """Bir ses tamponunun RMS enerjisini döndürür."""
    if audio.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(audio.astype(np.float64)))))


def calibrate(seconds: float = settings.NOISE_CALIBRATION_SECONDS,
              sample_rate: int = settings.SAMPLE_RATE) -> dict:
    """
    Belirli süre kayıt yapıp ortam gürültüsünün RMS'ini ölçer.
    Konuşma için eşik değerini de hesaplar.

    Returns:
        {"noise_rms": float, "speech_threshold": float}
    """
    print(f"[noise] {seconds}s gürültü kalibrasyonu — lütfen sessiz kalın...")
    recording = sd.rec(int(seconds * sample_rate),
                       samplerate=sample_rate,
                       channels=settings.CHANNELS,
                       dtype=settings.DTYPE)
    sd.wait()
    noise_audio = recording.flatten()

    noise_level = rms(noise_audio)
    threshold = max(noise_level * settings.SPEECH_RMS_MULTIPLIER,
                    settings.MIN_SPEECH_RMS)

    print(f"[noise] Gürültü RMS = {noise_level:.5f} | "
          f"Konuşma eşiği = {threshold:.5f}")
    return {"noise_rms": noise_level, "speech_threshold": threshold}


if __name__ == "__main__":
    result = calibrate()
    print(result)
