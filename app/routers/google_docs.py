from __future__ import annotations
from typing import List, Dict, Any
import httpx
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.security.internal import require_internal
from app.security.ratelimit import limit_by_api_key, limit_by_user
from app.services.access_tokens import ensure_access_token

router = APIRouter(prefix="/google/docs", tags=["google-docs"])

def _text_from_elements(elements: List[Dict[str, Any]]) -> str:
    parts: List[str] = []
    for el in elements or []:
        if "textRun" in el and "content" in el["textRun"]:
            parts.append(el["textRun"]["content"])
    return "".join(parts)

def _collect_doc_text(body: Dict[str, Any]) -> str:
    lines: List[str] = []
    for content in body.get("content", []):
        if "paragraph" in content:
            lines.append(_text_from_elements(content["paragraph"].get("elements")))
        elif "table" in content:
            tbl = content["table"]
            for row in tbl.get("tableRows", []):
                cells = []
                for cell in row.get("tableCells", []):
                    cell_lines = []
                    for c in cell.get("content", []):
                        if "paragraph" in c:
                            cell_lines.append(_text_from_elements(c["paragraph"].get("elements")))
                    cells.append(" ".join([t.strip() for t in cell_lines if t]))
                lines.append(" | ".join([c for c in cells if c]).strip())
        elif "sectionBreak" in content:
            lines.append("")
    return "\n".join([ln.strip() for ln in lines if ln is not None]).strip()

@router.get(
    "/{document_id}/text",
    operation_id="docs_get_text",
    dependencies=[Depends(require_internal), Depends(limit_by_api_key), Depends(limit_by_user)],
)
async def get_doc_text(
    document_id: str = Path(..., min_length=5),
    user_id: str = Query(...),
    db: Session = Depends(get_db),
):
    access = await ensure_access_token(db, user_id=user_id)
    headers = {"Authorization": f"Bearer {access['access_token']}"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"https://docs.googleapis.com/v1/documents/{document_id}", headers=headers)
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail=f"google api error: {r.text[:200]}")
    data = r.json()
    text = _collect_doc_text(data.get("body", {}))
    return {"documentId": data.get("documentId"), "title": data.get("title"), "text": text}

@router.get(
    "/{doc_id}",
    operation_id="docs_get_document",
    dependencies=[Depends(require_internal), Depends(limit_by_api_key), Depends(limit_by_user)],
)
async def get_doc(
    doc_id: str = Path(..., min_length=5),
    user_id: str = Query(...),
    db: Session = Depends(get_db),
):
    access = await ensure_access_token(db, user_id=user_id)
    headers = {"Authorization": f"Bearer {access['access_token']}"}
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(f"https://docs.googleapis.com/v1/documents/{doc_id}", headers=headers)
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail=f"google api error: {r.text[:200]}")
    return r.json()
