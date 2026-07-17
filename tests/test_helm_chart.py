"""Guards for the reference #7 Helm chart (infra/helm/platform-agent).

These render the chart with the real ``helm`` binary and pin its safety
posture — the same guardrails the codebase enforces elsewhere:

  - default install is webhook-only, executor log-only, and CANNOT touch nodes
  - RBAC enumerates verbs/resources per action; a ``"*"`` anywhere is a failure
    (IAM least-privilege parity)
  - readiness probes the strict circuit-breaker endpoint, liveness the lenient one
  - the JSONL store stays single-writer (replicas 1, Recreate)

Skipped when helm is not installed (CI without helm still runs the rest).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

CHART = Path(__file__).resolve().parents[1] / "infra" / "helm" / "platform-agent"

pytestmark = pytest.mark.skipif(shutil.which("helm") is None, reason="helm not installed")


def _render(*args: str) -> list[dict]:
    out = subprocess.run(
        ["helm", "template", "pa", str(CHART), *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [doc for doc in yaml.safe_load_all(out) if doc]


def _kinds(docs: list[dict]) -> set[str]:
    return {d["kind"] for d in docs}


def test_helm_lint_passes():
    proc = subprocess.run(["helm", "lint", str(CHART)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_default_install_is_webhook_only_and_cannot_touch_nodes():
    docs = _render()
    kinds = _kinds(docs)
    assert "Deployment" in kinds and "Role" in kinds
    # router is opt-in; drain rights are opt-in — neither renders by default
    names = [d["metadata"]["name"] for d in docs]
    assert not any("router" in n for n in names)
    assert "ClusterRole" not in kinds and "ClusterRoleBinding" not in kinds

    (webhook,) = [d for d in docs if d["kind"] == "Deployment"]
    container = webhook["spec"]["template"]["spec"]["containers"][0]
    env = {e["name"]: e.get("value") for e in container["env"]}
    assert env["ONPREM_EXECUTOR_LIVE"] == "false"  # log-only until armed


def test_rbac_never_uses_wildcards_even_fully_armed():
    docs = _render(
        "--set", "webhook.executorLive=true",
        "--set", "webhook.rbac.allowDrain=true",
        "--set", "router.enabled=true",
    )
    for doc in docs:
        if doc["kind"] in ("Role", "ClusterRole"):
            for rule in doc["rules"]:
                for field in ("apiGroups", "resources", "verbs"):
                    assert "*" not in rule.get(field, []), (doc["metadata"]["name"], rule)


def test_drain_clusterrole_grants_exactly_the_polite_drain_surface():
    docs = _render("--set", "webhook.rbac.allowDrain=true")
    (cr,) = [d for d in docs if d["kind"] == "ClusterRole"]
    grants = {
        (group, resource): sorted(rule["verbs"])
        for rule in cr["rules"]
        for group in rule["apiGroups"]
        for resource in rule["resources"]
    }
    assert grants[("", "nodes")] == ["get", "list", "patch"]  # cordon, not delete
    assert grants[("", "pods/eviction")] == ["create"]  # eviction API honors PDBs
    assert ("", "pods") in grants and "delete" not in grants[("", "pods")]


def test_probes_split_lenient_liveness_from_strict_readiness():
    docs = _render()
    (webhook,) = [d for d in docs if d["kind"] == "Deployment"]
    container = webhook["spec"]["template"]["spec"]["containers"][0]
    assert container["livenessProbe"]["httpGet"]["path"] == "/health"
    assert container["readinessProbe"]["httpGet"]["path"] == "/health/ready"


def test_store_stays_single_writer():
    docs = _render("--set", "router.enabled=true")
    for dep in [d for d in docs if d["kind"] == "Deployment"]:
        assert dep["spec"]["replicas"] == 1, dep["metadata"]["name"]
        assert dep["spec"]["strategy"]["type"] == "Recreate", dep["metadata"]["name"]
