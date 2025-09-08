
from typing import List, ClassVar  
from pydantic import field_validator, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    ENV: str = "dev"
    LOG_DIR: str = "logs"

    INTERNAL_ALLOWED_IPS: List[str] = []
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_BASE: str = "http://localhost:8000"

    RATE_LIMIT_WINDOW_SECONDS: int = 60
    RATE_LIMIT_MAX_PER_KEY: int = 120
    RATE_LIMIT_MAX_PER_USER: int = 60

    ALLOWED_REDIRECT_HOSTS: List[str] = ["localhost", "127.0.0.1"]
    ENCRYPTION_KEY: str = ""      
    API_INTERNAL_KEY: str = ""    

    # CORS: default to disabled (README expectation); set via env when needed
    CORS_ORIGINS: List[str] = []
   
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @field_validator("ALLOWED_REDIRECT_HOSTS", "CORS_ORIGINS", mode="before")
    @classmethod
    def split_csv(cls, v):
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v

settings = Settings()
