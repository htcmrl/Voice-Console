"""
END-TO-END test (mikrofon olmadan):

espeak-ng ile 3 farklı sesle (farklı pitch/voice) TR cümleler üretip:
  1) Konuşmacı backend'lerini (MFCC, Resemblyzer) karşılaştır
  2) STT backend'lerini (whisper, faster_whisper) karşılaştır
  3) Tam pipeline'ı (parse + execute) çalıştır

Bu, gerçek mikrofona benzer karakterli üç "konuşmacı" üretir.
Sonuçlar sentetik dry_run'dan çok daha gerçekçidir çünkü espeak konuşma
sinyali (gerçek formant + fonem dizilimi) üretir.
"""
import subprocess
from pathlib import Path
import time
import numpy as np
import soundfile as sf

from config import settings
from speaker.backends import MFCCBackend, ResemblyzerBackend
from speaker.liveness import is_human


# 3 farklı espeak konuşmacısı — voice, pitch, hız varyasyonu ile
SPEAKERS = {
    "alice": {"voice": "tr+f3", "pitch": 80,  "speed": 145},
    "bob":   {"voice": "tr+m2", "pitch": 35,  "speed": 130},
    "carol": {"voice": "tr+f5", "pitch": 65,  "speed": 160},
}

# Enrollment metni — kısa, fonetik çeşitli
ENROLL_TEXT = (
    "Merhaba bugün hava oldukça güzel. "
    "Bahçedeki çiçekler renk renk açmış durumda. "
    "Yarın sabah erken kalkıp şehir merkezine gideceğim. "
    "Doğal dil işleme projesinde ses tanıma çok ilginç bir konu. "
    "Öğretmen tahtaya büyük harflerle önemli bir not yazdı."
)

# Test cümleleri — komutları tetikleyecek
TEST_UTTERANCES = [
    "Tarih nedir",
    "Listele bakalım",
    "Sesi yetmiş yap",   # "yetmiş" Whisper'dan "70" olarak gelebilir, bilinçli zor örnek
    "Firefox aç",
]


def synth_with_espeak(text: str, voice: str, pitch: int, speed: int,
                      out_path: Path) -> np.ndarray:
    """espeak-ng ile sentez. 16 kHz mono WAV döndürür."""
    subprocess.run([
        "espeak-ng",
        "-v", voice,
        "-p", str(pitch),
        "-s", str(speed),
        "-w", str(out_path),
        text,
    ], check=True, capture_output=True)
    audio, sr = sf.read(out_path)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    if sr != settings.SAMPLE_RATE:
        import librosa
        audio = librosa.resample(audio.astype(np.float32),
                                 orig_sr=sr, target_sr=settings.SAMPLE_RATE)
    return audio.astype(np.float32)


def speaker_backend_comparison(out_dir: Path) -> dict:
    """Her backend için: enrollment + same-speaker + different-speaker testi."""
    print("\n" + "=" * 60)
    print("  KONUŞMACI BACKEND KARŞILAŞTIRMASI")
    print("=" * 60)

    enrollment_audio = {}
    second_audio = {}     # aynı konuşmacının 2. kaydı (farklı metin)
    for name, cfg in SPEAKERS.items():
        e_path = out_dir / f"{name}_enroll.wav"
        s_path = out_dir / f"{name}_second.wav"
        enrollment_audio[name] = synth_with_espeak(ENROLL_TEXT, **cfg,
                                                    out_path=e_path)
        # 2. kayıt — farklı metin, aynı ses
        second_audio[name] = synth_with_espeak(
            "Bu ikinci bir test kaydıdır. Konuşmacı aynı kişidir.",
            **cfg, out_path=s_path)

    backends = {
        "mfcc": MFCCBackend(),
        "resemblyzer": ResemblyzerBackend(),
    }
    results = {}
    for bname, backend in backends.items():
        print(f"\n--- Backend: {bname} ---")
        t0 = time.time()
        embs = {n: backend.embed(a) for n, a in enrollment_audio.items()}
        embs_second = {n: backend.embed(a) for n, a in second_audio.items()}
        t_embed = time.time() - t0
        print(f"  6 embedding süresi: {t_embed:.2f}s "
              f"(boyut={embs['alice'].shape})")

        # Aynı-konuşmacı vs farklı-konuşmacı
        same_scores = []
        diff_scores = []
        for n in SPEAKERS:
            same_scores.append(backend.similarity(embs[n], embs_second[n]))
            for m in SPEAKERS:
                if m != n:
                    diff_scores.append(backend.similarity(embs[n], embs[m]))

        same_min = min(same_scores)
        same_avg = np.mean(same_scores)
        diff_max = max(diff_scores)
        diff_avg = np.mean(diff_scores)
        margin = same_min - diff_max

        print(f"  Aynı kişi  (3 çift)   : min={same_min:.3f}, avg={same_avg:.3f}")
        print(f"  Farklı kişi (6 çift)  : max={diff_max:.3f}, avg={diff_avg:.3f}")
        print(f"  Margin (same_min - diff_max) = {margin:+.3f} "
              f"{'✓ ayrım iyi' if margin > 0.05 else '✗ overlap'}")

        results[bname] = {
            "same_min": same_min, "same_avg": same_avg,
            "diff_max": diff_max, "diff_avg": diff_avg,
            "margin": margin, "embed_time": t_embed,
        }
    return results, enrollment_audio


