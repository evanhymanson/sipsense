"""
Dedicated rate limiters for sensitive endpoints (auth, etc.).
Works in-memory per process — suitable for single-worker deployments.
For multi-worker production, swap to a Redis-backed implementation.
"""

import time
from collections import defaultdict

from fastapi import HTTPException, Request, status


class AuthRateLimiter:
    """Limits authentication attempts per IP with progressive backoff.

    Level 1: max_attempts per window_seconds (default 5 per 60s)
    Level 2: lockout_duration after lockout_threshold attempts in lockout_window
             (default 15-min lockout after 15 attempts in 15 min)
    """

    def __init__(
        self,
        max_attempts: int = 5,
        window_seconds: int = 60,
        lockout_threshold: int = 15,
        lockout_window: int = 900,
        lockout_duration: int = 900,
    ):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.lockout_threshold = lockout_threshold
        self.lockout_window = lockout_window
        self.lockout_duration = lockout_duration
        self._attempts: dict[str, list[float]] = defaultdict(list)
        self._lockouts: dict[str, float] = {}

    async def __call__(self, request: Request) -> None:
        client_ip = request.client.host if request.client else "unknown"
        now = time.monotonic()

        # Check if IP is locked out
        lockout_until = self._lockouts.get(client_ip)
        if lockout_until and now < lockout_until:
            remaining = int(lockout_until - now)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many failed attempts. Try again in {remaining} seconds.",
                headers={"Retry-After": str(remaining)},
            )
        elif lockout_until:
            del self._lockouts[client_ip]

        # Prune expired entries
        cutoff = now - max(self.window_seconds, self.lockout_window)
        self._attempts[client_ip] = [t for t in self._attempts[client_ip] if t > cutoff]

        # Check lockout threshold (e.g. 15 attempts in 15 min)
        lockout_cutoff = now - self.lockout_window
        recent_total = sum(1 for t in self._attempts[client_ip] if t > lockout_cutoff)
        if recent_total >= self.lockout_threshold:
            self._lockouts[client_ip] = now + self.lockout_duration
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many failed attempts. Try again in {self.lockout_duration} seconds.",
                headers={"Retry-After": str(self.lockout_duration)},
            )

        # Check short-window limit (e.g. 5 per 60s)
        short_cutoff = now - self.window_seconds
        recent_short = sum(1 for t in self._attempts[client_ip] if t > short_cutoff)
        if recent_short >= self.max_attempts:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many attempts. Try again in {self.window_seconds} seconds.",
            )

        self._attempts[client_ip].append(now)


auth_rate_limit = AuthRateLimiter(max_attempts=5, window_seconds=60)


class ChatRateLimiter:
    """Per-user rate limiting for chat endpoints.

    Authenticated users: auth_max messages per window (default 20/min).
    Anonymous users: anon_max messages per window (default 5/min).
    """

    def __init__(self, auth_max: int = 20, anon_max: int = 5, window: int = 60):
        self.auth_max = auth_max
        self.anon_max = anon_max
        self.window = window
        self._buckets: dict[str, list[float]] = defaultdict(list)

    def check(self, key: str, is_authenticated: bool) -> None:
        now = time.monotonic()
        limit = self.auth_max if is_authenticated else self.anon_max
        cutoff = now - self.window
        self._buckets[key] = [t for t in self._buckets[key] if t > cutoff]
        if len(self._buckets[key]) >= limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Chat rate limit exceeded. Try again shortly.",
                headers={"Retry-After": str(self.window)},
            )
        self._buckets[key].append(now)


chat_rate_limiter = ChatRateLimiter()
