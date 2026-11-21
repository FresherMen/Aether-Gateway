import time
from pathlib import Path
from typing import Dict, Any, Optional
from .profiler_agent import ProfilerAgent, StudentProfile
from .choice_strategist_agent import ChoiceStrategistAgent
from .verifier_critic_agent import VerifierCriticAgent, VerifiedConsultationReport

try:
    from core.semantic_cache import SemanticCache
except ImportError:
    from ..core.semantic_cache import SemanticCache


class MultiAgentCounsellingOrchestrator:
    def __init__(self, data_csv_path: Path, semantic_cache: Optional[SemanticCache] = None):
        self.profiler = ProfilerAgent()
        self.strategist = ChoiceStrategistAgent(data_csv_path)
        self.critic = VerifierCriticAgent()
        self.cache = semantic_cache or SemanticCache()

    def consult(
        self,
        rank: int,
        category: str,
        domicile_state: str,
        course: str = "MBBS",
        max_annual_fee_inr: float = 100000.0
    ) -> Dict[str, Any]:
        start_time = time.time()
        cache_key = (
            f"strategy_rank_{rank}_cat_{category.lower()}_state_{domicile_state.lower()}_"
            f"course_{course.lower()}_fee_{int(max_annual_fee_inr)}"
        )

        cached_res, sim = self.cache.lookup(cache_key)
        if cached_res is not None:
            latency_ms = round((time.time() - start_time) * 1000, 2)
            return {
                "report_markdown": cached_res.get("summary_markdown", ""),
                "audit_passed": cached_res.get("audit_passed", True),
                "citations": cached_res.get("citations", []),
                "is_cached": True,
                "similarity_score": sim,
                "latency_ms": latency_ms
            }

        profile = self.profiler.audit_profile(
            rank=rank,
            category=category,
            domicile_state=domicile_state,
            course=course,
            max_annual_fee_inr=max_annual_fee_inr
        )

        plan = self.strategist.formulate_plan(profile)
        verified_report = self.critic.audit_and_verify(plan)

        latency_ms = round((time.time() - start_time) * 1000, 2)
        response_payload = {
            "summary_markdown": verified_report.summary_markdown,
            "audit_passed": verified_report.audit_passed,
            "citations": verified_report.verified_citations,
            "latency_ms": latency_ms
        }

        self.cache.store(cache_key, response_payload)

        return {
            "report_markdown": verified_report.summary_markdown,
            "audit_passed": verified_report.audit_passed,
            "citations": verified_report.verified_citations,
            "is_cached": False,
            "similarity_score": 0.0,
            "latency_ms": latency_ms
        }
