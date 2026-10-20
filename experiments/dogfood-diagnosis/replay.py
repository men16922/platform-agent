"""Replay saved diagnosis evidence through the existing Scorecard/GradeOutcome.

No model calls, role-classification surrogate, keyword semantic grading or new
evaluation engine. Semantic review remains explicit and bound to each report hash.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

from contract import Diagnosis, SnapshotQuestion, prepare, validate_citations
from src.agents.ai.eval_harness import GradeOutcome, Scorecard, Verdict


def replay(cases, expectations, reports):
    if {c["id"] for c in cases} != set(expectations["cases"]):
        raise ValueError("Every case requires an explicit expectation")
    scorecard = Scorecard(outcomes={"evidence_contract": [], "recovery_fixture": []})
    rows = []
    for case in cases:
        case_id = case["id"]
        if not re.fullmatch(r"[a-z0-9-]+", case_id):
            raise ValueError("Invalid case ID")
        path = reports / (case_id + ".json")
        report = json.loads(path.read_text()) if path.exists() else None
        expected = expectations["cases"][case_id]
        observed_recovery = None
        error = None
        try:
            if report is None or report.get("case_id") != case_id:
                raise ValueError("Missing or wrong report")
            request = SnapshotQuestion.model_validate(case["input"])
            if SnapshotQuestion.model_validate(report["request"]) != request:
                raise ValueError("Report request differs from the specified case")
            prepared = prepare(request)
            if report["prepared"] != prepared:
                raise ValueError("Reported applicable sources differ from the declared target/time contract")
            if prepared["sources"]:
                if report["status"] != "schema_citations_valid":
                    raise ValueError("No schema/citation-valid model result")
                result = Diagnosis.model_validate(report["output"])
                validate_citations(result, prepared)
                observed_recovery = result.recovery
            else:
                if report["status"] != "insufficient_applicable_evidence" or report.get("http_attempt_count") != 0:
                    raise ValueError("Inapplicable evidence must be withheld before the model request")
                observed_recovery = report["recovery"]
        except (ValueError, TypeError, KeyError) as exc:
            error = str(exc)

        contract_ok = error is None
        recovery_ok = contract_ok and observed_recovery == expected["recovery"]
        for metric, ok, reason in (
            ("evidence_contract", contract_ok, error or "Input binding, target/time selection and output citations match; no semantic claim"),
            ("recovery_fixture", recovery_ok, f"expected={expected['recovery']}; observed={observed_recovery}. {expected['reason']}"),
        ):
            scorecard.outcomes[metric].append(GradeOutcome(metric, "code", Verdict.PASS if ok else Verdict.FAIL, f"{case_id}: {reason}"))
        rows.append({
            "case_id": case_id,
            "report": str(path),
            "report_sha256": hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None,
            "contract": "pass" if contract_ok else "fail",
            "expected_recovery": expected["recovery"], "observed_recovery": observed_recovery,
            "recovery_fixture": "pass" if recovery_ok else "fail", "contract_error": error,
            "semantic_review": "required; categorical/schema success does not validate causal text",
        })
    return {"scope": expectations["scope"], "scoring": "existing src.agents.ai.eval_harness.Scorecard",
            "scorecard": scorecard.to_dict(), "cases": rows,
            "completion": "not_established_by_this_replay"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("reports", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    root = Path(__file__).parent
    result = replay(json.loads((root / "cases.json").read_text()),
                    json.loads((root / "expectations.json").read_text()), args.reports)
    with args.output.open("x") as handle:
        handle.write(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(result["scorecard"], ensure_ascii=False))
