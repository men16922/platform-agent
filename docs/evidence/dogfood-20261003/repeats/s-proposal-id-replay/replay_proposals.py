"""One fixed local-model pass; recorded/synthetic inputs only, no cluster access."""
import argparse
import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

import httpx
from openai import AsyncOpenAI

from proposal_contract import PROMPT, Proposal, prepare, render, state_report, validate
from src.agents.ai.deployment_evidence import digest, pod_waiting_observations, summarize_deployment
from tests.test_deployment_evidence import NOW, snapshot


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def cases(root):
    base = root / "docs/evidence/dogfood-20261003/repeats"
    original = json.loads((base / "r-pod-diagnostics-replay/cases.json").read_text())
    rows = [deepcopy(c) for c in original]
    for row in rows:
        row.pop("instruction", None)
        row["provenance"] = "unchanged R frozen tool_result"
    contradictory = rows[-1]
    contradictory["id"] = "contradictory-availability"
    contradictory["expected"] = "Notice aggregate available/ready=1 versus both ReplicaSets/Pods unavailable; request reconciliation. No recovery or established cause."
    consistent = deepcopy(contradictory)
    consistent["id"] = "both-revisions-failing-consistent"
    consistent["provenance"] = "New internally consistent synthetic raw fixture; not a live acquisition. Original contradictory R case retained separately."
    d, objects = snapshot()
    d["status"].update(readyReplicas=0, availableReplicas=0)
    for index in (2, 3):
        objects[index]["status"]["containerStatuses"][0].update(ready=False, restartCount=2, lastState={"terminated": {"exitCode": 1}})
        objects[index]["status"]["containerStatuses"][0]["state"] = {"waiting": {"reason": "CrashLoopBackOff",
            "message": "Application startup failed after a connection timeout to the shared dependency. No dependency or network trace is supplied."}}
        objects[index]["status"]["conditions"] = [{"type": "Ready", "status": "False"}]
    objects[1]["status"]["availableReplicas"] = 0
    facts = summarize_deployment(d, objects, context="recorded-local-context", namespace="acme", name="orders",
        sources=[{"source_id": "deployment", "sha256": digest(d), "observed_at": NOW.isoformat()},
                 {"source_id": "replicasets-pods", "sha256": digest(objects), "observed_at": NOW.isoformat()}],
        as_of=NOW, window_start=NOW)
    consistent["raw_synthetic_fixture"] = {"deployment": d, "objects": objects}
    consistent["tool_result"] = {"ok": True, "evidence": facts, "diagnostic_observations": pod_waiting_observations(facts, objects)}
    consistent["expected"] = "Dependency/network possibilities with supporting timeout quote; no healthy prior/candidate/approved action or proven cause. Previous-attempt logs may be useful."
    rows.append(consistent)
    folder = base / "q-revision-window/restored"
    dep = json.loads((folder / "deployment-before.json").read_text())
    related = json.loads((folder / "replicasets-pods.json").read_text())
    manifest = json.loads((folder / "manifest.json").read_text())
    d, objects = json.loads(dep["stdout"]), json.loads(related["stdout"])["items"]
    facts = summarize_deployment(d, objects, context="recorded-local-context",
        namespace=d["metadata"]["namespace"], name=d["metadata"]["name"],
        sources=[{"source_id": "deployment", "sha256": digest(d), "observed_at": dep["completed_at"]},
                 {"source_id": "replicasets-pods", "sha256": digest(objects), "observed_at": related["completed_at"]}],
        as_of=datetime.fromisoformat(manifest["at"]), window_start=datetime.fromisoformat(manifest["window_start"]))
    rows.append({"id": "recorded-restored", "provenance": "Q restored recorded Deployment/RS/Pods; no added health logs",
        "tool_result": {"ok": True, "evidence": facts, "diagnostic_observations": pod_waiting_observations(facts, objects)},
        "expected": "Current rollout complete but no readiness probe/external health evidence. Do not diagnose an ongoing current failure from previous revision waiting state. Select useful revision-specific health evidence."})
    return rows


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    args.output.mkdir(exist_ok=False)
    rows = cases(root)
    for row in rows:
        row["prepared"] = prepare(row["tool_result"])
        row["state"] = state_report(row["tool_result"])
    write(args.output / "cases.json", rows)
    files = [Path(__file__), Path(__file__).with_name("proposal_contract.py"),
             root / "src/agents/ai/inspection_report.py", root / "src/agents/ai/deployment_evidence.py",
             root / "tests/test_deployment_evidence.py"]
    manifest = {"at": datetime.now(timezone.utc).isoformat(), "model": "mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit",
        "max_tokens": 1024, "temperature": 0, "http_retries": 0, "http_timeout_seconds": 60,
        "scope": "Prototype output contract, one generation per frozen case, no tool registry or browser. No semantic accuracy implied by schema/citation success.",
        "cases_sha256": digest(rows), "files": {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
        "model_request": "Only prepared source data, choice descriptions and output schema; expectations and code state report excluded.",
        "prompt": PROMPT, "schema": Proposal.model_json_schema()}
    write(args.output / "manifest.json", manifest)
    for p in files:
        (args.output / p.name).write_bytes(p.read_bytes())
    if args.prepare_only:
        print(json.dumps({"prepared_cases": len(rows)}))
        return
    attempts = []
    async def requested(request):
        request.extensions["index"] = len(attempts)
        attempts.append({"at": datetime.now(timezone.utc).isoformat(), "status": None})
    async def responded(response):
        attempts[response.request.extensions["index"]]["status"] = response.status_code
    client = AsyncOpenAI(base_url="http://127.0.0.1:18091/v1", api_key="mlx-local", max_retries=0,
        http_client=httpx.AsyncClient(timeout=httpx.Timeout(60, connect=5), event_hooks={"request": [requested], "response": [responded]}))
    try:
        for row in rows:
            request = {"model": manifest["model"], "max_tokens": 1024, "temperature": 0,
                "messages": [{"role": "system", "content": PROMPT + "\nOutput schema:\n" + json.dumps(manifest["schema"])},
                             {"role": "user", "content": json.dumps(row["prepared"], ensure_ascii=False)}]}
            record = {"case_id": row["id"], "case_sha256": digest(row), "request": request,
                      "state": row["state"], "schema_citations": "not_validated", "semantic_review": "required"}
            first, started = len(attempts), time.monotonic()
            try:
                response = await client.chat.completions.create(**request)
                record["response"] = response.model_dump(mode="json")
                choice = response.choices[0]
                raw = choice.message.content or ""
                record["raw"] = raw
                if choice.finish_reason != "stop" or choice.message.tool_calls:
                    raise ValueError("Incomplete response or unrequested tool call")
                proposal = validate(raw, row["prepared"])
                record.update(schema_citations="valid", proposal=proposal.model_dump(), rendered=render(proposal, row["state"], row["prepared"]))
            except Exception as exc:
                record["error"] = {"type": type(exc).__name__, "message": str(exc)}
            record.update(elapsed_seconds=round(time.monotonic()-started, 3), http_attempts=attempts[first:])
            write(args.output / (row["id"] + ".json"), record)
            print(json.dumps({"case_id": row["id"], "seconds": record["elapsed_seconds"],
                "contract": record["schema_citations"], "error": record.get("error")}), flush=True)
            if "response" not in record:
                break
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
