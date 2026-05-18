"""
3 kişinin imzasını karşılaştıran raporlar.
- Heatmap (cosine similarity matris)
- Bar chart (her kişinin diğerleriyle benzerlik puanı)
- MFCC istatistikleri karşılaştırma (mean + std)
- Spektrogram karşılaştırma
"""
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")   # GUI'siz ortamlar için
import matplotlib.pyplot as plt
import librosa
import librosa.display
import soundfile as sf

from config import settings
from speaker.features import (
    build_voiceprint,
    cosine_similarity,
    extract_features,
)


def similarity_heatmap(voiceprints: dict, output: Path):
    """Kullanıcılar arası kosinüs benzerliği matrisi."""
    users = list(voiceprints.keys())
    n = len(users)
    matrix = np.zeros((n, n))
    for i, u1 in enumerate(users):
        for j, u2 in enumerate(users):
            matrix[i, j] = cosine_similarity(voiceprints[u1], voiceprints[u2])

    fig, ax = plt.subplots(figsize=(6, 5))
    im = ax.imshow(matrix, cmap="viridis", vmin=-0.2, vmax=1.0)
    ax.set_xticks(range(n))
    ax.set_yticks(range(n))
    ax.set_xticklabels(users, rotation=45, ha="right")
    ax.set_yticklabels(users)
    for i in range(n):
        for j in range(n):
            ax.text(j, i, f"{matrix[i, j]:.2f}",
                    ha="center", va="center",
                    color="white" if matrix[i, j] < 0.6 else "black")
    ax.set_title("Konuşmacı imza benzerliği (kosinüs)")
    fig.colorbar(im, ax=ax)
    fig.tight_layout()
    fig.savefig(output, dpi=120)
    plt.close(fig)
    return matrix


def voiceprint_bars(voiceprints: dict, output: Path):
    """İmza vektörlerinin yan yana bar gösterimi."""
    fig, axes = plt.subplots(len(voiceprints), 1,
                             figsize=(12, 2.5 * len(voiceprints)),
                             sharex=True)
    if len(voiceprints) == 1:
        axes = [axes]
    for ax, (user, vec) in zip(axes, voiceprints.items()):
        ax.bar(range(len(vec)), vec, width=1.0)
        ax.set_title(f"İmza vektörü — {user}")
        ax.set_ylabel("değer")
    axes[-1].set_xlabel("özellik indeksi")
    fig.tight_layout()
    fig.savefig(output, dpi=120)
    plt.close(fig)


def spectrogram_grid(wavs: dict, output: Path):
    """Üç kişinin spektrogramını yan yana."""
    n = len(wavs)
    fig, axes = plt.subplots(1, n, figsize=(5 * n, 4))
    if n == 1:
        axes = [axes]
    for ax, (user, audio) in zip(axes, wavs.items()):
        S = librosa.stft(audio.astype(np.float32),
                         n_fft=settings.N_FFT,
                         hop_length=settings.HOP_LENGTH)
        S_db = librosa.amplitude_to_db(np.abs(S), ref=np.max)
        librosa.display.specshow(S_db, sr=settings.SAMPLE_RATE,
                                 hop_length=settings.HOP_LENGTH,
                                 x_axis="time", y_axis="hz", ax=ax)
        ax.set_title(f"Spektrogram — {user}")
    fig.tight_layout()
    fig.savefig(output, dpi=120)
    plt.close(fig)


def mfcc_means(wavs: dict, output: Path):
    """Her kullanıcı için MFCC katsayılarının ortalaması (radar/line)."""
    fig, ax = plt.subplots(figsize=(10, 5))
    for user, audio in wavs.items():
        feats = extract_features(audio)
        mfcc_mean = feats[:, :settings.N_MFCC].mean(axis=0)
        ax.plot(mfcc_mean, marker="o", label=user)
    ax.set_xlabel("MFCC katsayı indeksi")
    ax.set_ylabel("ortalama değer")
    ax.set_title("MFCC ortalamaları karşılaştırması")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(output, dpi=120)
    plt.close(fig)


def full_report(voiceprints: dict, wavs: dict, output_dir: Path) -> dict:
    """Tüm grafikleri üretir ve dosya yollarını döndürür."""
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {}
    matrix = similarity_heatmap(voiceprints, output_dir / "similarity_heatmap.png")
    paths["heatmap"] = output_dir / "similarity_heatmap.png"
    voiceprint_bars(voiceprints, output_dir / "voiceprint_bars.png")
    paths["bars"] = output_dir / "voiceprint_bars.png"
    if wavs:
        spectrogram_grid(wavs, output_dir / "spectrograms.png")
        paths["spectrograms"] = output_dir / "spectrograms.png"
        mfcc_means(wavs, output_dir / "mfcc_means.png")
        paths["mfcc"] = output_dir / "mfcc_means.png"
    paths["similarity_matrix"] = matrix
    return paths
