from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import health
from .core.config import settings  
from .core.logging import setup_logging
from .db.session import engine
from .db.models import Base
from app.services.crypto import get_fernet  

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

@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
app.include_router(health.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
