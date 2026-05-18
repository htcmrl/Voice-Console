"""Tüm sabitler ve eşikler buradan yönetilir."""
from pathlib import Path

# Yollar
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
VOICEPRINTS_DIR = DATA_DIR / "voiceprints"
ENROLLMENT_TEXT = DATA_DIR / "enrollment_text.txt"
TEST_RECORDINGS_DIR = DATA_DIR / "test_recordings"

# Ses
SAMPLE_RATE = 16000          # Whisper 16 kHz bekler
CHANNELS = 1
DTYPE = "float32"
BLOCK_DURATION = 0.05        # saniye — 50 ms bloklar halinde dinle

# Gürültü kalibrasyonu
NOISE_CALIBRATION_SECONDS = 2.0
SPEECH_RMS_MULTIPLIER = 3.0
MIN_SPEECH_RMS = 0.015

# VAD
SILENCE_HANGOVER = 1.2
MIN_UTTERANCE_DURATION = 1.0
MAX_UTTERANCE_DURATION = 15

# MFCC öznitelikleri (MFCCBackend için)
N_MFCC = 20
HOP_LENGTH = 512
N_FFT = 2048

# -------- Konuşmacı Backend Seçimi --------
# "mfcc"        : librosa MFCC mean+std (hafif, ek bağımlılık yok)
# "resemblyzer" : GE2E 256-d sinir ağı embedding (~17MB model, daha doğru)
SPEAKER_BACKEND = "resemblyzer"

# Backend-spesifik eşikler (None = backend'in default'unu kullan)
SPEAKER_SIMILARITY_THRESHOLDS = {
    "mfcc":        0.75,
    "resemblyzer": 0.70,
}

# Liveness
SPEECH_RATE_MIN = 2.0
SPEECH_RATE_MAX = 10.0
PITCH_VAR_MIN = 5.0
SPECTRAL_FLATNESS_MAX = 0.5

# -------- STT Backend Seçimi --------
# "whisper"        : Resmi openai-whisper
# "faster_whisper" : CTranslate2 tabanlı, CPU'da 3-4x hız + yarı RAM (int8)
STT_BACKEND = "faster_whisper"

WHISPER_MODEL = "small"      # tiny / base / small / medium / large(-v3)
WHISPER_LANGUAGE = "tr"
WHISPER_FP16 = False         # openai-whisper, CPU'da False

# faster-whisper ayarları
FASTER_WHISPER_DEVICE = "cpu"          # "cpu" / "cuda" / "auto"
FASTER_WHISPER_COMPUTE = "int8"        # "int8" (CPU) / "float16" (GPU) / "float32"
FASTER_WHISPER_VAD_FILTER = True       # Whisper dahili Silero VAD ile sessizliği filtrele

# Uyandırma kelimesi
WAKE_WORD = ""               # ör. "konsol" — boş bırakılırsa her cümle değerlendirilir

# -------- Komutlar --------
# Yeni format için commands/registry.py içindeki DEFAULT_COMMANDS kullanılır.
# Burada eski sözlük formatıyla ekstra komutlar tanımlanabilir; bunlar default
# listeye eklenir (override etmez).
COMMAND_REGISTRY = {
    # Örnek legacy giriş — boş bırakabilirsin
    # "merhaba": "echo 'Selam!'",
}

# Yeni format ile özel komutlar tanımlamak istersen burayı doldur — bu durumda
# DEFAULT_COMMANDS atlanır ve sadece bu liste kullanılır.
# Örn:
# COMMANDS = [
#     {"name": "müzik_çal", "patterns": ["müzik {parça}"],
#      "action": "mpv ~/Music/{parça}.mp3",
#      "params": {"parça": {"type": "word"}}},
# ]
COMMANDS: list = []

# Boş bırakırsan eski davranış (sessizlik-tabanlı) çalışır.
PTT_START_PHRASE = "konsol dinle"
PTT_STOP_PHRASE = "konsol tamam"