"""
app/middleware/rate_limiter.py — Rate Limiting.
"""

import time
from collections import defaultdict
from typing import Dict, List, Tuple

from fastapi import Request, HTTPException
from loguru import logger


class RateLimiter:
    LIMITS: Dict[str, Tuple[int, int]] = {
        "/chat":               (10, 60),
        "/council/deliberate": (5,  60),
        "/register":           (5,  300),
        "/login":              (10, 60),
        "default":             (30, 60),
    }

    def __init__(self) -> None:
        self._requests: Dict[str, List[float]] = defaultdict(list)

    def _get_limit(self, path: str) -> Tuple[int, int]:
        for endpoint, limit in self.LIMITS.items():
            if endpoint != "default" and path.startswith(endpoint):
                return limit
        return self.LIMITS["default"]

    async def check(self, request: Request) -> None:
        client_ip = request.client.host if request.client else "unknown"
        path = request.url.path
        max_requests, window = self._get_limit(path)
        key = f"{client_ip}:{path}"
        now = time.time()

        self._requests[key] = [t for t in self._requests[key] if now - t < window]

        if len(self._requests[key]) >= max_requests:
            wait_sec = int(window - (now - self._requests[key][0])) + 1
            logger.warning(f"Rate limit exceeded | IP={client_ip} | path={path}")
            raise HTTPException(
                status_code=429,
                detail=f"Слишком много запросов. Подождите {wait_sec} сек.",
            )

        self._requests[key].append(now)

    def get_stats(self) -> Dict[str, int]:
        return {key: len(ts) for key, ts in self._requests.items()}


rate_limiter = RateLimiter()
