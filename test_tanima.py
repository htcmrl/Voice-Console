"""Kendi sesini tanima testi.
5 saniye konus, sistem:
  - Whisper ile metne cevirecek
  - Resemblyzer ile imzani kayitli imzanla karsilastiracak
  - Eslesme yuzdesini gosterecek
"""
import time
from audio.recorder import record_fixed
from stt.transcriber import transcribe
from speaker.enrollment import load_all_voiceprints
from speaker.verification import identify

print("Kayitli kullanicilar yukleniyor...")
voiceprints = load_all_voiceprints()
print(f"  Kayitli: {list(voiceprints.keys())}")

print("\n5 saniye konus... (Mesela: 'Merhaba ben rabia, bugun bir test yapiyorum')")
audio = record_fixed(5.0)

# 1) Whisper
t0 = time.time()
stt = transcribe(audio)
print(f"\nWhisper ({time.time()-t0:.1f}s): {stt['text']!r}")

# 2) Konusmaci tanima
t0 = time.time()
result = identify(audio, voiceprints)
print(f"\nKonusmaci tanima ({time.time()-t0:.1f}s):")
print(f"  Backend       : {result['backend']}")
print(f"  Esik          : {result['threshold']}")
print(f"  En yakin aday : {result['best_candidate']}")
print(f"  Benzerlik     : {result['similarity']:.3f}")
print(f"  Tum skorlar   : {result['scores']}")
if result['user_id']:
    print(f"\n  >>> KIMLIK ONAYLANDI: {result['user_id']} <<<")
else:
    print(f"\n  >>> YETKISIZ — esik gecilemedi <<<")