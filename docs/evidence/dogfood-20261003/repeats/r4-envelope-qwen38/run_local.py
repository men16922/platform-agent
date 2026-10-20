"""Bounded local Qwen experiment. No operational tools or external model endpoint."""
import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import time

from pydantic_ai import Agent, ModelRetry, PromptedOutput, RunContext, capture_run_messages
from pydantic_ai.messages import ModelMessagesTypeAdapter
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import UsageLimits
from contract import Diagnosis, PROMPT, SnapshotQuestion, prepare, validate_citations

MODEL = "mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit"


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("cases", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("--model", choices=[MODEL, "mlx-community/Qwen3.8-27B-4bit"], default=MODEL)
    args = parser.parse_args()
    cases = json.loads(args.cases.read_text())
    args.out.mkdir(exist_ok=False)
    model = OpenAIChatModel(args.model, provider=OpenAIProvider(base_url="http://127.0.0.1:18091/v1", api_key="mlx-local"))
    agent = Agent(model, output_type=PromptedOutput(Diagnosis), deps_type=dict, system_prompt=PROMPT, retries=1)

    @agent.output_validator
    def cited(ctx: RunContext[dict], result: Diagnosis):
        try:
            validate_citations(result, ctx.deps)
        except ValueError as exc:
            raise ModelRetry(str(exc)) from exc
        return result

    manifest = {
        "at": datetime.now(timezone.utc).isoformat(), "model": args.model,
        "pydantic_ai_distributions": {
            name: importlib.metadata.version(name)
            for name in importlib.metadata.packages_distributions().get("pydantic_ai", [])
        },
        "operational_tools": 0, "request_limit": 2, "timeout_per_case_seconds": 60,
        "files": {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in (args.cases, Path(__file__), Path(__file__).with_name("contract.py"))},
        "interpretation": "Prototype only; citation/metadata validity does not prove semantic correctness.",
    }
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    for path in (args.cases, Path(__file__), Path(__file__).with_name("contract.py")):
        (args.out / path.name).write_bytes(path.read_bytes())
    for case in cases:
        q = SnapshotQuestion.model_validate(case["input"])
        prepared = prepare(q)
        report = {"case_id": case["id"], "request": q.model_dump(mode="json"), "prepared": prepared,
                  "started_at": datetime.now(timezone.utc).isoformat(), "operational_tools": 0}
        start = time.monotonic()
        with capture_run_messages() as messages:
            if not prepared["sources"]:
                report.update(status="insufficient_applicable_evidence", model_requests=0,
                              recovery="not_established", explanation="No source applies to the declared target and time window. Obtain matching observations; excluded records remain in the report.")
            else:
                try:
                    result = await asyncio.wait_for(agent.run(json.dumps(prepared), deps=prepared,
                                                   usage_limits=UsageLimits(request_limit=2)), timeout=60)
                    report.update(status="schema_citations_valid", output=result.output.model_dump())
                except Exception as exc:
                    report.update(status="failed", error_type=type(exc).__name__, error=str(exc))
        report["elapsed_sec"] = round(time.monotonic() - start, 3)
        report["messages"] = json.loads(ModelMessagesTypeAdapter.dump_json(messages))
        report["model_requests"] = sum(m["kind"] == "response" for m in report["messages"])
        (args.out / (case["id"] + ".json")).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
        print(json.dumps({k: v for k, v in report.items() if k in ("case_id", "status", "output", "elapsed_sec", "error")}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
