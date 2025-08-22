from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Dict, Any
from urllib.parse import urlencode, urlparse

import httpx

from app.core.config import settings
from app.services.state import create_state  # you already import/verify state in the router

GOOGLE_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"

SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/documents.readonly",
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/presentations.readonly",
]


def _ensure_client_config() -> None:
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise RuntimeError("Missing GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET in environment")


def _validate_redirect_host(redirect_uri: str) -> None:
    host = urlparse(redirect_uri).hostname or ""
    if host not in settings.ALLOWED_REDIRECT_HOSTS:
        raise ValueError(f"redirect_uri host '{host}' is not allowed")


def build_consent_url(user_id: str, redirect_uri: str, prompt_consent: bool = True) -> str:
    """
    Build Google's OAuth consent URL and return it as a string (frontend will redirect).
    """
    _ensure_client_config()
    _validate_redirect_host(redirect_uri)

    state = create_state(user_id)  # short-lived, signed state carrying the user_id

    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "state": state,
        "access_type": "offline",            # ensure we get a refresh_token on first connect
        "include_granted_scopes": "true",
    }
    if prompt_consent:
        params["prompt"] = "consent"

    return f"{GOOGLE_AUTH_ENDPOINT}?{urlencode(params)}"


async def exchange_code_for_tokens(code: str, redirect_uri: str) -> Dict[str, Any]:
    """
    Exchange authorization code for tokens.
    Returns: {access_token, refresh_token?, expires_at(datetime), scope(str), token_type, raw(dict)}
    """
    _ensure_client_config()
    _validate_redirect_host(redirect_uri)

    data = {
        "code": code,
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(GOOGLE_TOKEN_ENDPOINT, data=data)

    if resp.status_code != 200:
        raise RuntimeError(f"token exchange failed: {resp.status_code} {resp.text[:200]}")

    j = resp.json()
    expires_in = int(j.get("expires_in", 0) or 0)
    # subtract a small skew for safety
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=max(0, expires_in - 30))

    return {
        "access_token": j.get("access_token"),
        "refresh_token": j.get("refresh_token"),  # may be absent on re-consent
        "expires_at": expires_at,
        "scope": j.get("scope"),
        "token_type": j.get("token_type"),
        "raw": j,
    }


async def refresh_access_token(refresh_token: str) -> Dict[str, Any]:
    """
    Use refresh_token to get a fresh access_token.
    Returns: {access_token, expires_at(datetime), scope?, token_type, raw}
    """
    _ensure_client_config()
    if not refresh_token:
        raise ValueError("refresh_token required")

    data = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(GOOGLE_TOKEN_ENDPOINT, data=data)

    if resp.status_code != 200:
        raise RuntimeError(f"refresh failed: {resp.status_code} {resp.text[:200]}")

    j = resp.json()
    expires_in = int(j.get("expires_in", 0) or 0)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=max(0, expires_in - 30))

    return {
        "access_token": j.get("access_token"),
        "expires_at": expires_at,
        "scope": j.get("scope"),
        "token_type": j.get("token_type"),
        "raw": j,
    }


async def revoke_token(token: str) -> bool:
    """
    Google OAuth2 token revocation.
    Returns True if Google says OK or already-revoked (200 or 400).
    """
    url = "https://oauth2.googleapis.com/revoke"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {"token": token}

    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.post(url, data=data, headers=headers)

    return r.status_code in (200, 400)
