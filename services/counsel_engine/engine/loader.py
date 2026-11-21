import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any


@dataclass
class Document:
    page_content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    doc_id: str = ""


def load_closing_ranks(csv_path: Path) -> List[Document]:
    documents: List[Document] = []
    
    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader):
            college_id = row.get("college_id", "").strip()
            college_name = row.get("college_name", "").strip()
            state = row.get("state", "").strip()
            course = row.get("course", "").strip()
            quota = row.get("quota", "").strip()
            category = row.get("category", "").strip()
            round_name = row.get("round", "").strip()
            opening_rank = row.get("opening_rank", "").strip()
            closing_rank = row.get("closing_rank", "").strip()
            seat_type = row.get("seat_type", "").strip()
            fee = row.get("annual_tuition_fee_inr", "").strip()

            content = (
                f"In NEET UG 2024 {round_name}, {college_name} (Code: {college_id}) in {state} "
                f"for course {course} under {quota} quota for {category} category had an "
                f"opening rank of {opening_rank} and a closing rank (cut-off) of {closing_rank}. "
                f"Seat Type: {seat_type}. Annual Tuition Fee: INR {fee}."
            )

            metadata = {
                "source": "neet_ug_2024_closing_ranks.csv",
                "doc_type": "cut_off_record",
                "college_id": college_id,
                "college_name": college_name,
                "state": state,
                "course": course,
                "quota": quota,
                "category": category,
                "round": round_name,
                "opening_rank": int(opening_rank) if opening_rank.isdigit() else 0,
                "closing_rank": int(closing_rank) if closing_rank.isdigit() else 0,
                "seat_type": seat_type,
                "annual_tuition_fee_inr": fee,
            }

            documents.append(
                Document(
                    page_content=content,
                    metadata=metadata,
                    doc_id=f"rank_{idx}_{college_id}_{category}_{round_name.replace(' ', '_')}"
                )
            )

    return documents


def load_counselling_faq(md_path: Path) -> List[Document]:
    documents: List[Document] = []
    
    with open(md_path, mode="r", encoding="utf-8") as f:
        text = f.read()

    sections = text.split("\n## ")
    main_title = sections[0].replace("#", "").strip() if sections else "MCC Counselling Guidelines"

    for idx, sec in enumerate(sections[1:], start=1):
        lines = sec.strip().split("\n")
        header = lines[0].strip()
        body = "\n".join(lines[1:]).strip()

        content = f"Section: {header}\nDetails: {body}"
        metadata = {
            "source": "counselling_rules_faq.md",
            "doc_type": "counselling_guideline",
            "section_title": header,
            "main_title": main_title,
        }

        documents.append(
            Document(
                page_content=content,
                metadata=metadata,
                doc_id=f"rule_sec_{idx}"
            )
        )

    return documents


def load_all_documents(data_dir: Path) -> List[Document]:
    csv_file = data_dir / "neet_ug_2024_closing_ranks.csv"
    md_file = data_dir / "counselling_rules_faq.md"

    docs: List[Document] = []
    if csv_file.exists():
        docs.extend(load_closing_ranks(csv_file))
    if md_file.exists():
        docs.extend(load_counselling_faq(md_file))

    return docs
