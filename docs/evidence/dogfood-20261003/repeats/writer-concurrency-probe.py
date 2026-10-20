"""Reproduce only the existing synthetic loopback writer test; no GitHub calls.

Run from the repository root. Keeps its local attempt directories and refuses to
overwrite the named report. The wrappers observe/re-raise, never suppress errors.
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, Lock, get_ident
import argparse
import datetime as dt
import hashlib
import json
import os
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from tests.test_writer_workflow import lab, run
import src.agents.platform.writer_workflow as workflow

parser = argparse.ArgumentParser()
parser.add_argument("report", type=Path)
parser.add_argument("--trials", type=int, default=50)
args = parser.parse_args()
assert 1 <= args.trials <= 100
assert not args.report.exists(), "keep previous evidence"
captured = []
mutex = Lock()


def wrap(obj, name):
    original = getattr(obj, name)

    def call(*positional, **named):
        try:
            return original(*positional, **named)
        except Exception as exc:
            with mutex:
                captured.append({
                    "thread": get_ident(), "function": name,
                    "type": type(exc).__name__, "errno": getattr(exc, "errno", None),
                    "code": str(exc)[:160],
                })
            raise

    setattr(obj, name, call)


for obj, name in [(workflow, "_directory"), (workflow, "_write_new"),
                  (workflow, "_read"), (workflow.fcntl, "flock"),
                  (os, "mkdir"), (os, "open"), (os, "fsync")]:
    wrap(obj, name)

base = ROOT / "_workspace/dogfood-20261003"
root = Path(tempfile.mkdtemp(prefix="writer-concurrency-", dir=base))
trials = []
for trial in range(args.trials):
    fixture = lab.__wrapped__()
    state = next(fixture)
    directory = root / str(trial)
    directory.mkdir(mode=0o700)
    barrier = Barrier(8, timeout=5)
    captured.clear()

    def execute(_):
        barrier.wait()
        return {"thread": get_ident(), "result": run(directory, state)}

    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(execute, range(8)))
        passed = (
            sum(r["result"]["state"] == "CONSISTENT" for r in results) == 1
            and sum(r["result"]["state"] == "BLOCKED" for r in results) == 7
            and state.calls == list(workflow.STAGES) + ["revoke_token"]
            and len(list(directory.iterdir())) == 1
        )
        trials.append({"trial": trial, "passed": passed, "results": results,
                       "calls": state.calls.copy(), "exceptions": captured.copy()})
        if not passed:
            break
    finally:
        try:
            next(fixture)
        except StopIteration:
            pass

report = {
    "at": dt.datetime.now(dt.timezone.utc).isoformat(),
    "instrumentation": "Record and re-raise filesystem/flock exceptions; synthetic loopback HTTP fixture",
    "writer_workflow_sha256": hashlib.sha256((ROOT / "src/agents/platform/writer_workflow.py").read_bytes()).hexdigest(),
    "workspace": str(root), "trials": trials,
}
args.report.write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps({"trials": len(trials), "failed": sum(not x["passed"] for x in trials),
                  "missing_lock_open_observed": sum(e["function"] == "open" and e["errno"] == 2 and "workflow.lock" in e["code"] for t in trials for e in t["exceptions"])}))
sys.exit(0 if all(x["passed"] for x in trials) else 1)
