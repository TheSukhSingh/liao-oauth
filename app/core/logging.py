# app/core/logging.py
import json
import logging
import os
from logging.handlers import RotatingFileHandler
from contextvars import ContextVar
from pathlib import Path

# Context for per-request correlation
_request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")

def set_request_id(value: str) -> None:
    _request_id_ctx.set(value)

def get_request_id() -> str:
    return _request_id_ctx.get()

class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True

class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "lvl": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
            "path": record.pathname,
            "line": record.lineno,
        }
        # Attach any extra fields if present
        for k, v in record.__dict__.items():
            if k not in payload and k not in ("args", "msg", "exc_info", "exc_text", "stack_info"):
                try:
                    json.dumps({k: v})
                    payload[k] = v
                except Exception:
                    pass
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)

def setup_logging() -> None:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_dir = Path(os.getenv("LOG_DIR", "logs"))
    log_dir.mkdir(parents=True, exist_ok=True)

    # Size-based rotation so you can test instantly
    max_bytes = int(os.getenv("LOG_MAX_BYTES", "1048576"))  # 1 MiB
    backups = int(os.getenv("LOG_BACKUPS", "7"))

    file_handler = RotatingFileHandler(log_dir / "app.log", maxBytes=max_bytes, backupCount=backups, encoding="utf-8")
    console_handler = logging.StreamHandler()

    jf = JsonFormatter()
    file_handler.setFormatter(jf)
    console_handler.setFormatter(jf)

    rid_filter = RequestIdFilter()
    file_handler.addFilter(rid_filter)
    console_handler.addFilter(rid_filter)

    root = logging.getLogger()
    root.setLevel(level)

    # Clear default handlers then attach ours
    for h in list(root.handlers):
        root.removeHandler(h)
    root.addHandler(file_handler)
    root.addHandler(console_handler)

    # Align common libraries
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error", "fastapi", "httpx", "googleapiclient"):
        logging.getLogger(name).setLevel(level)
