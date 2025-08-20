from typing import List
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    ENV: str = "dev"
    LOG_DIR: str = "logs"

    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_BASE: str = "http://localhost:8000"

    ALLOWED_REDIRECT_HOSTS: List[str] = ["localhost", "127.0.0.1"]
    ENCRYPTION_KEY: str = ""      # base64 urlsafe
    API_INTERNAL_KEY: str = ""    # long random string

    CORS_ORIGINS: List[str] = ["http://localhost:8000", "http://127.0.0.1:8000"]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @field_validator("ALLOWED_REDIRECT_HOSTS", "CORS_ORIGINS", mode="before")
    @classmethod
    def split_csv(cls, v):
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v

settings = Settings()
