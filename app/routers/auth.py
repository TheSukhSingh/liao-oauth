from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.services.state import create_state, verify_state, StateError
from app.services.google_oauth import build_consent_url, exchange_code_for_tokens
from app.services.tokens import upsert_tokens
from datetime import datetime
from typing import List
from app.security.internal import require_internal
from app.services.access_tokens import ensure_access_token, TokenNotFound, ReconnectRequired

router = APIRouter(prefix="/auth/google", tags=["google-oauth"])

def _redirect_uri() -> str:
    # single source of truth for the callback URL
    base = settings.GOOGLE_REDIRECT_BASE.rstrip("/")
    return f"{base}/auth/google/callback"

class AuthURLResp(BaseModel):
    auth_url: str

class ConnectResp(BaseModel):
    connected: bool

@router.get("/url", response_model=AuthURLResp, summary="Generate Google OAuth consent URL")
def auth_url(user_id: str = Query(..., min_length=1)):
    try:
        url = build_consent_url(user_id=user_id, redirect_uri=_redirect_uri())
        return {"auth_url": url}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/callback", response_model=ConnectResp, summary="OAuth callback to exchange code and store tokens")
async def auth_callback(
    code: str = Query(..., min_length=1),
    state: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
):
    try:
        payload = verify_state(state)
        user_id = payload["u"]
    except StateError as e:
        raise HTTPException(status_code=400, detail=f"invalid state: {e}")

    try:
        token_data = await exchange_code_for_tokens(code=code, redirect_uri=_redirect_uri())
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"token exchange failed: {e}")

    access_token = token_data.get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="no access_token in response")

    refresh_token = token_data.get("refresh_token")  # may be None on re-consent
    expires_at = token_data.get("expires_at")
    scope = token_data.get("scope")

    try:
        upsert_tokens(
            db,
            user_id=user_id,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
            scope=scope,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"failed to save tokens: {e}")

    return {"connected": True}


class TokenResp(BaseModel):
    access_token: str
    expires_at: datetime | None = None
    scopes: List[str] = []

@router.get(
    "/token",
    response_model=TokenResp,
    summary="Return a valid Google access token for a user (auto-refresh if expired)",
    dependencies=[Depends(require_internal)],
)
async def token(user_id: str = Query(..., min_length=1), db: Session = Depends(get_db)):
    try:
        data = await ensure_access_token(db, user_id=user_id)
        return data
    except TokenNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ReconnectRequired as e:
        # 409/428 both acceptable; using 409 to indicate action required
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"failed to fetch token: {e}")