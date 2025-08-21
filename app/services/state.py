from __future__ import annotations
import hmac, json, os, time, hashlib
from base64 import urlsafe_b64encode, urlsafe_b64decode
from typing import Any, Dict
from app.core.config import settings

class StateError(RuntimeError):
    pass

def _b64e(b: bytes) -> str:
    return urlsafe_b64encode(b).rstrip(b"=").decode("ascii")

def _b64d(s: str) -> bytes:
    pad = '=' * (-len(s) % 4)
    return urlsafe_b64decode((s + pad).encode("ascii"))

def _sign(message: bytes) -> str:
    key = settings.API_INTERNAL_KEY.encode("utf-8")
    sig = hmac.new(key, message, hashlib.sha256).digest()
    return _b64e(sig)

def create_state(user_id: str, ttl_seconds: int = 300) -> str:
    if not user_id:
        raise StateError("user_id required")

    # Harden TTL: coerce int and ensure minimum (e.g., 30s)
    try:
        ttl = int(ttl_seconds)
    except Exception:
        ttl = 300
    if ttl < 30:
        ttl = 30

    header = {"alg": "HS256", "typ": "STATE"}
    now = int(time.time())
    payload: Dict[str, Any] = {
        "u": user_id,
        "p": "google_oauth",
        "iat": now,
        "exp": now + ttl,
        "n": _b64e(os.urandom(8)),
    }

    h = _b64e(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    p = _b64e(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    msg = f"{h}.{p}".encode("utf-8")
    s = _sign(msg)
    return f"{h}.{p}.{s}"

def verify_state(token: str, leeway_seconds: int = 5) -> Dict[str, Any]:
    try:
        h, p, s = token.split(".")
    except ValueError as e:
        raise StateError("Malformed state") from e

    msg = f"{h}.{p}".encode("utf-8")
    expected = _sign(msg)
    if not hmac.compare_digest(s, expected):
        raise StateError("Invalid state signature")

    try:
        payload = json.loads(_b64d(p).decode("utf-8"))
    except Exception as e:
        raise StateError("Invalid state payload") from e

    if payload.get("p") != "google_oauth":
        raise StateError("Unexpected state purpose")

    try:
        exp = int(payload.get("exp"))
        iat = int(payload.get("iat"))
    except Exception:
        raise StateError("Invalid exp/iat in state")

    now = int(time.time())

    # Basic sanity: iat must not be in the future by more than leeway
    if iat - now > leeway_seconds:
        raise StateError("State issued in the future")

    # Expiry with small leeway
    if now - exp > leeway_seconds:
        raise StateError("State expired")

    uid = payload.get("u")
    if not uid:
        raise StateError("Missing user_id in state")

    return payload
