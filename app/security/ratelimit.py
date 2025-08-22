from __future__ import annotations
import time
from typing import Dict, Tuple, Optional
from fastapi import Header, HTTPException
from app.core.config import settings

# Simple fixed-window counters held in-process.
# Keys: ("key", api_key) or ("user", api_key, user_id) -> (window_start_epoch, count)
_counters: Dict[Tuple[str, ...], Tuple[int, int]] = {}

def _bump(key: Tuple[str, ...], max_requests: int, window_seconds: int):
    now = int(time.time())
    window = now - (now % window_seconds)  # start-of-window
    start, count = _counters.get(key, (window, 0))
    if start != window:
        start, count = window, 0
    count += 1
    _counters[key] = (start, count)
    remaining = max_requests - count
    if remaining < 0:
        retry_after = start + window_seconds - now
        raise HTTPException(
            status_code=429,
            detail="rate_limit_exceeded",
            headers={"Retry-After": str(max(0, retry_after))},
        )

async def limit_by_api_key(x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")):
    if not x_api_key:
        # The internal guard will already reject missing/invalid keys.
        raise HTTPException(status_code=401, detail="missing or invalid X-API-Key")
    _bump(
        ("key", x_api_key),
        settings.RATE_LIMIT_MAX_PER_KEY,
        settings.RATE_LIMIT_WINDOW_SECONDS,
    )

async def limit_by_user(user_id: str, x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")):
    if not x_api_key:
        raise HTTPException(status_code=401, detail="missing or invalid X-API-Key")
    _bump(
        ("user", x_api_key, user_id),
        settings.RATE_LIMIT_MAX_PER_USER,
        settings.RATE_LIMIT_WINDOW_SECONDS,
    )
