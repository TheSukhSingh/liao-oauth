from __future__ import annotations
from functools import lru_cache
from base64 import urlsafe_b64decode
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from app.core.config import settings

class CryptoError(RuntimeError):
    pass

@lru_cache(maxsize=1)
def get_fernet() -> Fernet:
    """
    Build a Fernet instance from ENCRYPTION_KEY.
    Key must be a urlsafe base64 string that decodes to 32 bytes.
    """
    key_str = settings.ENCRYPTION_KEY.strip()
    if not key_str:
        raise CryptoError("ENCRYPTION_KEY is empty. Set it in .env")

    try:
        raw = urlsafe_b64decode(key_str.encode())
        if len(raw) != 32:
            raise CryptoError("ENCRYPTION_KEY must decode to exactly 32 bytes")
    except Exception as e:
        raise CryptoError("Invalid ENCRYPTION_KEY format (must be urlsafe base64 of 32 bytes)") from e

    return Fernet(key_str.encode())

def encrypt_str(plaintext: str) -> str:
    """
    Encrypt a UTF-8 string and return a token (str). Never log the result.
    """
    if plaintext is None:
        return ""
    token = get_fernet().encrypt(plaintext.encode("utf-8"))
    return token.decode("utf-8")

def decrypt_str(token: str) -> Optional[str]:
    """
    Decrypt a token back to string. Returns None if token invalid.
    """
    if not token:
        return None
    try:
        out = get_fernet().decrypt(token.encode("utf-8"))
        return out.decode("utf-8")
    except InvalidToken:
        return None
