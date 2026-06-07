"""
Kayıtlı imzaların karşılaştırılması ve grafikli raporu.

Aktif backend ile (settings.SPEAKER_BACKEND) çalışır.
Bu backend ile kaydedilmemiş kullanıcılar atlanır.

Kullanım:
  python test_signatures.py
"""
from pathlib import Path
import numpy as np
import soundfile as sf

from config import settings
from speaker.enrollment import load_all_voiceprints
from speaker.backends import get_backend, get_threshold
from speaker.liveness import is_human
from reports.plotter import full_report


def main():
    output_dir = Path(__file__).parent / "reports" / "output"
    backend = get_backend()
    print(f"=== Aktif backend: {backend.name} (eşik={get_threshold()}) ===\n")

    voiceprints = load_all_voiceprints()
    if not voiceprints:
        print("Hiç kayıt yok. Önce: python enroll_user.py <isim>")
        return

    print(f"{len(voiceprints)} kullanıcı: {list(voiceprints.keys())}\n")

    # WAV'leri yükle (rapor + liveness için)
    wavs = {}
    for npy_file in settings.VOICEPRINTS_DIR.glob("*.npy"):
        backend_file = npy_file.with_suffix(".backend")
        recorded = backend_file.read_text().strip() if backend_file.exists() else "mfcc"
        if recorded != backend.name:
            continue
        wav_path = npy_file.with_suffix(".wav")
        if wav_path.exists():
            audio, sr = sf.read(wav_path)
            if sr != settings.SAMPLE_RATE:
                import librosa
                audio = librosa.resample(audio.astype(np.float32),
                                         orig_sr=sr,
                                         target_sr=settings.SAMPLE_RATE)
            wavs[npy_file.stem] = audio.astype(np.float32)

    # 1) Benzerlik matrisi
    print("--- Benzerlik matrisi (kosinüs) ---")
    users = list(voiceprints)
    print(" " * 12, *[f"{u:>10}" for u in users])
    sims_off_diag = []
    for u1 in users:
        row_vals = []
        for u2 in users:
            s = backend.similarity(voiceprints[u1], voiceprints[u2])
            row_vals.append(s)
            if u1 != u2:
                sims_off_diag.append(s)
        print(f"{u1:>12}", *[f"{v:>10.3f}" for v in row_vals])

    # 2) Liveness
    print("\n--- Liveness ---")
    for user, audio in wavs.items():
        r = is_human(audio)
        m = r["metrics"]
        print(f"{user:>12}: human={r['is_human']} ({r['passed']}/3) "
              f"hız={m['speech_rate_hz']:.2f}/s, "
              f"pitch_std={m['pitch_variation_hz']:.1f}Hz, "
              f"flat={m['spectral_flatness']:.3f}")

    # 3) Grafikler
    print(f"\n--- Grafikler → {output_dir} ---")
    paths = full_report(voiceprints, wavs, output_dir)
    for k, v in paths.items():
        if hasattr(v, "exists"):
            print(f"  {k}: {v}")

    # 4) Eşik değerlendirme
    if sims_off_diag:
        avg = float(np.mean(sims_off_diag))
        mx = float(np.max(sims_off_diag))
        th = get_threshold()
        print(f"\n--- Özet ---")
        print(f"  Farklı kişiler arası ortalama benzerlik: {avg:.3f}")
        print(f"  Farklı kişiler arası MAX benzerlik     : {mx:.3f}")
        print(f"  Aktif eşik                              : {th}")
        if mx > th:
            print(f"  UYARI: Farklı kişiler eşiği aşıyor → false-accept riski.")
        else:
            print(f"  Eşik tüm farklı kişileri reddediyor — temiz ayrım.")


if __name__ == "__main__":
    main()
