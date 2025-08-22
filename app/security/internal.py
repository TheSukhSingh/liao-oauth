from __future__ import annotations
from fastapi import Header, HTTPException, Request
from typing import Optional, List
import ipaddress

from app.core.config import settings

def _ip_allowed(client_ip: str, allowed: List[str]) -> bool:
    """
    True if client_ip is in any allowed CIDR or exact host string.
    Empty allowed => allow all (IP check disabled).
    """
    if not allowed:
        return True
    try:
        ip = ipaddress.ip_address(client_ip)
    except ValueError:
        # If parsing fails, fall back to string compare
        return client_ip in allowed

    for entry in allowed:
        entry = entry.strip()
        if not entry:
            continue
        # exact host string?
        try:
            if ip == ipaddress.ip_address(entry):
                return True
        except ValueError:
            pass
        # CIDR/network?
        try:
            if ip in ipaddress.ip_network(entry, strict=False):
                return True
        except ValueError:
            # not a network; fall back to raw compare (e.g., "localhost")
            if client_ip == entry:
                return True
    return False

def _get_client_ip(request: Request) -> str:
    # honor proxies if present; take the first hop
    xf = request.headers.get("x-forwarded-for")
    if xf:
        return xf.split(",")[0].strip()
    return request.client.host if request.client else ""

def _normalize_host(s: str) -> str:
    return "127.0.0.1" if s.strip().lower() == "localhost" else s.strip()

async def require_internal(
    request: Request,
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
):
    if not x_api_key or x_api_key != settings.API_INTERNAL_KEY:
        # using 401 for both missing/invalid is fine (reduces key probing)
        raise HTTPException(status_code=401, detail="missing or invalid X-API-Key")

    client_ip = _get_client_ip(request)
    allowed = [_normalize_host(x) for x in settings.INTERNAL_ALLOWED_IPS or []]
    if not _ip_allowed(client_ip, allowed):
        raise HTTPException(status_code=403, detail="ip_not_allowed")

