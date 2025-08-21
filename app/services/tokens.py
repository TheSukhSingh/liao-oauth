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
