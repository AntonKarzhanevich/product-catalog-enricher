from __future__ import annotations

import os
from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_dotenv(path: Path | None = None) -> None:
    """Минимальная загрузка .env без внешних зависимостей."""
    p = path or project_root() / ".env"
    if not p.is_file():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def require_env(name: str) -> str:
    load_dotenv()
    value = os.environ.get(name, "").strip().strip('"').strip("'")
    if not value:
        raise RuntimeError(
            f"Не задана переменная {name}. Скопируйте .env.example в .env и укажите ключ Mouser."
        )
    return value
