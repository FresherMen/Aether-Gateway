import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from agents.orchestrator import MultiAgentCounsellingOrchestrator
from core.semantic_cache import SemanticCache

CSV_PATH = ROOT_DIR / "services" / "counsel_engine" / "data" / "neet_ug_2024_closing_ranks.csv"


def run_stage3_benchmark():
    print("=" * 85)
    print("🤖 AETHER-GATEWAY: STAGE 3 (AUTONOMOUS MULTI-AGENT COUNSELLING) BENCHMARK")
    print("=" * 85)

    shared_cache = SemanticCache(similarity_threshold=0.80)
    orchestrator = MultiAgentCounsellingOrchestrator(
        data_csv_path=CSV_PATH,
        semantic_cache=shared_cache
    )

    test_consultations = [
        {
            "label": "Case 1: High-Rank State Domicile Candidate (Cold Request)",
            "rank": 1450,
            "category": "OBC",
            "domicile": "Uttar Pradesh",
            "budget": 60000.0,
            "expected_cache": "MISS (Agent Workflow Executes)"
        },
        {
            "label": "Case 2: Exact Candidate Re-Consultation (Cache Acceleration)",
            "rank": 1450,
            "category": "OBC",
            "domicile": "Uttar Pradesh",
            "budget": 60000.0,
            "expected_cache": "HIT (Served from Semantic Cache in < 1ms)"
        },
        {
            "label": "Case 3: Deemed & Private Budget Candidate (High Rank)",
            "rank": 48500,
            "category": "OPEN",
            "domicile": "Karnataka",
            "budget": 2000000.0,
            "expected_cache": "MISS (Deemed Evaluation Executes)"
        }
    ]

    for item in test_consultations:
        print(f"\n--- {item['label']} ---")
        print(f"Inputs     : Rank {item['rank']:,} | Category: {item['category']} | Domicile: {item['domicile']} | Budget: INR {item['budget']:,.0f}")
        print(f"Expectation: {item['expected_cache']}")

        t0 = time.time()
        res = orchestrator.consult(
            rank=item["rank"],
            category=item["category"],
            domicile_state=item["domicile"],
            max_annual_fee_inr=item["budget"]
        )
        elapsed_ms = (time.time() - t0) * 1000

        cache_badge = "⚡ CACHE HIT" if res["is_cached"] else "❄️ CACHE MISS (Agents Executed)"
        audit_badge = "✅ AUDIT PASSED" if res["audit_passed"] else "⚠️ FLAGGED"

        print(f"Status     : {cache_badge} | {audit_badge}")
        print(f"Latency    : {elapsed_ms:.2f} ms")
        print(f"Citations  : {len(res['citations'])} verified official records attached")
        print("-" * 50)
        lines = res["report_markdown"].split("\n")
        preview = "\n".join(lines[:12])
        print(preview)
        print("...")

    telemetry = shared_cache.get_telemetry()
    print("\n" + "=" * 85)
    print("📊 MULTI-AGENT & CACHE ORCHESTRATION TELEMETRY")
    print("=" * 85)
    print(f"Total Student Consultations: {telemetry['total_queries']}")
    print(f"Cache Hits                 : {telemetry['cache_hits']}")
    print(f"Cache Misses               : {telemetry['cache_misses']}")
    print(f"Hit Rate                   : {telemetry['hit_rate_pct']}%")
    print(f"Total Agent Latency Saved  : {telemetry['total_latency_saved_ms']} ms")
    print("=" * 85 + "\n")


if __name__ == "__main__":
    run_stage3_benchmark()