def stt_backend_comparison(out_dir: Path) -> dict:
    """faster_whisper vs whisper — hız + doğruluk."""
    print("\n" + "=" * 60)
    print("  STT BACKEND KARŞILAŞTIRMASI")
    print("=" * 60)

    # Tek konuşmacıyla test cümlelerini üret
    test_audios = {}
    for text in TEST_UTTERANCES:
        path = out_dir / f"test_{abs(hash(text)) % 10000}.wav"
        test_audios[text] = synth_with_espeak(
            text, **SPEAKERS["alice"], out_path=path)

    results = {"whisper": {}, "faster_whisper": {}}

    # whisper
    print("\n--- Backend: whisper (openai) ---")
    try:
        from stt.backends import OpenAIWhisperBackend
        be = OpenAIWhisperBackend()
        t0 = time.time()
        be.load()
        t_load = time.time() - t0
        print(f"  Model yükleme: {t_load:.2f}s")
        for text, audio in test_audios.items():
            t0 = time.time()
            r = be.transcribe(audio)
            dt = time.time() - t0
            print(f"  [{dt:.2f}s] {text!r:<25} → {r['text']!r}")
            results["whisper"][text] = {"output": r["text"], "time": dt}
    except Exception as e:
        print(f"  HATA: {e}")
        results["whisper"] = {"error": str(e)}

    # faster_whisper
    print("\n--- Backend: faster_whisper ---")
    try:
        from stt.backends import FasterWhisperBackend
        be = FasterWhisperBackend()
        t0 = time.time()
        be.load()
        t_load = time.time() - t0
        print(f"  Model yükleme: {t_load:.2f}s")
        for text, audio in test_audios.items():
            t0 = time.time()
            r = be.transcribe(audio)
            dt = time.time() - t0
            print(f"  [{dt:.2f}s] {text!r:<25} → {r['text']!r}")
            results["faster_whisper"][text] = {"output": r["text"], "time": dt}
    except Exception as e:
        print(f"  HATA: {e}")
        results["faster_whisper"] = {"error": str(e)}

    # Karşılaştırma
    print("\n--- Hız karşılaştırması ---")
    if "error" not in results["whisper"] and "error" not in results["faster_whisper"]:
        for text in TEST_UTTERANCES:
            t_w = results["whisper"][text]["time"]
            t_fw = results["faster_whisper"][text]["time"]
            speedup = t_w / t_fw if t_fw > 0 else 0
            print(f"  {text!r:<25}: whisper={t_w:.2f}s, "
                  f"faster={t_fw:.2f}s ({speedup:.1f}x)")

    return results, test_audios


def pipeline_test(test_audios: dict):
    """Parser + executor: STT çıktısını gerçek komutlara dönüştür."""
    print("\n" + "=" * 60)
    print("  TAM PIPELINE TESTİ (STT → parser → render)")
    print("=" * 60)
    from commands.parser import parse
    from commands.executor import _render
    from stt.backends import get_backend as get_stt
    be = get_stt()  # settings.STT_BACKEND
    be.load()
    for text, audio in test_audios.items():
        r = be.transcribe(audio)
        stt_text = r["text"]
        parsed = parse(stt_text)
        if parsed["matched"]:
            try:
                rendered = _render(parsed["command"]["action"],
                                   parsed["params"], parsed["keyword"])
            except Exception as e:
                rendered = f"<render hatası: {e}>"
            print(f"  Söylenen : {text!r}")
            print(f"  STT       → {stt_text!r}")
            print(f"  Komut     → {parsed['command']['name']} "
                  f"params={parsed['params']}")
            print(f"  Çalışacak → {rendered}\n")
        else:
            print(f"  Söylenen : {text!r}")
            print(f"  STT       → {stt_text!r}")
            print(f"  Komut     → (eşleşme yok){' / ' + parsed['error'] if parsed.get('error') else ''}\n")


def main():
    out_dir = Path(__file__).parent / "data" / "test_recordings"
    out_dir.mkdir(parents=True, exist_ok=True)

    spk_results, enroll_audio = speaker_backend_comparison(out_dir)
    stt_results, test_audios = stt_backend_comparison(out_dir)
    pipeline_test(test_audios)

    # Özet
    print("\n" + "=" * 60)
    print("  ÖZET")
    print("=" * 60)
    print(f"  MFCC margin           : {spk_results['mfcc']['margin']:+.3f}")
    print(f"  Resemblyzer margin    : {spk_results['resemblyzer']['margin']:+.3f}")
    print(f"  Tavsiye edilen backend: "
          f"{'resemblyzer' if spk_results['resemblyzer']['margin'] > spk_results['mfcc']['margin'] else 'mfcc'}")


if __name__ == "__main__":
    main()
