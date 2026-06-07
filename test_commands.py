"""
Yeni parser + executor için kapsamlı test.
Backend bağımsız — sentetik metinlerle çalışır, ses gerektirmez.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from commands.parser import parse, _compile_pattern
from commands.executor import execute, ExitRequested, _render


def test_parser():
    cases = [
        # (girdi, beklenen_komut_adı, beklenen_params)
        ("Tarih nedir",                        "tarih",          {}),
        ("Saat kaç şu an",                     "tarih",          {}),
        ("Listele bakalım",                    "listele",        {}),
        ("KİM ben",                            "kim",            {}),
        ("Sesi 50 yap",                        "ses_seviyesi",   {"level": 50}),
        ("ses 80",                             "ses_seviyesi",   {"level": 80}),
        ("ses seviyesi 25",                    "ses_seviyesi",   {"level": 25}),
        ("Firefox aç",                         "uygulama_ac",    {"app": "firefox"}),
        ("Aç chromium",                        "uygulama_ac",    {"app": "chromium"}),
        ("Ara kedi videoları nasıl çekilir",   "ara",            {"query": "kedi videoları nasıl çekilir"}),
        ("Çıkış",                              "cikis",          {}),
        # Negatif örnekler
        ("Hava bugün çok güzel",               None,             {}),
        ("",                                   None,             {}),
    ]
    print("=== Parser ===")
    ok = True
    for text, expected_name, expected_params in cases:
        r = parse(text)
        actual_name = r["command"]["name"] if r["matched"] else None
        actual_params = r["params"]
        passed = (actual_name == expected_name and actual_params == expected_params)
        ok = ok and passed
        sym = "✓" if passed else "✗"
        print(f"  {sym} {text!r:<45} → cmd={actual_name!r:<16} "
              f"params={actual_params}")
        if not passed:
            print(f"     beklenen: cmd={expected_name!r} params={expected_params}")
    return ok


def test_param_validation():
    print("\n=== Parametre doğrulama ===")
    ok = True
    # Range dışı sayı
    r = parse("sesi 150 yap")  # max 100
    cond = r.get("error") and "100" in (r.get("error") or "")
    print(f"  {'✓' if cond else '✗'} 'sesi 150' → range hatası: {r.get('error')}")
    ok = ok and cond

    # Sayı olmayan değer
    r = parse("ses çok")
    cond = r.get("error") and "sayı" in (r.get("error") or "").lower()
    print(f"  {'✓' if cond else '✗'} 'ses çok' → tip hatası: {r.get('error')}")
    ok = ok and cond
    return ok


def test_render():
    print("\n=== Action render + güvenli quoting ===")
    cases = [
        # Normal
        ({"app": "firefox"}, "tarih", "xdg-open {app}", "xdg-open firefox"),
        # Shell injection denemesi → shlex.quote ile bloklanmalı
        ({"app": "; rm -rf /"}, "tarih",
         "xdg-open {app}",
         "xdg-open '; rm -rf /'"),
        # Tek tırnak içeren değer
        ({"q": "it's nice"}, "x", "echo {q}", "echo 'it'\"'\"'s nice'"),
    ]
    ok = True
    for params, kw, tmpl, expected in cases:
        out = _render(tmpl, params, kw)
        passed = out == expected
        ok = ok and passed
        sym = "✓" if passed else "✗"
        print(f"  {sym} {params} + {tmpl!r} → {out!r}")
        if not passed:
            print(f"     beklenen: {expected!r}")
    return ok


def test_executor():
    print("\n=== Executor (gerçek subprocess) ===")
    # Basit
    parsed = parse("Tarih nedir")
    if not parsed["matched"]:
        print("  ✗ 'Tarih nedir' parse edilemedi")
        return False
    r = execute(parsed)
    cond1 = r["returncode"] == 0
    print(f"  {'✓' if cond1 else '✗'} 'tarih' → rc={r['returncode']}")

    # Parametre ile — render kontrolü
    parsed = parse("Ara python tutorial")
    if not parsed["matched"]:
        print("  ✗ 'Ara python tutorial' parse edilemedi")
        return False
    rendered = _render(parsed["command"]["action"],
                       parsed["params"], parsed["keyword"])
    cond2 = "duckduckgo.com" in rendered and "python" in rendered
    print(f"  {'✓' if cond2 else '✗'} ara render: {rendered}")

    # Exit
    parsed = parse("Çıkış")
    if not parsed["matched"]:
        print("  ✗ 'Çıkış' parse edilemedi")
        return False
    try:
        execute(parsed)
        cond3 = False
    except ExitRequested:
        cond3 = True
    print(f"  {'✓' if cond3 else '✗'} çıkış → ExitRequested")

    return cond1 and cond2 and cond3


def test_pattern_compile():
    print("\n=== Pattern → regex derleme ===")
    cases = [
        ("ses {level}",       "ses 50",       {"level": "50"}),
        ("ara {q:rest}",      "ara bu da bu", {"q": "bu da bu"}),
        ("{app} aç",          "firefox aç",   {"app": "firefox"}),
    ]
    ok = True
    for pattern, text, expected in cases:
        regex, slots = _compile_pattern(pattern)
        m = regex.search(text)
        if not m:
            print(f"  ✗ {pattern!r} ↮ {text!r}: hiç eşleşme yok")
            ok = False
            continue
        gd = m.groupdict()
        passed = all(gd.get(k) == v for k, v in expected.items())
        ok = ok and passed
        print(f"  {'✓' if passed else '✗'} {pattern!r} ⊕ {text!r} → {gd}")
    return ok


if __name__ == "__main__":
    results = [
        ("pattern_compile", test_pattern_compile()),
        ("parser",          test_parser()),
        ("param_validation", test_param_validation()),
        ("render",          test_render()),
        ("executor",        test_executor()),
    ]
    print("\n" + "=" * 50)
    all_ok = True
    for name, ok in results:
        print(f"  {name:<22}: {'GEÇTİ' if ok else 'BAŞARISIZ'}")
        all_ok = all_ok and ok
    print("=" * 50)
    sys.exit(0 if all_ok else 1)
