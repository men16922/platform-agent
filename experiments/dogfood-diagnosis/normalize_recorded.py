"""Replay the saved D Kubernetes observations without inventing missing history.

Run from repository root with PYTHONPATH=.; output must be a new directory.
The failure UI timestamp is NOT a timestamp for the raw Kubernetes acquisition.
Saved D files lack ReplicaSet snapshots, so they cannot prove the ownership chain.
"""
import argparse
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path

from src.agents.ai.deployment_evidence import digest, summarize_deployment


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    args.out.mkdir(exist_ok=False)
    manifest = json.loads((args.evidence / "final-candidate-verification.json").read_text())
    for label in ["v4-failure1", "v4-recovery1"]:
        dp = args.evidence / (label + "-deployment.json")
        pp = args.evidence / (label + "-pods.json")
        deployment, pod_file = json.loads(dp.read_text()), json.loads(pp.read_text())
        pods = pod_file if isinstance(pod_file, list) else pod_file["items"]
        if "failure" in label:
            when = next(r["failure_observed_at"] for r in manifest["runs"] if r["label"] == label)
            acquisition = None  # Only UI failure observation time was recorded.
            time_basis = "UI failure time is the question time; raw acquisition time unknown"
        else:
            observation = json.loads((args.evidence / (label + "-observation.json")).read_text())
            when = acquisition = observation["healthy_observed_at"]
            time_basis = "Recorded acquisition batch completion; individual fetch times not recorded"
        as_of = datetime.fromisoformat(when)
        sources = [{"source_id": "deployment", "sha256": digest(deployment), "observed_at": acquisition},
                   {"source_id": "pods-no-replicaset-snapshot", "sha256": digest(pods), "observed_at": acquisition}]
        result = summarize_deployment(deployment, pods, context="kind-platform-agent",
            namespace="acme-dev-observability", name="orders-api-dogfood", sources=sources,
            as_of=as_of, window_start=as_of - timedelta(minutes=2))
        result["replay"] = {"time_basis": time_basis, "live_observation": False,
            "files": {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in [dp, pp]},
            "missing": "ReplicaSet ownership/template snapshots were not recorded in D; no historical RS is invented from current state.",
            "health_logs": "Separate app access-log evidence is retained in D; text logs do not grant eligibility in this contract."}
        (args.out / (label + ".json")).write_text(json.dumps(result, indent=2) + "\n")
        print(label, result["revision"], result["rollout_complete"], result["recovery"]["status"])


if __name__ == "__main__":
    main()
