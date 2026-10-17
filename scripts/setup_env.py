"""Prepare .env for a local install (used by install.ps1 / install.sh).

- copies .env.example to .env when .env is missing, and then points it at
  SQLite and a local media folder;
- fills SECRET_KEY and ENCRYPTION_KEY_SALT with random values while they are
  empty or still the placeholder from .env.example.

An existing .env keeps everything else. Values are never printed.
"""

from __future__ import annotations

import secrets
import shutil
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
ENV = BASE_DIR / ".env"
EXAMPLE = BASE_DIR / ".env.example"
PLACEHOLDER = "change-me"


def set_var(lines: list[str], key: str, value: str) -> list[str]:
    prefix = f"{key}="
    for i, line in enumerate(lines):
        if line.startswith(prefix):
            lines[i] = prefix + value
            return lines
    lines.append(prefix + value)
    return lines


def get_var(lines: list[str], key: str) -> str | None:
    prefix = f"{key}="
    for line in lines:
        if line.startswith(prefix):
            return line[len(prefix) :].strip()
    return None


def main() -> int:
    fresh = not ENV.exists()
    if fresh:
        if not EXAMPLE.exists():
            print("Не найден .env.example", file=sys.stderr)
            return 1
        shutil.copyfile(EXAMPLE, ENV)
        print("Создан .env из .env.example")

    lines = ENV.read_text(encoding="utf-8-sig").splitlines()

    if fresh:
        lines = set_var(lines, "DATABASE_URL", "sqlite:///db.sqlite3")
        lines = set_var(lines, "MEDIA_ROOT", (BASE_DIR / "media").as_posix())
        lines = set_var(lines, "DEBUG", "true")
        print("База: SQLite (db.sqlite3), файлы: папка media")

    for key in ("SECRET_KEY", "ENCRYPTION_KEY_SALT"):
        current = get_var(lines, key)
        if not current or current.startswith(PLACEHOLDER):
            lines = set_var(lines, key, secrets.token_urlsafe(50))
            print(f"{key}: сгенерирован")

    ENV.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
