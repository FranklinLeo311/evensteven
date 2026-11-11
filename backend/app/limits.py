"""Usage limits for the endpoints that call Claude: a per-visitor hourly limit and a daily limit for the whole app.

Counts live in memory, which is enough for a single-instance demo (they reset when the service restarts).
"""
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from .config import get_settings

_lock = threading.Lock()
_per_ip: dict[str, deque[float]] = defaultdict(deque)
_today = {"day": "", "count": 0}


def client_ip(request: Request) -> str:
    """The visitor's address (Render and other proxies put it first in X-Forwarded-For)."""
    forwarded = request.headers.get("x-forwarded-for", "")
    return forwarded.split(",")[0].strip() or (request.client.host if request.client else "unknown")


def check_ai_call(request: Request) -> None:
    """Count one Claude call for this visitor, or refuse it with 429 when a limit is reached."""
    settings = get_settings()
    now = time.time()
    day = time.strftime("%Y-%m-%d", time.gmtime(now))
    ip = client_ip(request)
    with _lock:
        if _today["day"] != day:
            _today.update(day=day, count=0)
        if _today["count"] >= settings.ai_calls_per_day:
            raise HTTPException(429, "The demo has reached today's limit of receipt reads. Please try again tomorrow.")
        calls = _per_ip[ip]
        while calls and now - calls[0] > 3600:
            calls.popleft()
        if len(calls) >= settings.ai_calls_per_ip_per_hour:
            wait_minutes = int((3600 - (now - calls[0])) // 60) + 1
            raise HTTPException(429, f"You've used this demo a lot in the last hour. Please try again in {wait_minutes} minutes.")
        calls.append(now)
        _today["count"] += 1
