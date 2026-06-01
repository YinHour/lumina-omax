"""Simple in-memory rate limiter for API endpoints."""

import time
from collections import defaultdict
from typing import Dict, Tuple

from fastapi import HTTPException, Request, status


class RateLimiter:
    """Sliding window rate limiter with configurable window and max requests."""

    def __init__(self, max_requests: int = 5, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._clients: Dict[str, Tuple[float, int]] = defaultdict(
            lambda: (0.0, 0)
        )

    def _cleanup_expired(self):
        """Remove expired entries to prevent memory leaks."""
        now = time.time()
        expired = [
            key
            for key, (start, _count) in self._clients.items()
            if now - start > self.window_seconds
        ]
        for key in expired:
            del self._clients[key]

    async def check(self, request: Request):
        """Check rate limit for the given request. Raises HTTPException if exceeded."""
        now = time.time()

        # Identify client by IP (use X-Forwarded-For if behind proxy)
        forwarded = request.headers.get("X-Forwarded-For")
        client_ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")

        # Periodic cleanup
        if len(self._clients) > 1000:
            self._cleanup_expired()

        window_start, count = self._clients[client_ip]
        if now - window_start > self.window_seconds:
            # Start new window
            self._clients[client_ip] = (now, 1)
        elif count >= self.max_requests:
            retry_after = int(self.window_seconds - (now - window_start))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many requests. Try again in {retry_after} seconds.",
                headers={"Retry-After": str(retry_after)},
            )
        else:
            self._clients[client_ip] = (window_start, count + 1)


# Per-endpoint rate limiters
login_limiter = RateLimiter(max_requests=10, window_seconds=60)
register_limiter = RateLimiter(max_requests=5, window_seconds=300)
