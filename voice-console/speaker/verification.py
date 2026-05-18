"""
Gelen sesi kayıtlı embedding'lerle karşılaştırır.
Aktif backend (settings.SPEAKER_BACKEND) kullanılır.
"""
import numpy as np

from speaker.backends import get_backend, get_threshold


def identify(audio: np.ndarray,
             known_embeddings: dict,
             threshold: float | None = None) -> dict:
    """
    Args:
        audio: numpy ses dizisi
        known_embeddings: {user_id: embedding}
        threshold: None ise aktif backend için settings'teki eşik kullanılır

    Returns:
        {"user_id": str|None,
         "similarity": float,
         "scores": {user: sim},
         "best_candidate": str,
         "threshold": float,
         "backend": str}
    """
    backend = get_backend()
    th = threshold if threshold is not None else get_threshold()

    if not known_embeddings:
        return {"user_id": None, "similarity": 0.0, "scores": {},
                "best_candidate": None, "threshold": th, "backend": backend.name}

    probe = backend.embed(audio)
    scores = {uid: backend.similarity(probe, vec)
              for uid, vec in known_embeddings.items()}
    best_user = max(scores, key=scores.get)
    best_score = scores[best_user]
    matched = best_user if best_score >= th else None

    return {"user_id": matched,
            "similarity": best_score,
            "scores": scores,
            "best_candidate": best_user,
            "threshold": th,
            "backend": backend.name}
