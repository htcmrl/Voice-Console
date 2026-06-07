"""
Komut çalıştırıcı.

execute(parsed_result) — parser.parse() çıktısını alır, action template'ini
parametrelerle doldurur, subprocess ile çalıştırır.

Parametre güvenliği: tüm slot değerleri shlex.quote ile sarılır → shell
enjeksiyonu engellenir. Sabit literal kısımlar developer-controlled.
"""
import shlex
import subprocess
import sys


class ExitRequested(Exception):
    """çıkış komutu için."""


def _render(action: str, params: dict, keyword: str) -> str:
    """
    Action template'ine parametreleri yerleştir.
    Tüm parametre değerleri shlex.quote ile escape edilir.
    '__keyword__' özel placeholder'ı eşleşen pattern'i gösterir.
    """
    safe = {k: shlex.quote(str(v)) for k, v in params.items()}
    safe["__keyword__"] = keyword
    try:
        return action.format(**safe)
    except KeyError as e:
        raise RuntimeError(f"Action template'te eksik parametre: {e}")


def execute(parsed: dict, timeout: float = 10.0) -> dict:
    """
    Args:
        parsed: commands.parser.parse() çıktısı (matched=True olmalı)

    Returns:
        {"returncode", "stdout", "stderr", "rendered_command"}
    """
    if not parsed.get("matched"):
        raise ValueError("execute: parsed.matched=False")

    cmd = parsed["command"]
    action = cmd["action"]

    if action == "__EXIT__":
        raise ExitRequested()

    rendered = _render(action, parsed["params"], parsed["keyword"])
    print(f"\n[exec] $ {rendered}")

    try:
        wrapped = "cmd /c chcp 65001 >nul && " + rendered
        result = subprocess.run(wrapped,
                                shell=True,
                                capture_output=True,
                                text=True,
                                encoding= "utf-8",
                                errors="replace",
                                timeout=timeout)
        if result.stdout:
            print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
        if result.stderr:
            print(result.stderr, end="" if result.stderr.endswith("\n") else "\n",
                  file=sys.stderr)
        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "rendered_command": rendered,
        }
    except subprocess.TimeoutExpired:
        print(f"[exec] zaman aşımı ({timeout}s)")
        return {"returncode": -1, "stdout": "", "stderr": "timeout",
                "rendered_command": rendered}
