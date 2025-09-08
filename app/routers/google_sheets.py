from __future__ import annotations
import httpx
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.security.internal import require_internal
from app.security.ratelimit import limit_by_api_key, limit_by_user
from app.services.access_tokens import ensure_access_token

router = APIRouter(prefix="/google/sheets", tags=["google-sheets"])

@router.get(
    "/{spreadsheet_id}/values",
    summary="Read a Sheets range",
    dependencies=[Depends(require_internal), Depends(limit_by_api_key), Depends(limit_by_user)],
)
async def sheets_values(
    spreadsheet_id: str = Path(..., min_length=3),
    user_id: str = Query(..., min_length=1),
    range_: str = Query("Sheet1!A1:D10", alias="range"),
    db: Session = Depends(get_db),
):
    access = await ensure_access_token(db, user_id=user_id)
    headers = {"Authorization": f"Bearer {access['access_token']}"}
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{range_}"
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(url, headers=headers)
    if r.status_code == 401:
        raise HTTPException(status_code=409, detail="Google token invalid; user must reconnect")
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"google api error: {r.status_code} {r.text[:200]}")
    return r.json()
