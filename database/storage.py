from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from threading import RLock
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
BASE_DIR.mkdir(parents=True, exist_ok=True)

FILES = {
    "users": BASE_DIR / "users.json",
    "groups": BASE_DIR / "groups.json",
    "messages": BASE_DIR / "messages.json",
}

LOCK = RLock()

DEFAULTS = {
    "users": [],
    "groups": [],
    "messages": [],
}


def _ensure_file(name: str) -> None:
    path = FILES[name]
    if not path.exists():
        _atomic_write(path, DEFAULTS[name])


def _load(name: str) -> list[dict[str, Any]]:
    _ensure_file(name)
    path = FILES[name]
    with LOCK:
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else list(DEFAULTS[name])
        except (json.JSONDecodeError, OSError):
            return list(DEFAULTS[name])


def _atomic_write(path: Path, data: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def save(name: str, data: list[dict[str, Any]]) -> None:
    with LOCK:
        _atomic_write(FILES[name], data)


def get_all(name: str) -> list[dict[str, Any]]:
    return _load(name)


def replace_all(name: str, data: list[dict[str, Any]]) -> None:
    save(name, data)
