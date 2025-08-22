# app/routers/google_drive.py  (or wherever you put Google routes)
from __future__ import annotations
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.access_tokens import ensure_access_token
from app.security.internal import require_internal
from app.security.ratelimit import limit_by_api_key

router = APIRouter(prefix="/google/drive", tags=["google-drive"])

@router.get("/me", dependencies=[Depends(require_internal), Depends(limit_by_api_key)])
async def drive_me(user_id: str = Query(...), db: Session = Depends(get_db)):
    access = await ensure_access_token(db, user_id=user_id)
    headers = {"Authorization": f"Bearer {access['access_token']}"}
    params = {"fields": "user"}
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get("https://www.googleapis.com/drive/v3/about", headers=headers, params=params)
    if r.status_code != 200:
        raise HTTPException(500, f"google api error: {r.text[:200]}")
    return r.json()

@router.get("/files", dependencies=[Depends(require_internal), Depends(limit_by_api_key)])
async def drive_files(
    user_id: str = Query(...),
    page_size: int = Query(10, ge=1, le=1000),
    page_token: str | None = None,
    q: str | None = None,
    order_by: str | None = None,
    include_all_drives: bool = False,
    corpora: str | None = None,   # "user" | "allDrives" | "domain" | etc.
    db: Session = Depends(get_db),
):
    access = await ensure_access_token(db, user_id=user_id)
    headers = {"Authorization": f"Bearer {access['access_token']}"}

    params = {
        "pageSize": page_size,
        "pageToken": page_token,
        "q": q,
        "orderBy": order_by,
        "fields": "nextPageToken,files(id,name,mimeType,owners(displayName),modifiedTime,trashed,webViewLink,iconLink,size)",
        # Drives-related
        "supportsAllDrives": "true" if include_all_drives else "false",
        "includeItemsFromAllDrives": "true" if include_all_drives else "false",
        "corpora": corpora or "user",
    }
    # prune Nones
    params = {k: v for k, v in params.items() if v is not None}

    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get("https://www.googleapis.com/drive/v3/files", headers=headers, params=params)
    if r.status_code != 200:
        raise HTTPException(500, f"google api error: {r.text[:200]}")
    return r.json()
