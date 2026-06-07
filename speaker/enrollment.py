"""
Konuşmacı kayıt (enrollment).
Aktif backend (settings.SPEAKER_BACKEND) ile imza/embedding çıkarır.
"""
import time
import numpy as np
import soundfile as sf

from config import settings
from audio import recorder
from speaker.backends import get_backend


def read_enrollment_text() -> str:
    return settings.ENROLLMENT_TEXT.read_text(encoding="utf-8")


def enroll(user_id: str, duration: float = 35.0) -> dict:
    """
    Kaydedilenler:
      data/voiceprints/<user_id>.npy        — embedding (aktif backend)
      data/voiceprints/<user_id>.wav        — ham kayıt
      data/voiceprints/<user_id>.backend    — hangi backend kullanıldı

    Not: Backend değiştirilince eski .npy dosyaları geçersiz olur.
    test_signatures.py ya da enroll_user.py yeniden çağrılmalı.
    """
    settings.VOICEPRINTS_DIR.mkdir(parents=True, exist_ok=True)
    backend = get_backend()

    print("\n" + "=" * 60)
    print(f"KAYIT: {user_id}   (backend: {backend.name})")
    print("=" * 60)
    print(read_enrollment_text())
    print("=" * 60)
    print(f"Hazır olduğunuzda Enter'a basın — {duration:.0f}s kayıt yapılacak.")
    input()

    for i in range(3, 0, -1):
        print(f"  {i}...")
        time.sleep(1)
    print("  KAYIT BAŞLADI")

    audio = recorder.record_fixed(duration)
    print("  KAYIT BİTTİ")

    # WAV
    wav_path = settings.VOICEPRINTS_DIR / f"{user_id}.wav"
    sf.write(wav_path, audio, settings.SAMPLE_RATE)

    # Embedding
    print(f"[enroll] {backend.name} embedding çıkarılıyor...")
    emb = backend.embed(audio)
    npy_path = settings.VOICEPRINTS_DIR / f"{user_id}.npy"
    np.save(npy_path, emb)

    # Backend etiketi
    (settings.VOICEPRINTS_DIR / f"{user_id}.backend").write_text(backend.name)

    print(f"[enroll] Kaydedildi:")
    print(f"  Ses:       {wav_path}")
    print(f"  Embedding: {npy_path} (boyut={emb.shape}, backend={backend.name})")

    return {"user_id": user_id, "embedding": emb,
            "wav_path": str(wav_path), "npy_path": str(npy_path),
            "backend": backend.name}


def load_all_voiceprints() -> dict:
    """
    Diskteki tüm embedding'leri yükle.
    Sadece aktif backend ile kaydedilenler döner; uyumsuz olanlar atlanır.
    """
    settings.VOICEPRINTS_DIR.mkdir(parents=True, exist_ok=True)
    active = get_backend().name
    prints = {}
    skipped = []
    for npy_file in settings.VOICEPRINTS_DIR.glob("*.npy"):
        backend_file = npy_file.with_suffix(".backend")
        recorded = backend_file.read_text().strip() if backend_file.exists() else "mfcc"
        if recorded != active:
            skipped.append((npy_file.stem, recorded))
            continue
        prints[npy_file.stem] = np.load(npy_file)
    if skipped:
        print(f"[enroll] Aktif backend ({active}) ile uyumsuz "
              f"{len(skipped)} kayıt atlandı:")
        for uid, bk in skipped:
            print(f"  - {uid} ({bk}) → enroll_user.py ile yeniden kaydet")
    return prints


if __name__ == "__main__":
    import sys
    user_id = sys.argv[1] if len(sys.argv) > 1 else input("Kullanıcı adı: ")
    duration = float(sys.argv[2]) if len(sys.argv) > 2 else 35.0
    enroll(user_id, duration=duration)
