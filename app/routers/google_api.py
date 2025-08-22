from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.orm import Session
import httpx

from app.db.session import get_db
from app.security.internal import require_internal
from app.security.ratelimit import limit_by_api_key, limit_by_user
from app.services.access_tokens import (
    ensure_access_token,
    TokenNotFound,
    ReconnectRequired,
)

router = APIRouter(prefix="/google", tags=["google-apis"])


async def _google_get(url: str, access_token: str, params: dict | None = None):
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(url, headers=headers, params=params)
    return r


def _handle_google_response(r: httpx.Response):
    if r.status_code == 401:
        # token invalid at Google → force reconnect on the client app
        raise HTTPException(status_code=409, detail="Google token invalid; user must reconnect")
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"google api error: {r.status_code} {r.text[:200]}")
    return r.json()


@router.get(
    "/drive/me",
    dependencies=[Depends(require_internal), Depends(limit_by_api_key), Depends(limit_by_user)],
    summary="Drive profile (about.user)",
)
async def drive_me(user_id: str = Query(..., min_length=1), db: Session = Depends(get_db)):
    try:
        tok = await ensure_access_token(db, user_id=user_id)
    except TokenNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ReconnectRequired as e:
        raise HTTPException(status_code=409, detail=str(e))

    url = "https://www.googleapis.com/drive/v3/about"
    r = await _google_get(url, tok["access_token"], params={"fields": "user"})
    return _handle_google_response(r)


@router.get(
    "/drive/files",
    dependencies=[Depends(require_internal), Depends(limit_by_api_key), Depends(limit_by_user)],
    summary="List Drive files",
)
async def drive_files(
    user_id: str = Query(..., min_length=1),
    page_size: int = Query(10, ge=1, le=100),
    q: str | None = Query(None, description="Drive search query"),
    db: Session = Depends(get_db),
):
    try:
        tok = await ensure_access_token(db, user_id=user_id)
    except TokenNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ReconnectRequired as e:
        raise HTTPException(status_code=409, detail=str(e))

    params = {
        "pageSize": page_size,
        "fields": "files(id,name,mimeType,modifiedTime,owners,webViewLink),nextPageToken",
    }
    if q:
        params["q"] = q

    url = "https://www.googleapis.com/drive/v3/files"
    r = await _google_get(url, tok["access_token"], params=params)
    return _handle_google_response(r)


@router.get(
    "/sheets/{spreadsheet_id}/values",
    dependencies=[Depends(require_internal), Depends(limit_by_api_key), Depends(limit_by_user)],
    summary="Read a Sheets range",
)
async def sheets_values(
    spreadsheet_id: str = Path(..., min_length=3),
    user_id: str = Query(..., min_length=1),
    range_: str = Query("Sheet1!A1:D10", alias="range"),
    db: Session = Depends(get_db),
):
    try:
        tok = await ensure_access_token(db, user_id=user_id)
    except TokenNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ReconnectRequired as e:
        raise HTTPException(status_code=409, detail=str(e))

    url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{range_}"
    r = await _google_get(url, tok["access_token"])
    return _handle_google_response(r)
