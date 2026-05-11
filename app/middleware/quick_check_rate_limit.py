from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from threading import Lock
from time import time

from fastapi import HTTPException, status
from starlette.requests import Request

RATE_LIMIT_MESSAGE = (
    "Zu viele Schnellcheck-Anfragen. Bitte versuchen Sie es später erneut."
)


@dataclass
class _RequestWindow:
    timestamps: deque[float] = field(default_factory=deque)


class QuickCheckRateLimiter:
    def __init__(self, *, limit_per_minute: int) -> None:
        self._limit_per_minute = limit_per_minute
        self._lock = Lock()
        self._windows: dict[str, _RequestWindow] = {}

    def verify(self, request: Request) -> None:
        if self._limit_per_minute <= 0:
            return

        ip = _client_ip(request)
        if not ip:
            return

        now = time()
        cutoff = now - 60.0
        with self._lock:
            window = self._windows.setdefault(ip, _RequestWindow())
            while window.timestamps and window.timestamps[0] <= cutoff:
                window.timestamps.popleft()
            if len(window.timestamps) >= self._limit_per_minute:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=RATE_LIMIT_MESSAGE,
                )
            window.timestamps.append(now)


def _client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        first = forwarded_for.split(",")[0].strip()
        if first:
            return first
    client = request.client
    return client.host if client else ""
