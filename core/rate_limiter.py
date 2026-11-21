import time
import asyncio
from typing import Dict, Tuple, Optional
from pydantic import BaseModel, Field

class RateLimitResult(BaseModel):
    allowed: bool
    retry_after: float = 0.0
    remaining_requests: int
    remaining_tokens: int
    limit_requests: int
    limit_tokens: int

    def get_http_headers(self) -> Dict[str, str]:
        headers = {
            "X-RateLimit-Limit-Requests": str(self.limit_requests),
            "X-RateLimit-Remaining-Requests": str(max(0, self.remaining_requests)),
            "X-RateLimit-Limit-Tokens": str(self.limit_tokens),
            "X-RateLimit-Remaining-Tokens": str(max(0, self.remaining_tokens)),
        }
        if not self.allowed:
            headers["Retry-After"] = f"{self.retry_after:.2f}"
        return headers


class TokenBucket:
    def __init__(self, capacity: float, refill_rate_per_sec: float):
        self.capacity: float = float(capacity)
        self.refill_rate: float = float(refill_rate_per_sec)
        self.tokens: float = float(capacity)
        self.last_refill_time: float = time.monotonic()
        self.lock: asyncio.Lock = asyncio.Lock()

    async def consume(self, amount: int = 1) -> Tuple[bool, float, int]:
        async with self.lock:
            now = time.monotonic()
            elapsed = now - self.last_refill_time

            if elapsed > 0:
                self.tokens = min(self.capacity, self.tokens + (elapsed * self.refill_rate))
                self.last_refill_time = now

            if self.tokens >= amount:
                self.tokens -= amount
                return True, 0.0, int(self.tokens)
            else:
                shortfall = amount - self.tokens
                retry_after = shortfall / self.refill_rate if self.refill_rate > 0 else 1.0
                return False, retry_after, int(self.tokens)


