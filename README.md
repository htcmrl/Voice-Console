# Sözlü Komut Konsolu

Sesle çalışan, konuşmacıyı tanıyan, parametreli komutları yürüten Python konsolu.
Bu sürümde **üç büyük geliştirme** entegre edildi:

1. **Daha güçlü konuşmacı tanıma** — Resemblyzer (GE2E 256-d sinir ağı embedding) backend.
2. **Daha hızlı STT** — faster-whisper (CTranslate2, CPU'da ~3-4x).
3. **Parametreli komut sistemi** — `"ses {level}"`, `"ara {query:rest}"`, vb.

## Mimari

```
voice-console/
├── config/settings.py                # Backend seçimi + tüm sabitler
├── audio/
│   ├── recorder.py                   # sounddevice canlı kayıt
│   ├── vad.py                        # Sessizlik tabanlı cümle bölme
│   └── noise.py                      # Gürültü kalibrasyonu
├── speaker/
│   ├── backends.py        [YENİ]     # MFCCBackend | ResemblyzerBackend
│   ├── features.py                   # MFCC + delta öznitelikleri (MFCC backend için)
│   ├── enrollment.py     [yenilendi] # Aktif backend'e göre embedding kaydı
│   ├── verification.py   [yenilendi] # Aktif backend ile identify
│   └── liveness.py                   # İnsan sesi tespiti
├── stt/
│   ├── backends.py        [YENİ]     # OpenAIWhisperBackend | FasterWhisperBackend
│   └── transcriber.py    [yenilendi] # Backend facade
├── commands/
│   ├── registry.py       [yenilendi] # Pattern + slot + param spec
│   ├── parser.py         [yenilendi] # Regex pattern matching + param doğrulama
│   └── executor.py       [yenilendi] # shlex.quote ile güvenli render
├── reports/plotter.py                # Matplotlib grafik raporları
├── data/
│   ├── enrollment_text.txt           # Türkçe fonetik dengeli metin
│   └── voiceprints/                  # <isim>.wav, <isim>.npy, <isim>.backend
├── enroll_user.py                    # Kayıt scripti
├── test_signatures.py    [yenilendi] # Aktif backend ile karşılaştırma + grafik
├── test_commands.py       [YENİ]     # Parser + executor birim testleri
├── test_e2e.py            [YENİ]     # espeak-ng ile uçtan uca test
├── main.py               [yenilendi] # Ana döngü (backend bilgili)
├── requirements.txt
└── README.md
```

## Kurulum

```bash
# Sistem bağımlılıkları (Linux)
sudo apt-get install -y portaudio19-dev ffmpeg espeak-ng

# Python ortamı
python3.10 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

espeak-ng yalnızca `test_e2e.py` için gerekli (mikrofonsuz uçtan uca test).

## Backend Seçimi (`config/settings.py`)

```python
# "mfcc"        : Hızlı, ek bağımlılık yok, ama overlap riski yüksek
# "resemblyzer" : ~17 MB pretrained model, çok daha doğru
SPEAKER_BACKEND = "resemblyzer"

# "whisper"        : Resmi OpenAI Whisper
# "faster_whisper" : CTranslate2, CPU'da 3-4x hız + yarı RAM (int8)
STT_BACKEND = "faster_whisper"
```

**Önemli:** Backend değiştirince eski `.npy` imzaları farklı boyutta/dağılımdadır;
`load_all_voiceprints()` aktif backend ile uyumsuz olanları otomatik atlar
(`.backend` etiket dosyalarına bakar). Backend değişirse her kullanıcıyı
yeniden enroll etmek gerekir.

## Yeni Komut Sistemi

Eski biçim hâlâ destekleniyor (`COMMAND_REGISTRY = {kw: cmd}`), ama yeni
biçim `commands/registry.py: DEFAULT_COMMANDS` ile çok daha güçlü:

```python
{
    "name": "ses_seviyesi",
    "patterns": [
        "ses {level}",
        "sesi {level} yap",
        "ses seviyesi {level}",
    ],
    "action": "amixer -q set Master {level}%",
    "params": {"level": {"type": "int", "min": 0, "max": 100}},
    "description": "Master ses seviyesini değiştirir (0-100)",
},
```

**Pattern özellikleri:**
- Birden çok eşanlamlı pattern → tek komut
- `{slot}` tek kelime yakalar, `{slot:rest}` cümle sonuna kadar
- `params` ile tip ve min/max doğrulaması (`int`, `word`, `rest`)
- En çok literal karakter eşleyen pattern kazanır (spesifiklik önceliği)
- Action template parametreleri `shlex.quote` ile escape edilir → shell injection güvenli
- `{__keyword__}` özel placeholder eşleşen pattern'i ifade eder
- `"action": "__EXIT__"` özel — programı sonlandırır

Tanımlı komutları görmek için:
```bash
python main.py --commands
```

## Üç Kademeli Kullanım

### 1) Komut sistemini test et (ses gerekmez)

```bash
python test_commands.py
```

Pattern derleme, parametre yakalama, range/tip doğrulama, shell-injection
koruması, executor — hepsi 5 grupta birim test.

### 2) Kullanıcı kaydı (enrollment)

```bash
python enroll_user.py alice    # 35 sn varsayılan
python enroll_user.py bob
python enroll_user.py carol
```

Bu, aktif backend'in (örn. resemblyzer) embedding'ini çıkarır ve
`data/voiceprints/alice.{wav, npy, backend}` üretir.

### 3) Üç kişiyi karşılaştır, rapor çıkar

```bash
python test_signatures.py
```

Konsolda benzerlik matrisi, liveness metrikleri, eşik uyarısı;
`reports/output/` altında 4 grafik (heatmap, vektör barları, spektrogramlar, MFCC ortalamaları).

### 4) Canlı konsolu çalıştır

```bash
python main.py                # Tam pipeline
python main.py --no-speaker-check    # Sadece STT + komut
python main.py --no-liveness         # Liveness atla
python main.py --list-devices        # Cihazları listele
python main.py --commands            # Komutları yazdır ve çık
```

## Benchmark — espeak-ng ile 3 Sahte Konuşmacı

Sandbox'ta `test_e2e.py` ile aldığım gerçekçi sonuçlar (TR sentez sesi):

```
Backend: mfcc
  Aynı kişi  min=0.993, avg=0.994
  Farklı kişi max=0.986, avg=0.967
  Margin = +0.007    ← yetersiz, false-accept riski yüksek

Backend: resemblyzer
  Aynı kişi  min=0.933, avg=0.937
  Farklı kişi max=0.791, avg=0.713
  Margin = +0.142    ← sağlam ayrım, eşik 0.70 güvenli
```

**Sonuç:** Resemblyzer kuvvetle önerilir. MFCC sadece bağımlılık eklemek
istemediğin/edge cihaz için.

## Komut Örnekleri

| Söylenen                                | Algılanan komut    | Parametre              |
|-----------------------------------------|--------------------|------------------------|
| "Tarih nedir"                           | `tarih`            | -                      |
| "Saat kaç şu an"                        | `tarih`            | -                      |
| "Listele bakalım"                       | `listele`          | -                      |
| "Sesi 50 yap"                           | `ses_seviyesi`     | `{"level": 50}`        |
| "Ses seviyesi 80"                       | `ses_seviyesi`     | `{"level": 80}`        |
| "Firefox aç"                            | `uygulama_ac`      | `{"app": "firefox"}`   |
| "Aç chromium"                           | `uygulama_ac`      | `{"app": "chromium"}`  |
| "Ara kedi videoları nasıl çekilir"      | `ara`              | `{"query": "kedi…"}`   |
| "Çıkış"                                 | `cikis` → `__EXIT__` | -                    |
| "Sesi 150 yap"                          | hata: max=100      | (range)                |
| "Ses çok"                               | hata: tip          | (int değil)            |

Kendi komutunu eklemek için `config/settings.py: COMMANDS` listesine ya da
`commands/registry.py: DEFAULT_COMMANDS` listesine ekleyebilirsin.

## Güvenlik Notları

- **Shell injection**: Tüm slot değerleri `shlex.quote` ile escape edilir.
  `parse("Aç ; rm -rf /")` çalıştırılırsa rendered komut `xdg-open '; rm -rf /'`
  olur — tek argüman olarak işlenir, exec olmaz.
- **Konuşmacı bypass**: Resemblyzer replay/deep-fake'e karşı zayıf değil ama
  korumalı değil. Üretim için anti-spoof (RawNet2/AASIST) gerekir.
- **Liveness**: Yalnızca sinyal istatistikleri (hız, pitch std, flatness).
  TTS sentetik sesleri liveness'ı geçebilir; insan sesinin sinyal yapısına
  yakın olduğu için bu beklenen davranış.

## Yol Haritası

- [ ] Tek konuşmadan çoklu konuşmacı diarization (pyannote)
- [ ] Hot-word ile uyandırma (porcupine/pico) → her cümleyi Whisper'a göndermek yerine
- [ ] Web arayüzü (FastAPI + WebSocket) — şu an konsol; istersen sonraki adım
- [ ] Resemblyzer yerine ECAPA-TDNN (SpeechBrain) — biraz daha doğru ama büyük model
- [ ] Anti-spoof katmanı (replay attack koruması)
