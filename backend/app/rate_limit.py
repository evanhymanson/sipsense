"""
Dedicated rate limiters for sensitive endpoints (auth, etc.).
Works in-memory per process — suitable for single-worker deployments.
For multi-worker production, swap to a Redis-backed implementation.
"""

import time
from collections import defaultdict

from fastapi import HTTPException, Request, status


class AuthRateLimiter:
    """Limits authentication attempts per IP address."""

    def __init__(self, max_attempts: int = 5, window_seconds: int = 60):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._attempts: dict[str, list[float]] = defaultdict(list)

    async def __call__(self, request: Request) -> None:
        client_ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        cutoff = now - self.window_seconds

        # Prune expired entries
        attempts = self._attempts[client_ip]
        self._attempts[client_ip] = [t for t in attempts if t > cutoff]

        if len(self._attempts[client_ip]) >= self.max_attempts:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many attempts. Try again in {self.window_seconds} seconds.",
            )

        self._attempts[client_ip].append(now)


auth_rate_limit = AuthRateLimiter(max_attempts=5, window_seconds=60)
