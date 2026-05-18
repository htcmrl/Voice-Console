"""5 saniye kayit + Whisper transkripsiyon testi."""
import time
from audio.recorder import record_fixed
from stt.transcriber import transcribe

print("5 saniye konus...")
audio = record_fixed(5.0)

print("Whisper yukleniyor...")
t0 = time.time()
result = transcribe(audio)
elapsed = time.time() - t0

print(f"Sure: {elapsed:.1f}s")
print(f"Metin: {result['text']!r}")