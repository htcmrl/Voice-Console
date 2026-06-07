"""
Komut satırından kullanıcı kaydı:
    python enroll_user.py <user_id> [süre_saniye]
"""
import sys
from speaker.enrollment import enroll


def main():
    if len(sys.argv) < 2:
        user_id = input("Kullanıcı adı: ").strip()
    else:
        user_id = sys.argv[1]
    duration = float(sys.argv[2]) if len(sys.argv) > 2 else 35.0
    enroll(user_id, duration=duration)


if __name__ == "__main__":
    main()
