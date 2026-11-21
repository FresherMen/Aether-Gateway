import csv
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Any
from .profiler_agent import StudentProfile


@dataclass
class CollegeChoice:
    college_id: str
    college_name: str
    state: str
    quota: str
    category: str
    round: str
    closing_rank: int
    annual_fee_inr: float
    seat_type: str
    tier: str


@dataclass
class StrategyPlan:
    profile: StudentProfile
    dream_choices: List[CollegeChoice] = field(default_factory=list)
    target_choices: List[CollegeChoice] = field(default_factory=list)
    safe_choices: List[CollegeChoice] = field(default_factory=list)
    total_options_evaluated: int = 0


class ChoiceStrategistAgent:
    def __init__(self, data_csv_path: Path):
        self.data_csv_path = data_csv_path

    def _load_eligible_records(self, profile: StudentProfile) -> List[Dict[str, Any]]:
        eligible = []
        with open(self.data_csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("course") != profile.course:
                    continue
                if row.get("category") != profile.category:
                    continue

                row_quota = row.get("quota", "")
                row_state = row.get("state", "")

                if row_quota == "State Quota" and row_state.lower() != profile.domicile_state.lower():
                    continue

                fee = float(row.get("annual_tuition_fee_inr", 0)) if row.get("annual_tuition_fee_inr", "").isdigit() else 0.0
                if fee > profile.max_annual_fee_inr:
                    continue

                c_rank = int(row.get("closing_rank", 0)) if row.get("closing_rank", "").isdigit() else 0
                eligible.append({
                    "college_id": row.get("college_id"),
                    "college_name": row.get("college_name"),
                    "state": row_state,
                    "quota": row_quota,
                    "category": row.get("category"),
                    "round": row.get("round"),
                    "closing_rank": c_rank,
                    "annual_fee_inr": fee,
                    "seat_type": row.get("seat_type")
                })
        return eligible

    def formulate_plan(self, profile: StudentProfile) -> StrategyPlan:
        records = self._load_eligible_records(profile)
        dream: List[CollegeChoice] = []
        target: List[CollegeChoice] = []
        safe: List[CollegeChoice] = []

        rank = profile.rank

        for r in records:
            c_rank = r["closing_rank"]
            if c_rank == 0:
                continue

            if rank * 0.65 <= c_rank < rank:
                dream.append(
                    CollegeChoice(
                        college_id=r["college_id"],
                        college_name=r["college_name"],
                        state=r["state"],
                        quota=r["quota"],
                        category=r["category"],
                        round=r["round"],
                        closing_rank=c_rank,
                        annual_fee_inr=r["annual_fee_inr"],
                        seat_type=r["seat_type"],
                        tier="Dream (Ambitious Upgradation)"
                    )
                )
            elif rank <= c_rank <= rank * 1.8:
                target.append(
                    CollegeChoice(
                        college_id=r["college_id"],
                        college_name=r["college_name"],
                        state=r["state"],
                        quota=r["quota"],
                        category=r["category"],
                        round=r["round"],
                        closing_rank=c_rank,
                        annual_fee_inr=r["annual_fee_inr"],
                        seat_type=r["seat_type"],
                        tier="Target (High Probability Allotment)"
                    )
                )
            elif c_rank > rank * 1.8:
                safe.append(
                    CollegeChoice(
                        college_id=r["college_id"],
                        college_name=r["college_name"],
                        state=r["state"],
                        quota=r["quota"],
                        category=r["category"],
                        round=r["round"],
                        closing_rank=c_rank,
                        annual_fee_inr=r["annual_fee_inr"],
                        seat_type=r["seat_type"],
                        tier="Safe (Guaranteed Safety Net)"
                    )
                )

        dream.sort(key=lambda x: x.closing_rank)
        target.sort(key=lambda x: x.closing_rank)
        safe.sort(key=lambda x: x.closing_rank)

        return StrategyPlan(
            profile=profile,
            dream_choices=dream[:5],
            target_choices=target[:5],
            safe_choices=safe[:5],
            total_options_evaluated=len(records)
        )