class DualRateLimiter:
    def __init__(self, default_rpm: int = 60, default_tpm: int = 40000):
        self.default_rpm: int = default_rpm
        self.default_tpm: int = default_tpm
        self._buckets: Dict[str, Dict[str, TokenBucket]] = {}
        self._manager_lock: asyncio.Lock = asyncio.Lock()

    async def _get_or_create_buckets(
        self,
        client_id: str,
        rpm: Optional[int] = None,
        tpm: Optional[int] = None
    ) -> Tuple[TokenBucket, TokenBucket, int, int]:
        effective_rpm = rpm or self.default_rpm
        effective_tpm = tpm or self.default_tpm

        async with self._manager_lock:
            if client_id not in self._buckets:
                rpm_bucket = TokenBucket(
                    capacity=effective_rpm,
                    refill_rate_per_sec=effective_rpm / 60.0
                )
                tpm_bucket = TokenBucket(
                    capacity=effective_tpm,
                    refill_rate_per_sec=effective_tpm / 60.0
                )
                self._buckets[client_id] = {
                    "rpm": rpm_bucket,
                    "tpm": tpm_bucket,
                    "rpm_limit": effective_rpm,
                    "tpm_limit": effective_tpm
                }

            entry = self._buckets[client_id]
            return entry["rpm"], entry["tpm"], entry["rpm_limit"], entry["tpm_limit"]

    async def check_rate_limit(
        self,
        client_id: str,
        estimated_tokens: int = 100,
        custom_rpm: Optional[int] = None,
        custom_tpm: Optional[int] = None
    ) -> RateLimitResult:
        rpm_bucket, tpm_bucket, rpm_limit, tpm_limit = await self._get_or_create_buckets(
            client_id, custom_rpm, custom_tpm
        )

        rpm_allowed, rpm_retry, rpm_rem = await rpm_bucket.consume(amount=1)
        if not rpm_allowed:
            return RateLimitResult(
                allowed=False,
                retry_after=rpm_retry,
                remaining_requests=rpm_rem,
                remaining_tokens=int(tpm_bucket.tokens),
                limit_requests=rpm_limit,
                limit_tokens=tpm_limit
            )

        tpm_allowed, tpm_retry, tpm_rem = await tpm_bucket.consume(amount=estimated_tokens)
        if not tpm_allowed:
            async with rpm_bucket.lock:
                rpm_bucket.tokens = min(rpm_bucket.capacity, rpm_bucket.tokens + 1)

            return RateLimitResult(
                allowed=False,
                retry_after=tpm_retry,
                remaining_requests=int(rpm_bucket.tokens),
                remaining_tokens=tpm_rem,
                limit_requests=rpm_limit,
                limit_tokens=tpm_limit
            )

        return RateLimitResult(
            allowed=True,
            retry_after=0.0,
            remaining_requests=rpm_rem,
            remaining_tokens=tpm_rem,
            limit_requests=rpm_limit,
            limit_tokens=tpm_limit
        )

    def check_sync(
        self,
        client_id: str,
        estimated_tokens: int = 100,
        custom_rpm: Optional[int] = None,
        custom_tpm: Optional[int] = None
    ) -> RateLimitResult:
        effective_rpm = custom_rpm or self.default_rpm
        effective_tpm = custom_tpm or self.default_tpm

        if client_id not in self._buckets:
            rpm_bucket = TokenBucket(capacity=effective_rpm, refill_rate_per_sec=effective_rpm / 60.0)
            tpm_bucket = TokenBucket(capacity=effective_tpm, refill_rate_per_sec=effective_tpm / 60.0)
            self._buckets[client_id] = {
                "rpm": rpm_bucket,
                "tpm": tpm_bucket,
                "rpm_limit": effective_rpm,
                "tpm_limit": effective_tpm
            }

        entry = self._buckets[client_id]
        rpm_b = entry["rpm"]
        tpm_b = entry["tpm"]

        now = time.monotonic()
        elapsed_rpm = now - rpm_b.last_refill_time
        if elapsed_rpm > 0:
            rpm_b.tokens = min(rpm_b.capacity, rpm_b.tokens + (elapsed_rpm * rpm_b.refill_rate))
            rpm_b.last_refill_time = now

        elapsed_tpm = now - tpm_b.last_refill_time
        if elapsed_tpm > 0:
            tpm_b.tokens = min(tpm_b.capacity, tpm_b.tokens + (elapsed_tpm * tpm_b.refill_rate))
            tpm_b.last_refill_time = now

        if rpm_b.tokens < 1:
            shortfall = 1 - rpm_b.tokens
            retry = shortfall / rpm_b.refill_rate if rpm_b.refill_rate > 0 else 1.0
            return RateLimitResult(
                allowed=False,
                retry_after=retry,
                remaining_requests=int(rpm_b.tokens),
                remaining_tokens=int(tpm_b.tokens),
                limit_requests=entry["rpm_limit"],
                limit_tokens=entry["tpm_limit"]
            )

        if tpm_b.tokens < estimated_tokens:
            shortfall = estimated_tokens - tpm_b.tokens
            retry = shortfall / tpm_b.refill_rate if tpm_b.refill_rate > 0 else 1.0
            return RateLimitResult(
                allowed=False,
                retry_after=retry,
                remaining_requests=int(rpm_b.tokens),
                remaining_tokens=int(tpm_b.tokens),
                limit_requests=entry["rpm_limit"],
                limit_tokens=entry["tpm_limit"]
            )

        rpm_b.tokens -= 1
        tpm_b.tokens -= estimated_tokens

        return RateLimitResult(
            allowed=True,
            retry_after=0.0,
            remaining_requests=int(rpm_b.tokens),
            remaining_tokens=int(tpm_b.tokens),
            limit_requests=entry["rpm_limit"],
            limit_tokens=entry["tpm_limit"]
        )

    def reset(self, client_id: Optional[str] = None):
        if client_id:
            self._buckets.pop(client_id, None)
        else:
            self._buckets.clear()


DualTokenBucketRateLimiter = DualRateLimiter
