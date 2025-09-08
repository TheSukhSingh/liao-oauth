from __future__ import annotations
import httpx
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.security.internal import require_internal
from app.security.ratelimit import limit_by_api_key, limit_by_user
from app.services.access_tokens import ensure_access_token

router = APIRouter(prefix="/google/slides", tags=["google-slides"])
from typing import Dict, List, Any

def _collect_text(text_elements: List[Dict[str, Any]]) -> str:
    """Join all textRun/autoText contents into a single string."""
    parts: List[str] = []
    for el in text_elements or []:
        if "textRun" in el and "content" in el["textRun"]:
            parts.append(el["textRun"]["content"])
        elif "autoText" in el and "content" in el["autoText"]:
            parts.append(el["autoText"]["content"])
    return "".join(parts).strip()

def _shape_kind(shape: Dict[str, Any]) -> str:
    ph = (shape.get("placeholder") or {}).get("type")
    # Normalize a few common placeholders
    if ph in {"TITLE", "CENTERED_TITLE"}:
        return "title"
    if ph == "SUBTITLE":
        return "subtitle"
    if ph == "BODY":
        return "body"
    return "other"

@router.get(
    "/{presentation_id}/summary",
    dependencies=[Depends(require_internal), Depends(limit_by_api_key), Depends(limit_by_user)],
)
async def summarize_presentation(
    presentation_id: str = Path(..., min_length=5),
    user_id: str = Query(...),
    db: Session = Depends(get_db),
):
    """Return a simplified list of slides with title/subtitle/body text."""
    access = await ensure_access_token(db, user_id=user_id)
    headers = {"Authorization": f"Bearer {access['access_token']}"}

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"https://slides.googleapis.com/v1/presentations/{presentation_id}",
                             headers=headers)
    if r.status_code != 200:
        raise HTTPException(500, f"google api error: {r.text[:200]}")

    data = r.json()
    slides: List[Dict[str, Any]] = []

    for idx, slide in enumerate(data.get("slides", []), start=1):
        title = subtitle = body = ""
        all_text_parts: List[str] = []

        for pe in slide.get("pageElements", []):
            shape = pe.get("shape")
            if not shape or "text" not in shape:
                continue
            txt = _collect_text(shape["text"].get("textElements"))
            if not txt:
                continue

            kind = _shape_kind(shape)
            if kind == "title" and not title:
                title = txt
            elif kind == "subtitle" and not subtitle:
                subtitle = txt
            elif kind == "body":
                body = (body + "\n" + txt).strip() if body else txt

            all_text_parts.append(txt)

        slides.append({
            "index": idx,
            "pageObjectId": slide.get("objectId"),
            "title": title,
            "subtitle": subtitle,
            "body": body,
            "all_text": "\n".join([t for t in all_text_parts if t]).strip(),
        })

    return {
        "presentationId": data.get("presentationId"),
        "title": data.get("title"),
        "slideCount": len(slides),
        "slides": slides,
    }

@router.get(
    "/{presentation_id}",
    dependencies=[Depends(require_internal), Depends(limit_by_api_key), Depends(limit_by_user)],
)
async def get_presentation(
    presentation_id: str = Path(..., min_length=5),
    user_id: str = Query(...),
    db: Session = Depends(get_db),
):
    access = await ensure_access_token(db, user_id=user_id)
    headers = {"Authorization": f"Bearer {access['access_token']}"}
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(f"https://slides.googleapis.com/v1/presentations/{presentation_id}", headers=headers)
    if r.status_code != 200:
        raise HTTPException(500, f"google api error: {r.text[:200]}")
    return r.json()
