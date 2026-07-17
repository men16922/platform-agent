"""Live execution of the ⑦ model/parameter sweep against a local MLX endpoint.

Drives the SHIPPED code paths with a real model call — no stubs:
  - src.agents.ai.model_sweep.live_router_factory  (real chat completion per case)
  - src.agents.ai.model_sweep.run_sweep            (resumable via the points file)

Local MLX serves one model at a time, so run once per model and the points file
merges the results (resume dedup by config key):

  python scripts/live_model_sweep.py --model mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit
  # restart mlx_lm.server with the 7B, then:
  python scripts/live_model_sweep.py --model mlx-community/Qwen2.5-Coder-7B-Instruct-4bit

Cost is $0 (local inference), so the scoreboard ranks by seconds_per_success.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from urllib import request

from src.agents.ai.model_sweep import (
    SweepConfig,
    SweepPoint,
    _parse_role,
    grid,
    run_sweep,
    scoreboard,
)

ENDPOINT = os.getenv("ONPREM_LLM_ENDPOINT", "http://127.0.0.1:18090/v1").rstrip("/")
# effort axis → sampling temperature (the knob this backend actually has)
EFFORT_TEMPERATURE = {"low": 0.0, "high": 1.0}


def available_models(endpoint: str) -> set[str]:
    # mlx_lm.server lists every locally cached model here and loads the one named
    # in each request's ``model`` field on demand — this is availability, not
    # "currently served". call_model() double-checks the response echoes the
    # requested model.
    with request.urlopen(f"{endpoint}/models", timeout=5) as resp:
        data = json.load(resp)
    return {m["id"] for m in data["data"]}


def make_call_model(endpoint: str, stats: dict[str, int]):
    def call_model(config: SweepConfig, prompt: str) -> str:
        body = {
            "model": config.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 16,
            "temperature": EFFORT_TEMPERATURE[config.effort],
        }
        req = request.Request(
            f"{endpoint}/chat/completions",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
        )
        with request.urlopen(req, timeout=120) as resp:
            data = json.load(resp)
        if data.get("model") != config.model:
            # live_router_factory swallows exceptions into the deterministic
            # backstop, so count the mismatch too — main() refuses to persist a
            # run whose scores could be backstop-contaminated.
            stats["mismatch"] += 1
            raise RuntimeError(f"asked for {config.model}, server answered with {data.get('model')}")
        reply = data["choices"][0]["message"]["content"]
        stats["calls"] += 1
        if _parse_role(reply) is None:
            stats["unparsed"] += 1
        return reply

    return call_model


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="model id the server must be serving")
    ap.add_argument("--endpoint", default=ENDPOINT)
    ap.add_argument("--points", default="docs/evidence/model-sweep-live-points.jsonl")
    ap.add_argument("--trials", type=int, default=1)
    args = ap.parse_args()

    cached = available_models(args.endpoint)
    if args.model not in cached:
        raise SystemExit(f"'{args.model}' not in the endpoint's model list: {sorted(cached)}")

    points_path = Path(args.points)
    done: list[SweepPoint] = []
    if points_path.exists():
        done = [
            SweepPoint.from_dict(json.loads(line))
            for line in points_path.read_text().splitlines()
            if line.strip()
        ]

    configs = grid([args.model], effort=tuple(EFFORT_TEMPERATURE))
    stats = {"calls": 0, "unparsed": 0, "mismatch": 0}
    from src.agents.ai.model_sweep import live_router_factory

    points = run_sweep(
        configs,
        live_router_factory(make_call_model(args.endpoint, stats)),
        cost_per_call=lambda _cfg: 0.0,  # local inference — no spend
        trials=args.trials,
        done=done,
    )

    if stats["mismatch"]:
        raise SystemExit(
            f"{stats['mismatch']} call(s) answered by the wrong model — scores would be "
            "backstop-contaminated; nothing persisted"
        )

    points_path.parent.mkdir(parents=True, exist_ok=True)
    points_path.write_text("".join(json.dumps(p.to_dict()) + "\n" for p in points))

    print(f"live calls this run: {stats['calls']}  (unparsed replies → backstop: {stats['unparsed']})")
    print(f"\nscoreboard (by seconds_per_success) → {points_path}")
    for row in scoreboard(points, by="seconds_per_success"):
        c = row["config"]
        print(
            f"  {c['model'].split('/')[-1]:<38} effort={c['effort']:<6} "
            f"pass={row['pass_rate']:.2f} ({row['successes']}/{row['total']}) "
            f"sec/success={row['seconds_per_success']:.2f} total={row['seconds']:.1f}s"
        )


if __name__ == "__main__":
    main()
