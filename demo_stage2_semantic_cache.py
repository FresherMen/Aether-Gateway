import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.semantic_cache import SemanticCache
from services.counsel_engine.engine.rag_pipeline import NEETCounsellingRAG


def run_stage2_benchmark():
    print("=" * 80)
    print("🚀 AETHER-GATEWAY: STAGE 2 (SEMANTIC VECTOR CACHE) BENCHMARK")
    print("=" * 80)

    cache = SemanticCache(similarity_threshold=0.72)
    rag = NEETCounsellingRAG()

    test_queries = [
        (
            "Query 1 (Cold Request)",
            "What was the Round 1 closing rank for AIIMS New Delhi for OPEN category?",
            "Expected: CACHE MISS (Invokes Downstream RAG Engine)"
        ),
        (
            "Query 2 (Semantic Rephrase A)",
            "AIIMS Delhi Round 1 General closing cut-off",
            "Expected: CACHE HIT (Served from Semantic Vector Cache in < 2ms)"
        ),
        (
            "Query 3 (Semantic Rephrase B)",
            "cut-off rank of AIIMS New Delhi for UR category in Round 1",
            "Expected: CACHE HIT (Served from Semantic Vector Cache in < 2ms)"
        ),
        (
            "Query 4 (Unseen Topic Cold Request)",
            "What is the annual tuition fee for IPGMER SSKM Hospital Kolkata for MBBS?",
            "Expected: CACHE MISS (Invokes Downstream RAG Engine)"
        ),
        (
            "Query 5 (Unseen Topic Rephrase)",
            "IPGMER SSKM Kolkata MBBS fee structure",
            "Expected: CACHE HIT (Served from Semantic Vector Cache in < 2ms)"
        )
    ]

    for label, query, expectation in test_queries:
        print(f"\n--- {label} ---")
        print(f"User Query : \"{query}\"")
        print(f"Note       : {expectation}")

        t0 = time.time()
        cached_resp, sim_score = cache.lookup(query)

        if cached_resp is not None:
            elapsed_ms = (time.time() - t0) * 1000
            print(f"Result     : ⚡ CACHE HIT! (Similarity Score: {sim_score:.3f})")
            print(f"Latency    : {elapsed_ms:.2f} ms [Sub-2ms Zero GPU Cost]")
            print(f"Answer     : {cached_resp.get('answer', '')[:90]}...")
            print(f"Citations  : {len(cached_resp.get('citations', []))} verified sources attached")
        else:
            rag_start = time.time()
            rag_resp = rag.ask(query)
            elapsed_ms = (time.time() - rag_start) * 1000
            cache.store(query, rag_resp)
            print(f"Result     : ❄️ CACHE MISS (Highest Similarity: {sim_score:.3f})")
            print(f"Latency    : {elapsed_ms:.2f} ms [Downstream RAG Execution]")
            print(f"Answer     : {rag_resp.get('answer', '')[:90]}...")
            print(f"Action     : Stored vector embedding in Semantic Cache")

    telemetry = cache.get_telemetry()
    print("\n" + "=" * 80)
    print("📊 STAGE 2 SEMANTIC CACHE TELEMETRY SUMMARY")
    print("=" * 80)
    print(f"Total Requests Handled : {telemetry['total_queries']}")
    print(f"Cache Hits             : {telemetry['cache_hits']} ({telemetry['hit_rate_pct']}%)")
    print(f"Cache Misses           : {telemetry['cache_misses']}")
    print(f"Entries in Cache       : {telemetry['cached_entries_count']}")
    print(f"Est. Latency Saved     : {telemetry['total_latency_saved_ms']} ms")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    run_stage2_benchmark()
