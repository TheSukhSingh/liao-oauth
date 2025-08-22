import logging
import time
import uuid
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from .routers import health, google_docs, google_slides
from .routers import auth as auth_router 
from .routers import internal as internal_router
from .routers import google_api as google_api_router
from .core.config import settings  
from .core.logging import setup_logging
from .db.session import engine
from .db.models import Base
from app.services.crypto import get_fernet  
from starlette.staticfiles import StaticFiles
from app.core.logging import setup_logging, set_request_id
from starlette.middleware.base import BaseHTTPMiddleware
get_fernet()
setup_logging(settings.LOG_DIR)

app = FastAPI(title="Google Auth Service", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        set_request_id(rid)
        start = time.perf_counter()
        response = await call_next(request)
        dur_ms = int((time.perf_counter() - start) * 1000)
        logging.getLogger("app.request").info(
            f"{request.client.host} {request.method} {request.url.path} {response.status_code} {dur_ms}ms",
            extra={"method": request.method, "path": str(request.url.path), "status": response.status_code, "dur_ms": dur_ms},
        )
        response.headers["X-Request-ID"] = rid
        return response

app.add_middleware(RequestIdMiddleware)


app.include_router(health.router)
app.include_router(auth_router.router)
app.include_router(internal_router.router)
app.include_router(google_api_router.router)
app.include_router(google_docs.router)
app.include_router(google_slides.router)
app.include_router(google_docs.router)

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
