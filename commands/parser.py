"""
Pattern tabanlı komut parser.

Akış:
  1) Metni normalize et (TR lowercase + noktalama)
  2) WAKE_WORD varsa kontrol et
  3) Her komut için her pattern'i regex'e çevir, eşle
  4) En çok literal karakter eşleyen pattern = kazanan (en spesifik)
  5) Parametreleri yakala, tip dönüşümü + min/max doğrulaması yap

Pattern formatı:
  - Düz metin (örn. "tarih") → birebir kelime sınırı eşleşmesi
  - "{name}" slotu        → tek kelime (varsayılan)
  - "{name:rest}" slotu   → sonrasının tümü
"""
import re
from typing import Any

from config import settings
from commands.registry import get_commands
from commands.numbers import parse_turkish_number, extract_number_token, tr_lower as _tr_lower_helper

# ---------- Normalization ----------

def _tr_lower(text: str) -> str:
    """Türkçe büyük→küçük: 'İ'→'i', 'I'→'ı'."""
    return text.replace("İ", "i").replace("I", "ı").lower()


def _normalize(text: str) -> str:
    """Kullanıcı girdisi için: lowercase + noktalama temizle."""
    text = _tr_lower(text)
    text = re.sub(r"[^\wçğıöşü\s]", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _normalize_literal(text: str) -> str:
    """Pattern literal'leri için: lowercase + boşluk daralt.
    {} stripleme YAPMA — slot işaretçileri korunmalı."""
    text = _tr_lower(text)
    text = re.sub(r"\s+", " ", text)
    return text


# ---------- Pattern → regex ----------

_SLOT_RE = re.compile(r"\{(\w+)(?::(\w+))?\}")


def _compile_pattern(pattern: str) -> tuple[re.Pattern, list[tuple[str, str]]]:
    r"""
    "ses {level}" → regex r"\bses (?P<level>\S+)"
    "ara {q:rest}" → regex r"\bara (?P<q>.+)"

    Slot dışı literal'ler ayrı normalize edilir; {} korunur.
    """
    slots: list[tuple[str, str]] = []
    out_parts: list[str] = []
    last = 0
    for m in _SLOT_RE.finditer(pattern):
        literal = _normalize_literal(pattern[last:m.start()])
        out_parts.append(re.escape(literal))
        name = m.group(1)
        kind = m.group(2) or "word"
        slots.append((name, kind))
        if kind == "rest":
            # Greedy — slot'tan sonraki tüm girdiyi al
            out_parts.append(rf"(?P<{name}>.+)")
        elif kind == "tr_int":
            # Türkçe sayılar (en fazla 2 kelime) ya da rakamlar
            out_parts.append(
                rf"(?P<{name}>\d+|(?:on|yirmi|otuz|kırk|elli|altmış|yetmiş|seksen|doksan)"
                rf"(?:\s+(?:bir|iki|üç|dört|beş|altı|yedi|sekiz|dokuz))?"
                rf"|sıfır|bir|iki|üç|dört|beş|altı|yedi|sekiz|dokuz)"
            )
        else:
            out_parts.append(rf"(?P<{name}>\S+)")
        last = m.end()
    out_parts.append(re.escape(_normalize_literal(pattern[last:])))

    body = "".join(out_parts).strip()
    regex = re.compile(rf"(?:^|\b){body}(?:\b|$)", re.UNICODE)
    return regex, slots


def _literal_chars(pattern: str) -> int:
    """Spesifiklik skoru için literal karakter sayısı."""
    return len(_SLOT_RE.sub("", _normalize_literal(pattern)).strip())


# ---------- Param doğrulama ----------

class ParamError(ValueError):
    pass


def _validate_param(name: str, raw: str, spec: dict) -> Any:
    kind = spec.get("type", "word")
    if kind in ("int", "tr_int"):
        # Önce Türkçe yazılı sayı mı? ("yetmiş" → 70)
        parsed_num = parse_turkish_number(raw)
        if parsed_num is not None:
            val = parsed_num
        else:
            try:
                val = int(raw)
            except ValueError:
                raise ParamError(f"'{name}' tam sayı olmalı, alındı: {raw!r}")
        if "min" in spec and val < spec["min"]:
            raise ParamError(f"'{name}' >= {spec['min']} olmalı, alındı: {val}")
        if "max" in spec and val > spec["max"]:
            raise ParamError(f"'{name}' <= {spec['max']} olmalı, alındı: {val}")
        return val
    if kind == "rest":
        return raw.strip()
    # word veya bilinmeyen tür
    return raw.strip()


# ---------- Parse ----------

def parse(text: str) -> dict:
    """
    Args:
        text: ham transkripsiyon

    Returns:
        {
          "matched":  bool,
          "command":  komut dict'i veya None,
          "keyword":  eşleşen pattern (display için),
          "params":   {ad: değer},
          "text":     orijinal metin,
          "wake_ok":  bool,
          "error":    str | None    (param doğrulamada hata varsa)
        }
    """
    norm = _normalize(text)

    # Wake word
    wake = _normalize(settings.WAKE_WORD)
    if wake:
        if not re.search(rf"(?:^|\b){re.escape(wake)}\b", norm):
            return {"matched": False, "command": None, "keyword": None,
                    "params": {}, "text": text, "wake_ok": False,
                    "error": None}
        norm = re.sub(rf"^.*?{re.escape(wake)}\b", "", norm, count=1).strip()

    if not norm:
        return {"matched": False, "command": None, "keyword": None,
                "params": {}, "text": text, "wake_ok": True, "error": None}

    best = None     # (score, command, pattern, match)
    for cmd in get_commands():
        for pattern in cmd["patterns"]:
            try:
                regex, _ = _compile_pattern(pattern)
            except re.error:
                continue
            m = regex.search(norm)
            if m:
                score = _literal_chars(pattern)
                if best is None or score > best[0]:
                    best = (score, cmd, pattern, m)

    if best is None:
        return {"matched": False, "command": None, "keyword": None,
                "params": {}, "text": text, "wake_ok": True, "error": None}

    _, cmd, pattern, m = best
    params: dict = {}
    spec = cmd.get("params", {})
    try:
        for slot_name, raw in m.groupdict().items():
            if raw is None:
                continue
            params[slot_name] = _validate_param(slot_name, raw,
                                                spec.get(slot_name, {}))
    except ParamError as e:
        return {"matched": False, "command": cmd, "keyword": pattern,
                "params": {}, "text": text, "wake_ok": True,
                "error": str(e)}

    return {"matched": True, "command": cmd, "keyword": pattern,
            "params": params, "text": text, "wake_ok": True, "error": None}
