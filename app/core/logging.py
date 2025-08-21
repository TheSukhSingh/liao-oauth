from __future__ import annotations
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

def setup_logging(log_dir: str = "logs") -> None:
    Path(log_dir).mkdir(parents=True, exist_ok=True)

    fmt = logging.Formatter(
        '%(asctime)s %(levelname)s %(name)s %(message)s'
    )

    file_handler = RotatingFileHandler(
        filename=str(Path(log_dir) / "app.log"),
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    file_handler.setLevel(logging.INFO)

    # Root logger
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(file_handler)

    # Quiet noisy loggers if needed (optional)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
