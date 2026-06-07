"""
Sözlü Komutla Çalışan Konsol — Push-to-Talk modlu ana döngü

İki mod:
  1) PTT MODU (varsayılan): "konsol dinle" ile başlat, "konsol tamam" ile bitir.
     Aradaki her şey tek bir cümle olarak toplanır ve işlenir.
  2) KLASİK MOD: settings.PTT_START_PHRASE boşsa eski sessizlik-tabanlı akış.
"""
import argparse
import sys
import time
import re
import numpy as np

from config import settings
from audio import noise, recorder
from speaker.enrollment import load_all_voiceprints
from speaker.verification import identify
from speaker.liveness import is_human
from speaker.backends import get_backend as get_speaker_backend
from stt.transcriber import transcribe, get_model as preload_stt
from commands.parser import parse, _tr_lower
from commands.executor import execute, ExitRequested
from commands.registry import describe_all


def banner():
    print("=" * 60)
    print("  SÖZLÜ KOMUT KONSOLU")
    print("=" * 60)
    print(f"  STT backend       : {settings.STT_BACKEND} "
          f"(model={settings.WHISPER_MODEL}, lang={settings.WHISPER_LANGUAGE})")
    print(f"  Speaker backend   : {settings.SPEAKER_BACKEND}")
    ptt = getattr(settings, "PTT_START_PHRASE", "")
    if ptt:
        print(f"  Mod               : Push-to-Talk")
        print(f"  Başlangıç ifadesi : '{ptt}'")
        print(f"  Bitiş ifadesi     : '{settings.PTT_STOP_PHRASE}'")
    else:
        print(f"  Mod               : Klasik (sessizlik tabanlı)")
    print("=" * 60)
    print("  Tanımlı komutlar:")
    print(describe_all())
    print("=" * 60)


def contains_phrase(text: str, phrase: str) -> bool:
    """text içinde phrase olup olmadığını sorar (TR lowercase + esnek boşluk)."""
    if not phrase:
        return False
    norm_text = _tr_lower(text)
    norm_phrase = _tr_lower(phrase)
    # phrase'i boşluk esnek hale getir (örn. 'konsol  dinle' de eşlessin)
    pat = r"\b" + r"\s+".join(re.escape(p) for p in norm_phrase.split()) + r"\b"
    return re.search(pat, norm_text) is not None


def strip_phrase(text: str, phrase: str) -> str:
    """text'ten phrase'i çıkarır."""
    norm_phrase = _tr_lower(phrase)
    pat = r"\b" + r"\s+".join(re.escape(p) for p in norm_phrase.split()) + r"\b"
    return re.sub(pat, "", _tr_lower(text)).strip()


def process_utterance(audio, args, voiceprints):
    """Bir cümleyi işle: liveness → konuşmacı → STT → parser → execute.
    Returns: True (devam) / False (çıkış istendi)"""
    duration = len(audio) / settings.SAMPLE_RATE
    print(f"[main] << cümle hazır ({duration:.2f}s)")

    t0 = time.time()
    if not args.no_liveness:
        live = is_human(audio)
        if not live["is_human"]:
            print(f"[main]    LIVENESS BAŞARISIZ ({live['passed']}/3) — atlanıyor")
            return True

    if not args.no_speaker_check and voiceprints:
        ident = identify(audio, voiceprints)
        if ident["user_id"] is None:
            print(f"[main]    YETKİSİZ — en yakın: {ident['best_candidate']}"
                  f" ={ident['similarity']:.3f} | eşik={ident['threshold']}")
            return True
        print(f"[main]    Konuşmacı: {ident['user_id']} "
              f"(sim={ident['similarity']:.3f}, {ident['backend']})")

    t_stt = time.time()
    stt = transcribe(audio)
    text = stt["text"]
    if not text:
        print(f"[main]    (boş transkripsiyon, STT={time.time()-t_stt:.2f}s)")
        return True
    print(f"[main]    Metin: {text!r}  (STT={time.time()-t_stt:.2f}s)")

    # PTT işaretlerini temizle (komut parser'ına bunlar gitmesin)
    start_phrase = getattr(settings, "PTT_START_PHRASE", "")
    stop_phrase = getattr(settings, "PTT_STOP_PHRASE", "")
    clean_text = text
    if start_phrase:
        clean_text = strip_phrase(clean_text, start_phrase)
    if stop_phrase:
        clean_text = strip_phrase(clean_text, stop_phrase)

    if not clean_text:
        print("[main]    (sadece PTT işaretleri vardı, komut yok)")
        return True

    parsed = parse(clean_text)
    if parsed.get("error"):
        print(f"[main]    Parametre hatası: {parsed['error']}")
        return True
    if not parsed["matched"]:
        print(f"[main]    Tanımlı komut yok.")
        return True
    print(f"[main]    Komut: {parsed['command']['name']} "
          f"(pattern={parsed['keyword']!r}, params={parsed['params']})")

    try:
        execute(parsed)
    except ExitRequested:
        print("[main] Çıkış komutu alındı.")
        return False
    print(f"[main]    Toplam süre: {time.time()-t0:.2f}s")
    return True


