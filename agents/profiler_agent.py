from dataclasses import dataclass, field
from typing import List, Dict, Any


@dataclass
class StudentProfile:
    rank: int
    category: str
    domicile_state: str
    course: str = "MBBS"
    max_annual_fee_inr: float = 100000.0
    eligible_quotas: List[str] = field(default_factory=list)
    competitive_tier: str = "General"
    profile_summary: str = ""


class ProfilerAgent:
    def __init__(self):
        self.valid_categories = {"OPEN", "OBC", "EWS", "SC", "ST"}
        self.valid_courses = {"MBBS", "BDS"}

    def audit_profile(
        self,
        rank: int,
        category: str,
        domicile_state: str,
        course: str = "MBBS",
        max_annual_fee_inr: float = 100000.0
    ) -> StudentProfile:
        norm_cat = category.strip().upper()
        if norm_cat not in self.valid_categories:
            norm_cat = "OPEN"

        norm_course = course.strip().upper()
        if norm_course not in self.valid_courses:
            norm_course = "MBBS"

        quotas = ["AIQ"]
        if domicile_state.strip():
            quotas.append("State Quota")

        if max_annual_fee_inr >= 1000000.0:
            quotas.append("Deemed")

        if rank <= 1500:
            tier = "National Top Tier (AIIMS / Premier Central Institutes)"
        elif rank <= 8000:
            tier = "High Competitive Tier (Top State Govt Medical Colleges)"
        elif rank <= 25000:
            tier = "State Merit Tier (Peripheral Govt Medical Colleges)"
        else:
            tier = "Private & Deemed University Tier"

        summary = (
            f"Candidate Rank: {rank} | Category: {norm_cat} | Domicile: {domicile_state} | "
            f"Course: {norm_course} | Budget Cap: INR {max_annual_fee_inr:,.0f} | Tier: {tier}"
        )

        return StudentProfile(
            rank=rank,
            category=norm_cat,
            domicile_state=domicile_state.strip().title(),
            course=norm_course,
            max_annual_fee_inr=max_annual_fee_inr,
            eligible_quotas=quotas,
            competitive_tier=tier,
            profile_summary=summary
        )
