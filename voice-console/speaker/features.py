"""
Konuşmacı imzası için öznitelik çıkarımı (librosa).

Kullanılan öznitelikler:
  - MFCC (Mel-Frequency Cepstral Coefficients)
  - Delta MFCC (1. türev)
  - Delta-delta MFCC (2. türev)
  - Spektral merkez (centroid)
  - Sıfır geçiş oranı (ZCR)

İmza = tüm framelerin ortalaması + standart sapması (basit ama etkili
i-vector benzeri bir gösterim). Daha gelişmiş: GMM, x-vector vb.
"""
import numpy as np
import librosa

from config import settings


def extract_features(audio: np.ndarray,
                     sample_rate: int = settings.SAMPLE_RATE) -> np.ndarray:
    """
    Bir ses dizisinden frame-bazlı öznitelik matrisi çıkarır.

    Returns:
        np.ndarray, shape = (frames, n_features)
    """
    audio = audio.astype(np.float32)

    # Sessizlik kırp — başta/sonda boş kısımlar imzaya gürültü katmasın
    audio, _ = librosa.effects.trim(audio, top_db=30)

    if len(audio) < settings.N_FFT:
        # Çok kısa — sentetik sıfırlarla doldur
        audio = np.pad(audio, (0, settings.N_FFT - len(audio)))

    mfcc = librosa.feature.mfcc(y=audio,
                                sr=sample_rate,
                                n_mfcc=settings.N_MFCC,
                                hop_length=settings.HOP_LENGTH,
                                n_fft=settings.N_FFT)
    delta = librosa.feature.delta(mfcc)
    delta2 = librosa.feature.delta(mfcc, order=2)

    centroid = librosa.feature.spectral_centroid(y=audio,
                                                 sr=sample_rate,
                                                 hop_length=settings.HOP_LENGTH,
                                                 n_fft=settings.N_FFT)
    zcr = librosa.feature.zero_crossing_rate(audio,
                                             hop_length=settings.HOP_LENGTH)

    # frame eksenini hizala
    min_frames = min(mfcc.shape[1], centroid.shape[1], zcr.shape[1])
    feats = np.vstack([
        mfcc[:, :min_frames],
        delta[:, :min_frames],
        delta2[:, :min_frames],
        centroid[:, :min_frames],
        zcr[:, :min_frames],
    ])
    return feats.T  # (frames, features)


def build_voiceprint(audio: np.ndarray,
                     sample_rate: int = settings.SAMPLE_RATE) -> np.ndarray:
    """
    Konuşmacı imzası: SADECE MFCC + delta + delta² özniteliklerinin
    ortalaması + standart sapması. Spectral centroid ve ZCR mutlak
    büyüklük farkı nedeniyle MFCC sinyalini boğuyordu — imzaya katılmaz.
    (Bunlar yine de extract_features'tan dönüyor; liveness'ta kullanılıyor.)

    Returns:
        np.ndarray, shape = (2 * 3 * N_MFCC,)  ör. N_MFCC=20 ise 120-d
    """
    feats = extract_features(audio, sample_rate)
    mfcc_block = feats[:, : 3 * settings.N_MFCC]   # MFCC + delta + delta2
    mean = mfcc_block.mean(axis=0)
    std = mfcc_block.std(axis=0)
    voiceprint = np.concatenate([mean, std])
    return voiceprint


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """İki imzanın kosinüs benzerliği (-1..1)."""
    a_norm = np.linalg.norm(a)
    b_norm = np.linalg.norm(b)
    if a_norm < 1e-9 or b_norm < 1e-9:
        return 0.0
    return float(np.dot(a, b) / (a_norm * b_norm))
