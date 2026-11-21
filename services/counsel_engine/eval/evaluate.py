import sys
import json
import time
from pathlib import Path
from typing import List, Dict, Any

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from engine.config import EVAL_DIR
from engine.rag_pipeline import NEETCounsellingRAG


def run_benchmark() -> Dict[str, Any]:
    bench_file = EVAL_DIR / "test_bench.json"
    with open(bench_file, "r", encoding="utf-8") as f:
        cases: List[Dict[str, Any]] = json.load(f)

    rag = NEETCounsellingRAG()

    results: List[Dict[str, Any]] = []
    total_passed = 0
    refusal_tests = 0
    refusal_passed = 0
    citation_tests = 0
    citation_passed = 0
    latencies: List[float] = []

    print(f"\nRunning NEET.info Local RAG Evaluation Suite ({len(cases)} test cases)...\n")
    print(f"{'ID':<6} | {'Type':<24} | {'Status':<6} | {'Citations':<10} | {'Latency':<8} | {'Query':<40}")
    print("-" * 105)

    for case in cases:
        case_id = case["id"]
        c_type = case["type"]
        query = case["query"]
        expected = case["expected_behavior"]
        expected_tokens = [t.lower() for t in case.get("expected_tokens", [])]
        req_citation = case.get("requires_citation", False)

        resp = rag.ask(query)
        answer = resp["answer"].lower()
        is_refused = resp["is_refused"]
        citations = resp.get("citations", [])
        latency = resp.get("latency_ms", 0.0)
        latencies.append(latency)

        passed = False

        if expected == "refuse":
            refusal_tests += 1
            if is_refused or "not in the sources" in answer:
                passed = True
                refusal_passed += 1

        elif expected == "refuse_or_disclaim":
            refusal_tests += 1
            if is_refused or any(t in answer for t in expected_tokens):
                passed = True
                refusal_passed += 1

        elif expected == "answer":
            token_match = any(t in answer for t in expected_tokens)
            has_citations = len(citations) > 0 if req_citation else True

            if req_citation:
                citation_tests += 1
                if has_citations:
                    citation_passed += 1

            if not is_refused and token_match and has_citations:
                passed = True

        if passed:
            total_passed += 1

        status_str = "PASS" if passed else "FAIL"
        cite_str = f"{len(citations)} cites" if len(citations) > 0 else "None"
        lat_str = f"{latency:.1f}ms"
        display_q = (query[:37] + "...") if len(query) > 40 else query

        print(f"{case_id:<6} | {c_type:<24} | {status_str:<6} | {cite_str:<10} | {lat_str:<8} | {display_q:<40}")

        results.append({
            "id": case_id,
            "type": c_type,
            "query": query,
            "expected_behavior": expected,
            "passed": passed,
            "is_refused": is_refused,
            "citation_count": len(citations),
            "latency_ms": latency,
            "answer_preview": resp["answer"][:120]
        })

    accuracy = (total_passed / len(cases)) * 100
    refusal_acc = (refusal_passed / refusal_tests * 100) if refusal_tests else 100.0
    citation_acc = (citation_passed / citation_tests * 100) if citation_tests else 100.0
    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0

    print("-" * 105)
    print(f"\nBenchmark Summary:")
    print(f"Total Test Cases      : {len(cases)}")
    print(f"Passed                : {total_passed} / {len(cases)} ({accuracy:.1f}%)")
    print(f"Refusal Accuracy      : {refusal_passed} / {refusal_tests} ({refusal_acc:.1f}%)")
    print(f"Citation Accuracy     : {citation_passed} / {citation_tests} ({citation_acc:.1f}%)")
    print(f"Average Latency       : {avg_latency:.2f} ms\n")

    report_path = EVAL_DIR / "benchmark_results.md"
    generate_markdown_report(results, accuracy, refusal_acc, citation_acc, avg_latency, report_path)

    return {
        "accuracy": accuracy,
        "refusal_accuracy": refusal_acc,
        "citation_accuracy": citation_acc,
        "avg_latency_ms": avg_latency,
        "results": results
    }


def generate_markdown_report(
    results: List[Dict[str, Any]],
    accuracy: float,
    refusal_acc: float,
    citation_acc: float,
    avg_latency: float,
    out_path: Path
):
    lines = [
        "# NEET.info Local RAG Evaluation Report",
        "",
        "## Summary Metrics",
        f"- **Overall Test Accuracy**: {accuracy:.1f}% ({sum(1 for r in results if r['passed'])}/{len(results)})",
        f"- **Adversarial & Unknown Refusal Rate**: {refusal_acc:.1f}%",
        f"- **Citation Enforcement Rate**: {citation_acc:.1f}%",
        f"- **Average Query Latency**: {avg_latency:.2f} ms",
        "",
        "## Detailed Benchmark Results",
        "",
        "| ID | Evaluation Type | Query | Result | Citations | Latency | Model Response Preview |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
    ]

    for r in results:
        status_badge = "PASS" if r["passed"] else "FAIL"
        query_safe = r["query"].replace("|", "\\|")
        ans_safe = r["answer_preview"].replace("|", "\\|").replace("\n", " ")
        lines.append(
            f"| {r['id']} | {r['type']} | {query_safe} | {status_badge} | {r['citation_count']} | {r['latency_ms']:.1f}ms | {ans_safe} |"
        )

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    run_benchmark()
