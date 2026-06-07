"""
sounddevice canlı kayıt sarmalayıcısı.
Iki kullanım modu:
  - record_fixed(seconds): belirli süre kaydet, numpy array döndür (enrollment için)
  - stream_utterances(threshold): generator — her tamamlanan cümleyi yield eder
"""
import queue
import numpy as np
import sounddevice as sd

from config import settings
from audio.vad import VADState


def list_devices() -> str:
    """Kullanılabilir cihazları listele."""
    return str(sd.query_devices())


def record_fixed(seconds: float,
                 sample_rate: int = settings.SAMPLE_RATE) -> np.ndarray:
    """Belirli süre kayıt (enrollment, test için)."""
    print(f"[recorder] {seconds:.1f}s kayıt başlıyor...")
    audio = sd.rec(int(seconds * sample_rate),
                   samplerate=sample_rate,
                   channels=settings.CHANNELS,
                   dtype=settings.DTYPE)
    sd.wait()
    return audio.flatten()


def stream_utterances(threshold: float,
                      sample_rate: int = settings.SAMPLE_RATE):
    """
    Canlı mikrofondan dinler, her tamamlanan cümleyi (utterance) yield eder.
    'event' callback'ler de yield edilir; çağıran uygun olanı işler.

    Yields:
        dict — {"event": ..., "utterance": ndarray|None, "rms": float}
    """
    block_samples = int(settings.BLOCK_DURATION * sample_rate)
    queue_max_size = 500  # ~25 saniyelik tampon
    vad = VADState(threshold=threshold, sample_rate=sample_rate)
    q: queue.Queue = queue.Queue(maxsize=queue_max_size)

    def callback(indata, frames, time_info, status):
        if status:
            # XRun veya buffer overflow gibi durumlar
            print(f"[recorder][warn] {status}")
        q.put(indata.copy())

    with sd.InputStream(samplerate=sample_rate,
                        channels=settings.CHANNELS,
                        dtype=settings.DTYPE,
                        blocksize=block_samples,
                        callback=callback):
        print("[recorder] Canlı dinleme aktif. (Ctrl+C ile durdur)")
        while True:
            block = q.get()
            result = vad.process_block(block.flatten())
            yield result
