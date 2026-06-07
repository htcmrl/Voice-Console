"""Türkçe yazılı sayıları (yetmiş, otuz beş) tam sayıya çevirir."""
import re

_BIRLER = {
    "sıfır": 0, "bir": 1, "iki": 2, "üç": 3, "dört": 4,
    "beş": 5, "altı": 6, "yedi": 7, "sekiz": 8, "dokuz": 9,
}

_ONLAR = {
    "on": 10, "yirmi": 20, "otuz": 30, "kırk": 40, "elli": 50,
    "altmış": 60, "yetmiş": 70, "seksen": 80, "doksan": 90,
}

_TR_LOWER = str.maketrans("İI", "iı")


def tr_lower(text: str) -> str:
    """Türkçe büyük→küçük (İ→i, I→ı)."""
    return text.translate(_TR_LOWER).lower()


def parse_turkish_number(text: str) -> int | None:
    """
    Bir metni Türkçe yazılı sayı olarak yorumlamayı dener.
    Örnek:
        "yetmiş"        → 70
        "yetmiş beş"    → 75
        "yüz yirmi"     → 120  (bu sürümde desteklenmiyor — sadece 0-99)
        "80"            → 80   (zaten sayı ise olduğu gibi)
        "merhaba"       → None
    """
    text = tr_lower(text).strip()
    if not text:
        return None

    # Direkt sayı mı?
    if re.fullmatch(r"\d+", text):
        return int(text)

    # Sözlük tabanlı tarama
    tokens = text.split()
    if len(tokens) == 1:
        t = tokens[0]
        if t in _ONLAR:
            return _ONLAR[t]
        if t in _BIRLER:
            return _BIRLER[t]
        return None

    if len(tokens) == 2:
        # "yetmiş beş" gibi
        t1, t2 = tokens
        if t1 in _ONLAR and t2 in _BIRLER:
            return _ONLAR[t1] + _BIRLER[t2]
        return None

    return None


def extract_number_token(text: str) -> tuple[int, str] | None:
    """
    Metinde bir sayı (rakam veya Türkçe yazılı) bul ve değerini + ham metnini döndür.
    İlk eşleşmeyi getirir.

    Örnek:
        "sesi yetmiş yap"        → (70, "yetmiş")
        "sesi 50 yap"            → (50, "50")
        "ses seviyesi yetmiş beş" → (75, "yetmiş beş")
        "merhaba dünya"          → None
    """
    text = tr_lower(text)

    # 1) Rakam ara
    m = re.search(r"\d+", text)
    if m:
        return int(m.group()), m.group()

    # 2) Türkçe iki kelimeli ara ("yetmiş beş")
    pat_iki = r"\b(" + "|".join(_ONLAR.keys()) + r")\s+(" + "|".join(_BIRLER.keys()) + r")\b"
    m = re.search(pat_iki, text)
    if m:
        value = _ONLAR[m.group(1)] + _BIRLER[m.group(2)]
        return value, m.group()

    # 3) Türkçe tek kelimeli ara
    pat_tek = r"\b(" + "|".join(list(_ONLAR.keys()) + list(_BIRLER.keys())) + r")\b"
    m = re.search(pat_tek, text)
    if m:
        word = m.group()
        value = _ONLAR.get(word) or _BIRLER.get(word)
        if value is not None:
            return value, word

    return None


if __name__ == "__main__":
    # Hızlı test
    tests = [
        "yetmiş", "seksen", "yetmiş beş", "otuz iki", "sıfır",
        "100", "sesi yetmiş yap", "ses seviyesi sekiz", "merhaba",
    ]
    for t in tests:
        n = parse_turkish_number(t)
        e = extract_number_token(t)
        print(f"{t!r:<30} → parse={n}, extract={e}")