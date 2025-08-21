from fastapi import APIRouter, Depends
from app.security.internal import require_internal

router = APIRouter(prefix="/internal", tags=["internal"])

@router.get("/ping", dependencies=[Depends(require_internal)])
def ping():
    return {"ok": True}
