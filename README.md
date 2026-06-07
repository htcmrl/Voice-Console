# Sesli Komut Konsolu 



## Mimari

```
voice-console/
├── config/settings.py                # Backend seçimi + tüm sabitler
├── audio/
│   ├── recorder.py                   # sounddevice canlı kayıt
│   ├── vad.py                        # Sessizlik tabanlı cümle bölme
│   └── noise.py                      # Gürültü kalibrasyonu
├── speaker/
│   ├── backends.py                   # MFCCBackend | ResemblyzerBackend
│   ├── features.py                   # MFCC + delta öznitelikleri (MFCC backend için)
│   ├── enrollment.py                 # Aktif backend'e göre embedding kaydı
│   ├── verification.py               # Aktif backend ile identify
│   └── liveness.py                   # İnsan sesi tespiti
├── stt/
│   ├── backends.py                   # OpenAIWhisperBackend | FasterWhisperBackend
│   └── transcriber.py                # Backend facade
├── commands/
│   ├── registry.py                   # Pattern + slot + param spec
│   ├── parser.py                     # Regex pattern matching + param doğrulama
│   └── executor.py                   # shlex.quote ile güvenli render
├── reports/plotter.py                # Matplotlib grafik raporları
├── data/
│   ├── enrollment_text.txt           # Türkçe fonetik dengeli metin
│   └── voiceprints/                  # <isim>.wav, <isim>.npy, <isim>.backend
├── enroll_user.py                    # Kayıt scripti
├── test_signatures.py                # Aktif backend ile karşılaştırma + grafik
├── test_commands.py                  # Parser + executor birim testleri
├── test_e2e.py                       # espeak-ng ile uçtan uca test
├── main.py                           # Ana döngü 
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



## Komut Sistemi


```python
{
        "name": "ses_seviyesi",
        "patterns": [
            "ses {level:tr_int}",
            "sesi {level:tr_int} yap",
            "ses seviyesi {level:tr_int}",
            "ses seviyesini {level:tr_int} yap",
            "volume {level:tr_int}",
        ],
        "action": "cmd /c echo Ses seviyesi {level} olarak ayarlandi",
        "params": {"level": {"type": "tr_int", "min": 0, "max": 100}},
        "description": "Ses seviyesini ayarlar (0-100)",
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

### 3) Kişileri karşılaştır, rapor çıkar

```bash
python test_signatures.py
```

Konsolda benzerlik matrisi, liveness metrikleri, eşik uyarısı;
`reports/output/` altında 4 grafik (heatmap, vektör barları, spektrogramlar, MFCC ortalamaları).

### 4) Canlı konsolu çalıştır

```bash
python main.py                       # Tam pipeline
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





