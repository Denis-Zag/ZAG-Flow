"""Хеширование паролей и ограниченные по времени JWT администратора."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt

ISSUER = "zag-flow"


def hash_password(password: str) -> str:
    """Сохранить соль и scrypt-хеш, никогда не сохраняя пароль."""

    salt = secrets.token_hex(16)
    digest = hashlib.scrypt(
        password.encode(), salt=bytes.fromhex(salt), n=32768, r=8, p=1,
        maxmem=67108864, dklen=32,
    )
    return f"scrypt${salt}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    """Сравнить результат scrypt с сохранённым хешем."""

    try:
        kind, salt, expected = encoded.split("$")
        if kind != "scrypt":
            return False
        actual = hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(salt), n=32768, r=8, p=1,
            maxmem=67108864, dklen=32,
        ).hex()
        return secrets.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def issue_token(username: str, secret: str) -> str:
    """Выдать токен на один час без пароля и других секретов в payload."""

    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": username, "iss": ISSUER, "iat": now,
         "exp": now + timedelta(hours=1), "jti": secrets.token_hex(16)},
        secret, algorithm="HS256",
    )


def read_token(token: str, secret: str) -> str:
    """Проверить подпись, издателя, обязательные поля и срок действия."""

    payload = jwt.decode(
        token, secret, algorithms=["HS256"], issuer=ISSUER,
        options={"require": ["sub", "iss", "iat", "exp", "jti"]},
    )
    return payload["sub"]
