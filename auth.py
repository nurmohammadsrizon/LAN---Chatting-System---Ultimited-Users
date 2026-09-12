from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
SECRET_FILE = BASE_DIR / "database" / ".secret_key"
TOKEN_TTL_SECONDS = 60 * 60 * 24 * 7


def _load_secret() -> bytes:
    SECRET_FILE.parent.mkdir(parents=True, exist_ok=True)
    if SECRET_FILE.exists():
        value = SECRET_FILE.read_bytes().strip()
        if len(value) >= 32:
            return value
    value = os.urandom(48)
    SECRET_FILE.write_bytes(value)
    try:
        os.chmod(SECRET_FILE, 0o600)
    except OSError:
        pass
    return value


SECRET_KEY = _load_secret()


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    iterations = 240_000
    derived = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return f"pbkdf2_sha256${iterations}${base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(derived).decode()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, iterations, salt_b64, hash_b64 = encoded.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        salt = base64.urlsafe_b64decode(salt_b64.encode())
        expected = base64.urlsafe_b64decode(hash_b64.encode())
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(iterations))
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_token(user_id: str) -> str:
    payload = {"sub": user_id, "exp": int(time.time()) + TOKEN_TTL_SECONDS}
    header = {"alg": "HS256", "typ": "CHAT"}
    encoded_header = _b64(json.dumps(header, separators=(",", ":")).encode())
    encoded_payload = _b64(json.dumps(payload, separators=(",", ":")).encode())
    unsigned = f"{encoded_header}.{encoded_payload}".encode()
    signature = _b64(hmac.new(SECRET_KEY, unsigned, hashlib.sha256).digest())
    return f"{encoded_header}.{encoded_payload}.{signature}"


def decode_token(token: str) -> dict[str, Any] | None:
    try:
        header, payload, signature = token.split(".", 2)
        unsigned = f"{header}.{payload}".encode()
        expected = _b64(hmac.new(SECRET_KEY, unsigned, hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            return None
        data = json.loads(_unb64(payload))
        if int(data.get("exp", 0)) < int(time.time()):
            return None
        return data
    except Exception:
        return None
