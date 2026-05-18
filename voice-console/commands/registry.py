"""
Yapılandırılmış komut sözlüğü.

Bir komut:
{
    "name":        "human-okunabilir benzersiz ad",
    "patterns":    ["seç", "seç {item}", ...],   # eşanlamlılar + slot
    "action":      "kabuk komutu {item}'le birlikte",  # __EXIT__ özel
    "params":      {"item": {"type": "int", "min": 0, "max": 99}},
    "description": "kullanıcıya gösterilebilir açıklama",
}

Slot türleri:
  "word"   : tek kelime (boşluk içermez)    — varsayılan
  "int"    : tam sayı; min/max opsiyonel
  "tr_int" : Türkçe yazılı sayı veya rakam ("yetmiş" → 70)
  "rest"   : pattern'den sonraki tüm metin (arama sorgusu vb.)
"""
from __future__ import annotations
from typing import Any
from config import settings


DEFAULT_COMMANDS: list[dict[str, Any]] = [
    {
        "name": "selam",
        "patterns": ["seç", "tamam"],
        "action": "cmd /c chcp 65001 >nul && echo [{__keyword__}] algılandı",
        "description": "Anahtar kelimeyi yankıla",
    },
    {
        "name": "tarih",
        "patterns": ["tarih", "saat kaç", "bugün ne"],
        "action": "cmd /c date /t && time /t",
        "description": "Sistem tarih ve saatini gösterir",
    },
    {
        "name": "listele",
        "patterns": ["listele", "dosyaları göster"],
        "action": "cmd /c dir",
        "description": "Mevcut dizini listeler",
    },
    {
        "name": "kim",
        "patterns": ["kim", "ben kimim"],
        "action": "whoami",
        "description": "Geçerli kullanıcı adı",
    },
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
        "description": "Master ses seviyesini değiştirir (0-100)",
    },
    {
        "name": "uygulama_ac",
        "patterns": ["{app} aç", "aç {app}", "{app} başlat"],
        "action": "cmd /c start \"\" {app}",
        "params": {"app": {"type": "word"}},
        "description": "Bir uygulamayı/dosyayı varsayılan handler ile açar",
    },
    {
        "name": "ara",
        "patterns": ["ara {query:rest}", "internette ara {query:rest}"],
        "action": "cmd /c start \"\" \"https://duckduckgo.com/?q={query}\"",
        "params": {"query": {"type": "rest"}},
        "description": "DuckDuckGo'da arama yapar",
    },
{
        "name": "pil_durumu",
        "patterns": ["pil nasıl", "pil durumu", "şarj ne kadar", "pilim nasıl"],
        "action": "cmd /c chcp 65001 >nul && wmic path Win32_Battery get EstimatedChargeRemaining /value | findstr =",
        "description": "Pil seviyesini yüzde olarak gösterir",
    },
    {
        "name": "ip_adresim",
        "patterns": ["ip adresim", "ip nedir", "ağ bilgisi", "ip adresi"],
        "action": "cmd /c chcp 65001 >nul && ipconfig | findstr /R /C:\"IPv4\"",
        "description": "Yerel IP adres(ler)ini gösterir",
    },
    {
        "name": "ekrani_kilitle",
        "patterns": ["ekranı kilitle", "kilitle", "ekran kilitlensin", "bilgisayarı kilitle"],
        "action": "rundll32.exe user32.dll,LockWorkStation",
        "description": "Windows oturumunu kilitler",
    },
    {
        "name": "hesap_makinesi",
        "patterns": ["hesap makinesi", "hesap makinesi aç", "kalkülatör aç", "kalkülatörü aç"],
        "action": "cmd /c start \"\" calc.exe",
        "description": "Windows hesap makinesini açar",
    },
    {
        "name": "yazi_tura",
        "patterns": ["yazı tura at", "yazı mı tura mı", "yazı tura"],
        "action": "python -c \"import random; print(random.choice(['Yazı geldi!', 'Tura geldi!']))\"",
        "description": "Yazı tura atışı simüle eder",
    },
    {
        "name": "zar_at",
        "patterns": ["zar at", "zar fırlat", "zar atışı"],
        "action": "python -c \"import random; print(f'Zar geldi: {random.randint(1, 6)}')\"",
        "description": "1-6 arası rastgele zar atar",
    },
    {
        "name": "cikis",
        "patterns": ["çıkış", "kapat", "görüşürüz"],
        "action": "__EXIT__",
        "description": "Konsolu sonlandırır",
    },
]


def _from_legacy(legacy: dict[str, str]) -> list[dict[str, Any]]:
    """Eski {keyword: command} sözlüğünü yeni formata çevir."""
    out = []
    for kw, cmd in legacy.items():
        out.append({
            "name": kw,
            "patterns": [kw],
            "action": cmd,
            "description": f"(legacy) {kw}",
        })
    return out


def get_commands() -> list[dict[str, Any]]:
    """
    Settings'ten komutları yükle. Öncelik:
      1) settings.COMMANDS varsa onu kullan
      2) Yoksa DEFAULT_COMMANDS + settings.COMMAND_REGISTRY (legacy) birlikte
    """
    if hasattr(settings, "COMMANDS") and settings.COMMANDS:
        return list(settings.COMMANDS)
    legacy = getattr(settings, "COMMAND_REGISTRY", {}) or {}
    return DEFAULT_COMMANDS + _from_legacy(legacy)


def describe_all() -> str:
    """Help mesajı için tüm komutları liste halinde döndür."""
    lines = []
    for cmd in get_commands():
        patterns = " | ".join(cmd["patterns"])
        lines.append(f"  {cmd['name']:<18} → {patterns}")
        if cmd.get("description"):
            lines.append(f"  {'':<18}   {cmd['description']}")
    return "\n".join(lines)

