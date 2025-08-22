from __future__ import annotations
import json
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from app.db.models import OAuthToken
from app.services.crypto import decrypt_str
from app.services.google_oauth import refresh_access_token
from app.services.tokens import upsert_tokens

class TokenNotFound(Exception): ...
class ReconnectRequired(Exception): ...

def _now() -> datetime:
    return datetime.now(timezone.utc)

def _scopes_list_from_json(scopes_json: str | None) -> list[str]:
    try:
        return json.loads(scopes_json) if scopes_json else []
    except Exception:
        return []

def _scopes_list_from_str(scopes_str: str | None) -> list[str]:
    return (scopes_str or "").split()

async def ensure_access_token(db: Session, *, user_id: str) -> dict:
    """
    Returns a valid access token for user_id.
    Auto-refreshes if expired and a refresh_token is available.
    Response: {"access_token": str, "expires_at": datetime | None, "scopes": [str,...]}
    """
    row = db.query(OAuthToken).filter(OAuthToken.user_id == user_id).one_or_none()
    if not row:
        raise TokenNotFound("no token record for user")

    skew = timedelta(seconds=30)
    now = _now()

    needs_refresh = True
    if row.expires_at:
        exp = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=timezone.utc)
        needs_refresh = (exp - now) <= skew

    if not needs_refresh:
        return {
            "access_token": decrypt_str(row.access_token_enc),
            "expires_at": row.expires_at,
            "scopes": _scopes_list_from_json(row.scopes_json),
        }

    if not row.refresh_token_enc:
        raise ReconnectRequired("missing refresh_token; user must reconnect")

    refresh_token = decrypt_str(row.refresh_token_enc)
    new = await refresh_access_token(refresh_token)

    # Persist the new access token (keep the existing refresh_token)
    upsert_tokens(
        db,
        user_id=user_id,
        access_token=new["access_token"],
        refresh_token=refresh_token,
        expires_at=new.get("expires_at"),
        scope=new.get("scope"),
    )

    return {
        "access_token": new["access_token"],
        "expires_at": new.get("expires_at"),
        "scopes": _scopes_list_from_str(new.get("scope")),
    }
