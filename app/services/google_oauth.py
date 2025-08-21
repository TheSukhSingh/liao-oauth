from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from urllib.parse import urlencode, urlparse

import httpx

from app.core.config import settings
from app.services.state import create_state, StateError

GOOGLE_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"

# Scopes (space-delimited in the URL)
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
    # only allow hosts you’ve whitelisted
    host = urlparse(redirect_uri).hostname or ""
    if host not in settings.ALLOWED_REDIRECT_HOSTS:
        raise ValueError(f"redirect_uri host '{host}' is not allowed")

def build_consent_url(user_id: str, redirect_uri: str, prompt_consent: bool = True) -> str:
    """
    Build Google's OAuth consent URL. Returns a URL the frontend can redirect to.
    """
    _ensure_client_config()
    _validate_redirect_host(redirect_uri)

    # signed short-lived state carrying user_id
    state = create_state(user_id)

    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "state": state,
        # ensure we receive a refresh_token on first connect:
        "access_type": "offline",
        "include_granted_scopes": "true",
    }
    if prompt_consent:
        # request consent screen to guarantee refresh_token on the first grant
        params["prompt"] = "consent"

    return f"{GOOGLE_AUTH_ENDPOINT}?{urlencode(params)}"

async def exchange_code_for_tokens(code: str, redirect_uri: str) -> Dict[str, Any]:
    """
    Exchange authorization code for tokens.
    Returns dict: {access_token, refresh_token?, expires_at, scope, token_type, raw}
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

    # small timeout; tune as you like
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(GOOGLE_TOKEN_ENDPOINT, data=data)
    if resp.status_code != 200:
        # bubble up a clean error with response snippet
        raise RuntimeError(f"token exchange failed: {resp.status_code} {resp.text[:200]}")

    j = resp.json()
    # expires_in is seconds from now
    expires_in = int(j.get("expires_in", 0) or 0)
    # subtract a tiny skew to be safe
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=max(0, expires_in - 30))

    return {
        "access_token": j.get("access_token"),
        "refresh_token": j.get("refresh_token"),  # may be absent on subsequent consents
        "expires_at": expires_at,
        "scope": j.get("scope"),
        "token_type": j.get("token_type"),
        "raw": j,  # keep original for debugging if needed (don’t log tokens!)
    }

async def refresh_access_token(refresh_token: str) -> Dict[str, Any]:
    """
    Use refresh_token to get a fresh access_token.
    Returns dict: {access_token, expires_at, scope?, token_type}
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
