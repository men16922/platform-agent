"""Replay actual UI records with explicit, hash-bound assistant semantic reviews.

Uses the repository Scorecard rather than a new evaluator. Code checks request,
response and no-tool boundaries; the review file supplies semantic judgments.
No keyword-based causal grading and no new model or infrastructure calls.
"""
import argparse
import hashlib
import json
from pathlib import Path

from src.agents.ai.eval_harness import GradeOutcome, Scorecard, Verdict


def review_ui(directory: Path) -> dict:
    cases = json.loads((directory / "cases.json").read_text())
    reviews = json.loads((directory / "reviews.json").read_text())
    if set(reviews["cases"]) != {c["id"] for c in cases}:
        raise ValueError("Every declared case requires an explicit review")
    names = ("exact_prompt", "input_binding", "response_completion", "no_tool_calls", "semantic_review")
    scorecard = Scorecard(outcomes={name: [] for name in names})
    rows = []
    for case in cases:
        case_id = case["id"]
        path = directory / f"{case_id}-run.json"
        raw = path.read_bytes()
        report = json.loads(raw)
        state = report["state"]
        request = state["request"]
        done = state["events"][-1]
        completion = done.get("model_completion") or {}
        judgment = reviews["cases"][case_id]
        text = completion.get("text", "")
        # The existing single-line HTML input removes the single separator LF.
        # Retain the failed exact-byte metric; permit only this observed transform,
        # not arbitrary whitespace normalization or changes inside the JSON data.
        expected_ui = case["prompt"].replace("Supplied snapshot:\n{", "Supplied snapshot:{", 1)
        exact_prompt = request.get("instruction") == case["prompt"]
        input_matches = exact_prompt or request.get("instruction") == expected_ui
        bound = (input_matches and request.get("read_only") is True
                 and request.get("model") == "local-qwen" and request.get("provider") == "onprem"
                 and report["claims"] == 1 and done.get("request_id") == report["request_id"])
        complete = done.get("type") == "done" and completion.get("status") == "complete"
        no_tools = (report.get("tool_calls") == {} and completion.get("tool_call_attempts") == 0
                    and not any(e.get("type") in {"tool_call", "tool_result"} for e in state["events"])
                    and not (report.get("record") or {}).get("deployment_id"))
        review_bound = (judgment["report_sha256"] == hashlib.sha256(raw).hexdigest()
                        and judgment["quotes"] and all(quote and quote in text for quote in judgment["quotes"]))
        semantics = bound and complete and review_bound and judgment["status"] == "pass"
        for name, passed, reason in (
            ("exact_prompt", exact_prompt, "Original declared prompt byte equality; the single-line input removes the separator LF"),
            ("input_binding", bound, "Declared prompt or exactly one removed separator LF; local read-only mode, request ID and one claim"),
            ("response_completion", complete, f"Model completion: {completion.get('status')}; not an action success grade"),
            ("no_tool_calls", no_tools, "Supplied-snapshot-only request; no operational tool or deployment record"),
            ("semantic_review", semantics, judgment["reason"] if review_bound else "Review hash or quoted response mismatch"),
        ):
            scorecard.outcomes[name].append(GradeOutcome(
                name, "judge" if name == "semantic_review" else "code",
                Verdict.PASS if passed else Verdict.FAIL, f"{case_id}: {reason}"))
        rows.append({"case_id": case_id, "request_id": report["request_id"],
                     "exact_prompt": exact_prompt, "observed_input_transform": "none" if exact_prompt else "single separator LF removed by HTML input" if input_matches else "unrecognized input difference",
                     "report_sha256": hashlib.sha256(raw).hexdigest(),
                     "semantic_review": judgment, "review_binding": review_bound,
                     "expected": case["expected"], "duration_sec": report["acceptance_to_persistence_sec"],
                     "model_responses": completion.get("model_responses"),
                     "token_usage": completion.get("token_usage"), "durable_status": report["status"]})
    return {"reviewer": reviews["reviewer"], "scope": "Seven exploratory supplied-snapshot cases, not general diagnostic accuracy or live cluster recovery",
            "scoring": "src.agents.ai.eval_harness.Scorecard; semantic rows are supplied coding-assistant judgments",
            "scorecard": scorecard.to_dict(), "cases": rows}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = review_ui(args.directory)
    with args.output.open("x") as output:
        output.write(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(result["scorecard"], ensure_ascii=False))