def run_classic(args, threshold, voiceprints):
    """Klasik: sessizlik tabanlı cümle ayırma."""
    print("\n[main] Dinleme başladı. Konuşun!\n")
    for event in recorder.stream_utterances(threshold):
        ev = event["event"]
        if ev == "start":
            print("[main] >> konuşma başladı")
        elif ev == "end":
            if not process_utterance(event["utterance"], args, voiceprints):
                break


def run_ptt(args, threshold, voiceprints):
    """Push-to-Talk: 'konsol dinle' ile aç, 'konsol tamam' ile kapat."""
    start_phrase = settings.PTT_START_PHRASE
    stop_phrase = settings.PTT_STOP_PHRASE

    print(f"\n[main] PTT modu aktif.")
    print(f"  Komut almak için: '{start_phrase}' ile başla, '{stop_phrase}' ile bitir.")
    print(f"  Örnek: '{start_phrase} ... tarih nedir ... {stop_phrase}'\n")

    # Recording state
    recording = False
    buffer = []   # ndarray parçaları
    last_check_text = ""

    print("[main] >> Bekleniyor: '" + start_phrase + "'")

    for event in recorder.stream_utterances(threshold):
        ev = event["event"]
        if ev == "end":
            audio = event["utterance"]
            # Her bitmiş cümleyi STT'ye gönderip PTT işareti var mı bak
            stt = transcribe(audio)
            text = stt["text"]
            if not text:
                continue
            print(f"[main]    duydu: {text!r}")

            has_start = contains_phrase(text, start_phrase)
            has_stop = contains_phrase(text, stop_phrase)

            if not recording:
                if has_start:
                    print(f"[main] >>> KAYIT BAŞLADI ('{start_phrase}' algılandı)")
                    recording = True
                    buffer = []
                    # Eğer aynı cümlede bitiş de varsa — tek cümlede komut
                    if has_stop:
                        print(f"[main] <<< KAYIT BİTTİ ('{stop_phrase}' algılandı, aynı cümlede)")
                        recording = False
                        if not process_utterance(audio, args, voiceprints):
                            return
                        print("\n[main] >> Bekleniyor: '" + start_phrase + "'")
                    else:
                        # başlangıç cümlesi de buffer'a girsin (komut metni içerebilir)
                        buffer.append(audio)
                # else: konuşma görmezden gelinir
            else:
                buffer.append(audio)
                if has_stop:
                    print(f"[main] <<< KAYIT BİTTİ ('{stop_phrase}' algılandı)")
                    recording = False
                    combined = np.concatenate(buffer)
                    if not process_utterance(combined, args, voiceprints):
                        return
                    buffer = []
                    print("\n[main] >> Bekleniyor: '" + start_phrase + "'")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-speaker-check", action="store_true")
    ap.add_argument("--no-liveness", action="store_true")
    ap.add_argument("--list-devices", action="store_true")
    ap.add_argument("--commands", action="store_true",
                    help="Tanımlı komutları yazdır ve çık")
    ap.add_argument("--classic", action="store_true",
                    help="PTT'yi atla, sessizlik tabanlı moda zorla")
    args = ap.parse_args()

    if args.list_devices:
        print(recorder.list_devices())
        return
    if args.commands:
        print(describe_all())
        return

    banner()

    cal = noise.calibrate()
    threshold = cal["speech_threshold"]

    speaker_backend = get_speaker_backend()
    print(f"[main] Speaker backend: {speaker_backend.name}")

    voiceprints = load_all_voiceprints()
    if voiceprints:
        print(f"[main] Yetkili kullanıcılar: {list(voiceprints.keys())}")
    elif not args.no_speaker_check:
        print("[main] UYARI: Kayıt yok, konuşmacı doğrulaması atlanacak.")
        args.no_speaker_check = True

    print("[main] STT ısınıyor...")
    preload_stt()

    try:
        ptt = getattr(settings, "PTT_START_PHRASE", "")
        if ptt and not args.classic:
            run_ptt(args, threshold, voiceprints)
        else:
            run_classic(args, threshold, voiceprints)
    except KeyboardInterrupt:
        print("\n[main] Ctrl+C ile durduruldu.")
        sys.exit(0)


if __name__ == "__main__":
    main()