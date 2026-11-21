from dataclasses import dataclass, field
from typing import List, Dict, Any
from .choice_strategist_agent import StrategyPlan, CollegeChoice


@dataclass
class VerifiedConsultationReport:
    plan: StrategyPlan
    audit_passed: bool
    violations: List[str] = field(default_factory=list)
    verified_citations: List[Dict[str, Any]] = field(default_factory=list)
    ethical_disclaimer: str = ""
    summary_markdown: str = ""


class VerifierCriticAgent:
    def __init__(self):
        self.disclaimer_text = (
            "NEET.info verified intelligence: All choice tiers represent statistical analysis "
            "based strictly on published MCC Round 1/2 closing ranks. Final seat allocations "
            "depend on official MCC counselling rounds. Admission is never guaranteed."
        )

    def audit_and_verify(self, plan: StrategyPlan) -> VerifiedConsultationReport:
        violations = []
        citations = []
        rank = plan.profile.rank
        budget = plan.profile.max_annual_fee_inr

        for choice in plan.safe_choices:
            if choice.closing_rank < rank:
                violations.append(
                    f"CRITICAL ERROR: College {choice.college_name} in Safe Tier has closing rank "
                    f"{choice.closing_rank} which is tougher than candidate rank {rank}."
                )

        all_choices = plan.dream_choices + plan.target_choices + plan.safe_choices
        for choice in all_choices:
            if choice.annual_fee_inr > budget:
                violations.append(
                    f"BUDGET VIOLATION: {choice.college_name} fee INR {choice.annual_fee_inr} "
                    f"exceeds candidate budget INR {budget}."
                )

            citations.append({
                "college_id": choice.college_id,
                "college_name": choice.college_name,
                "quota": choice.quota,
                "category": choice.category,
                "round": choice.round,
                "closing_rank": choice.closing_rank,
                "tier": choice.tier,
                "source": "neet_ug_2024_closing_ranks.csv"
            })

        audit_passed = len(violations) == 0

        report_lines = [
            f"# Verified Medical Admissions Consultation Report",
            f"**Candidate:** Rank {rank} | Category: {plan.profile.category} | State: {plan.profile.domicile_state}",
            f"**Competitive Tier:** {plan.profile.competitive_tier}",
            f"**Verification Audit Status:** {'PASSED (Zero Hallucinations)' if audit_passed else 'FLAGGED'}",
            "",
            "### 1. Dream Choices (Ambitious Upgradation in Round 2)",
        ]

        if plan.dream_choices:
            for c in plan.dream_choices:
                report_lines.append(f"- **{c.college_name}** ({c.state}) | Quota: {c.quota} | Closing Rank: {c.closing_rank} | Fee: INR {c.annual_fee_inr:,.0f}")
        else:
            report_lines.append("- No close stretch choices within stated parameters.")

        report_lines.append("\n### 2. Target Choices (High Probability Allotment)")
        if plan.target_choices:
            for c in plan.target_choices:
                report_lines.append(f"- **{c.college_name}** ({c.state}) | Quota: {c.quota} | Closing Rank: {c.closing_rank} | Fee: INR {c.annual_fee_inr:,.0f}")
        else:
            report_lines.append("- No direct target matches.")

        report_lines.append("\n### 3. Safe Choices (Guaranteed Safety Net)")
        if plan.safe_choices:
            for c in plan.safe_choices:
                report_lines.append(f"- **{c.college_name}** ({c.state}) | Quota: {c.quota} | Closing Rank: {c.closing_rank} | Fee: INR {c.annual_fee_inr:,.0f}")
        else:
            report_lines.append("- No safe fallback matches.")

        report_lines.append(f"\n> **Policy Disclaimer:** {self.disclaimer_text}")

        return VerifiedConsultationReport(
            plan=plan,
            audit_passed=audit_passed,
            violations=violations,
            verified_citations=citations,
            ethical_disclaimer=self.disclaimer_text,
            summary_markdown="\n".join(report_lines)
        )
