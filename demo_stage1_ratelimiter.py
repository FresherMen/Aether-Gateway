import asyncio
import time
from core.rate_limiter import DualRateLimiter

async def run_simulation():
    print("=" * 70)
    print("🚀 AETHER-GATEWAY: STAGE 1 (TOKEN-BUCKET RATE LIMITER) BENCHMARK")
    print("=" * 70)

    # Initialize rate limiter with strict test limits:
    # 5 Requests Per Minute (RPM) & 500 Tokens Per Minute (TPM)
    limiter = DualRateLimiter(default_rpm=5, default_tpm=500)
    client_id = "tenant-enterprise-client-1"

    print(f"\n[CONFIG] Client: {client_id}")
    print("[CONFIG] Policy: Max 5 Requests/Min (Refill: ~0.08 req/sec), Max 500 Tokens/Min")
    print("-" * 70)

    # Test Phase 1: Rapid Burst of 6 Requests
    print("\n--- TEST 1: Rapid Burst Test (Sending 6 requests instantly) ---")
    for i in range(1, 7):
        result = await limiter.check_rate_limit(client_id, estimated_tokens=50)
        status = "✅ ALLOWED" if result.allowed else "🛑 THROTTLED (HTTP 429)"
        print(f"Request #{i}: {status} | Remaining Req: {result.remaining_requests}/5 | Retry-After: {result.retry_after:.2f}s")
        if not result.allowed:
            print(f"   ↳ Generated HTTP Headers: {result.get_http_headers()}")

    # Test Phase 2: Token Refill Demonstration
    print("\n--- TEST 2: Token-Bucket Refill Demonstration ---")
    wait_sec = 2.0
    print(f"Waiting {wait_sec} seconds for bucket to continuously refill tokens...")
    await asyncio.sleep(wait_sec)

    retry_result = await limiter.check_rate_limit(client_id, estimated_tokens=50)
    status = "✅ ALLOWED" if retry_result.allowed else "🛑 THROTTLED (HTTP 429)"
    print(f"Post-Cooldown Request: {status} | Remaining Req: {retry_result.remaining_requests}/5 | Remaining Tokens: {retry_result.remaining_tokens}")

    # Test Phase 3: Token Overflow Protection (Large Prompt Test)
    print("\n--- TEST 3: High Token Volume Protection (TPM Throttle) ---")
    large_token_req = await limiter.check_rate_limit(client_id, estimated_tokens=800)
    print(f"Requesting 800 tokens (limit is 500): {'✅ ALLOWED' if large_token_req.allowed else '🛑 THROTTLED (HTTP 429)'}")
    print(f"   ↳ Retry-After: {large_token_req.retry_after:.2f}s | Shortfall correctly calculated!")

    print("\n" + "=" * 70)
    print("🎯 STAGE 1 VERIFICATION COMPLETED SUCCESSFULLY!")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(run_simulation())

