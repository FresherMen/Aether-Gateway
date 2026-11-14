import time
import asyncio
from typing import Dict, Tuple, Optional
from pydantic import BaseModel, Field

class RateLimitResult(BaseModel):
    """
    Standardized result emitted by the rate limiting engine.
    Contains decision flags, remaining balance, and standard HTTP headers.
    """
    allowed: bool
    retry_after: float = 0.0
    remaining_requests: int
    remaining_tokens: int
    limit_requests: int
    limit_tokens: int

    def get_http_headers(self) -> Dict[str, str]:
        """Construct standard RFC rate-limiting headers for reverse proxy responses."""
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
    """
    Atomic, Asynchronous Token-Bucket Algorithm Implementation.
    
    Mathematical Model:
      Tokens refill continuously at rate R (tokens/sec).
      Bucket holds at most capacity B (burst volume).
      
      At time t:
        tokens_new = min(B, tokens_old + (t - t_last) * R)
    """

    def __init__(self, capacity: float, refill_rate_per_sec: float):
        self.capacity: float = float(capacity)
        self.refill_rate: float = float(refill_rate_per_sec)
        self.tokens: float = float(capacity)  # Start full
        self.last_refill_time: float = time.monotonic()
        self.lock: asyncio.Lock = asyncio.Lock()

    async def consume(self, amount: int = 1) -> Tuple[bool, float, int]:
        """
        Attempts to consume `amount` tokens atomically.
        Returns: (allowed: bool, retry_after_seconds: float, remaining_tokens: int)
        """
        async with self.lock:
            now = time.monotonic()
            elapsed = now - self.last_refill_time

            # Refill tokens proportional to elapsed time
            if elapsed > 0:
                self.tokens = min(self.capacity, self.tokens + (elapsed * self.refill_rate))
                self.last_refill_time = now

            if self.tokens >= amount:
                self.tokens -= amount
                return True, 0.0, int(self.tokens)
            else:
                # Calculate exact wait time until enough tokens are regenerated
                shortfall = amount - self.tokens
                retry_after = shortfall / self.refill_rate if self.refill_rate > 0 else 1.0
                return False, retry_after, int(self.tokens)


class DualRateLimiter:
    """
    Enterprise Dual-Dimension Rate Limiter for AI Gateways.
    Simultaneously tracks and enforces:
      1. Requests Per Minute (RPM) - To protect server threadpool and connection limits.
      2. Tokens Per Minute (TPM)  - To protect downstream provider budget & LLM rate limits.
    """

    def __init__(self, default_rpm: int = 60, default_tpm: int = 40000):
        self.default_rpm: int = default_rpm
        self.default_tpm: int = default_tpm
        
        # In-memory tenant bucket store: client_id -> {"rpm": TokenBucket, "tpm": TokenBucket}
        self._buckets: Dict[str, Dict[str, TokenBucket]] = {}
        self._manager_lock: asyncio.Lock = asyncio.Lock()

    async def _get_or_create_buckets(
        self,
        client_id: str,
        rpm: Optional[int] = None,
        tpm: Optional[int] = None
    ) -> Tuple[TokenBucket, TokenBucket, int, int]:
        """Fetches or initializes the dual token buckets for a tenant with thread-safety."""
        effective_rpm = rpm or self.default_rpm
        effective_tpm = tpm or self.default_tpm

        async with self._manager_lock:
            if client_id not in self._buckets:
                # RPM: Capacity = RPM, Refill rate = RPM / 60.0 tokens per second
                rpm_bucket = TokenBucket(
                    capacity=effective_rpm,
                    refill_rate_per_sec=effective_rpm / 60.0
                )
                # TPM: Capacity = TPM, Refill rate = TPM / 60.0 tokens per second
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
        """
        Validates both RPM and TPM bounds before allowing a request into the gateway pipeline.
        If either bucket is exhausted, request is denied with exact retry headers.
        """
        rpm_bucket, tpm_bucket, rpm_limit, tpm_limit = await self._get_or_create_buckets(
            client_id, custom_rpm, custom_tpm
        )

        # 1. Check Requests Limit (consumes 1 request token)
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

        # 2. Check Tokens Limit (consumes estimated token volume)
        tpm_allowed, tpm_retry, tpm_rem = await tpm_bucket.consume(amount=estimated_tokens)
        if not tpm_allowed:
            # Rollback the 1 request token consumed since request is not being served
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

    def reset(self, client_id: Optional[str] = None):
        """Administrative helper to reset buckets for a tenant or globally."""
        if client_id:
            self._buckets.pop(client_id, None)
        else:
            self._buckets.clear()

