from __future__ import annotations
import json
from datetime import datetime
from sqlalchemy.orm import Session

from app.db.models import OAuthToken
from app.services.crypto import encrypt_str

def upsert_tokens(
    db: Session,
    *,
    user_id: str,
    access_token: str,
    refresh_token: str | None,
    expires_at: datetime | None,
    scope: str | None,  # Google returns space-delimited string
) -> OAuthToken:
    scopes_json = json.dumps(scope.split() if scope else [])

    row = db.query(OAuthToken).filter(OAuthToken.user_id == user_id).one_or_none()
    if row is None:
        row = OAuthToken(
            user_id=user_id,
            access_token_enc=encrypt_str(access_token),
            refresh_token_enc=encrypt_str(refresh_token) if refresh_token else "",
            expires_at=expires_at,
            scopes_json=scopes_json,
        )
        db.add(row)
    else:
        row.access_token_enc = encrypt_str(access_token)
        row.refresh_token_enc = encrypt_str(refresh_token) if refresh_token else row.refresh_token_enc
        row.expires_at = expires_at
        row.scopes_json = scopes_json

    db.commit()
    db.refresh(row)
    return row

def clear_tokens(db: Session, *, user_id: str) -> bool:
    """
    Remove access/refresh tokens + expiry for this user_id.
    Keeps the row for auditability; safe to call multiple times.
    """
    row = db.query(OAuthToken).filter(OAuthToken.user_id == user_id).one_or_none()
    if not row:
        return False
    row.access_token_enc = None
    row.refresh_token_enc = None
    row.expires_at = None
    # keep scopes_json as-is or blank it if you prefer:
    # row.scopes_json = None
    db.add(row)
    db.commit()
    return True