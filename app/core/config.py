# app/core/config.py
from typing import List, ClassVar
from pydantic import field_validator, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # pydantic-settings config
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Regular settings (env-overridable because they’re typed)
    ENV: str = "dev"
    LOG_DIR: str = "logs"

    # Lists should use default_factory (no mutable defaults)
    INTERNAL_ALLOWED_IPS: List[str] = Field(default_factory=list)

    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_BASE: str = "http://localhost:8000"

    # ✅ Annotate rate-limit fields (ints) so Pydantic is happy
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    RATE_LIMIT_MAX_PER_KEY: int = 120
    RATE_LIMIT_MAX_PER_USER: int = 60

    ALLOWED_REDIRECT_HOSTS: List[str] = Field(default_factory=lambda: ["localhost", "127.0.0.1"])
    ENCRYPTION_KEY: str = ""       # base64 urlsafe
    API_INTERNAL_KEY: str = ""     # long random string

    CORS_ORIGINS: List[str] = Field(default_factory=lambda: ["http://localhost:8000", "http://127.0.0.1:8000"])

    # Back-compat alias (if other modules used INTERNAL_IP_ALLOWLIST)
    @property
    def INTERNAL_IP_ALLOWLIST(self) -> List[str]:
        return self.INTERNAL_ALLOWED_IPS

    @field_validator("ALLOWED_REDIRECT_HOSTS", "CORS_ORIGINS", "INTERNAL_ALLOWED_IPS", mode="before")
    @classmethod
    def split_csv(cls, v):
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v

settings = Settings()
