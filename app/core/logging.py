# app/core/logging.py
from __future__ import annotations

import json
import logging
import os
from contextvars import ContextVar
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

# ---- Request-ID context ------------------------------------------------------
_request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")

def set_request_id(value: str) -> None:
    _request_id_ctx.set(value)

def get_request_id() -> str:
    return _request_id_ctx.get()

class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # Always attach request_id (even if "-")
        record.request_id = get_request_id()
        return True

# ---- JSON formatter (defensive) ----------------------------------------------
class JsonFormatter(logging.Formatter):
    def _ts(self, record: logging.LogRecord) -> str:
        # UTC ISO8601, never raise
        return datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(timespec="seconds")

    def format(self, record: logging.LogRecord) -> str:
        try:
            base = {
                "ts": self._ts(record),
                "lvl": record.levelname,
                "logger": record.name,
                "msg": record.getMessage(),
                "request_id": getattr(record, "request_id", "-"),
                "file": record.pathname,
                "line": record.lineno,
            }
            # Attach serializable extras (best-effort)
            for k, v in list(record.__dict__.items()):
                if k in ("args", "msg", "exc_info", "exc_text", "stack_info", "pathname",
                         "lineno", "levelname", "name", "created"):
                    continue
                try:
                    json.dumps({k: v})
                except Exception:
                    continue
                if k not in base:
                    base[k] = v
            if record.exc_info:
                base["exc"] = self.formatException(record.exc_info)
            return json.dumps(base, ensure_ascii=False)
        except Exception as e:  # absolutely never crash logging
            return json.dumps({"ts": self._ts(record), "lvl": "ERROR", "logger": "logging",
                               "msg": f"formatting-error: {e!r}"}, ensure_ascii=False)

# ---- Setup -------------------------------------------------------------------
def setup_logging() -> None:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_dir = Path(os.getenv("LOG_DIR", "logs"))
    log_dir.mkdir(parents=True, exist_ok=True)

    max_bytes = int(os.getenv("LOG_MAX_BYTES", "1048576"))  # 1 MiB
    backups = int(os.getenv("LOG_BACKUPS", "7"))

    # Handlers
    file_handler = RotatingFileHandler(log_dir / "app.log",
                                       maxBytes=max_bytes, backupCount=backups,
                                       encoding="utf-8")
    console_handler = logging.StreamHandler()

    jf = JsonFormatter()
    file_handler.setFormatter(jf)
    console_handler.setFormatter(jf)

    rid_filter = RequestIdFilter()
    file_handler.addFilter(rid_filter)
    console_handler.addFilter(rid_filter)

    root = logging.getLogger()
    root.setLevel(level)

    # Reset handlers to avoid double-logging
    for h in list(root.handlers):
        root.removeHandler(h)
    root.addHandler(file_handler)
    root.addHandler(console_handler)

    # Quiet/noisy libs can be tuned here if you want
    logging.getLogger("uvicorn").setLevel(level)
    logging.getLogger("uvicorn.error").setLevel(level)
    logging.getLogger("uvicorn.access").setLevel(level)
    logging.getLogger("fastapi").setLevel(level)
    logging.getLogger("httpx").setLevel(level)
    logging.getLogger("googleapiclient").setLevel(level)
