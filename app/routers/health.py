from fastapi import APIRouter

router = APIRouter(tags=["health"])

@router.get("/healthz", summary="Liveness probe")
def healthz():
    return {"ok": True}
