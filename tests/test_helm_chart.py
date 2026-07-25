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


def _webhook_env(docs: list[dict]) -> dict[str, dict]:
    (webhook,) = [d for d in docs if d["kind"] == "Deployment"]
    return {e["name"]: e for e in webhook["spec"]["template"]["spec"]["containers"][0]["env"]}


def test_state_store_absent_by_default():
    assert "PLATFORM_STATE_DSN" not in _webhook_env(_render())  # JSONL mode


def test_state_store_dsn_and_secret_modes():
    # dev/kind: plain DSN value
    env = _webhook_env(_render("--set", "stateStore.dsn=postgresql://u:p@h/db"))
    assert env["PLATFORM_STATE_DSN"]["value"] == "postgresql://u:p@h/db"

    # production: secretKeyRef wins over any plain DSN
    env = _webhook_env(
        _render(
            "--set", "stateStore.dsn=postgresql://ignored",
            "--set", "stateStore.existingSecret=pa-state-dsn",
        )
    )
    ref = env["PLATFORM_STATE_DSN"]["valueFrom"]["secretKeyRef"]
    assert ref == {"name": "pa-state-dsn", "key": "dsn"}
    assert "value" not in env["PLATFORM_STATE_DSN"]


def test_dsn_mode_without_pvc_rolls_and_scales():
    docs = _render(
        "--set", "persistence.enabled=false",
        "--set", "stateStore.existingSecret=pa-state-dsn",
        "--set", "webhook.replicas=2",
    )
    assert not any(d["kind"] == "PersistentVolumeClaim" for d in docs)
    (webhook,) = [d for d in docs if d["kind"] == "Deployment"]
    assert webhook["spec"]["replicas"] == 2  # multi-replica unlocked by the store
    assert webhook["spec"]["strategy"]["type"] == "RollingUpdate"
    assert "volumes" not in webhook["spec"]["template"]["spec"]


# --- Analyzer model backend -------------------------------------------------
#
# `llm.endpoint` was declared in values.yaml from the start, but only the router
# (off by default) consumed it. The webhook — which runs the incident analyzer
# AND the canary release gate — never received it, so it silently ran the
# heuristic fallback: confidence 0.0, every judgement `unknown`. A release gate
# that can only ever say "unknown" can only ever block.


def test_webhook_receives_the_analyzer_model_backend():
    env = _webhook_env(_render("-f", str(CHART / "values-kind.yaml")))
    assert env["ANALYZER_LLM_ENDPOINT"]["value"] == "http://host.docker.internal:18091/v1"
    assert "ANALYZER_LLM_MODEL" in env, "endpoint without model would use the wrong default"


def test_no_endpoint_means_no_env_not_an_empty_one():
    """An empty ANALYZER_LLM_ENDPOINT is truthy-ish config that points nowhere."""
    env = _webhook_env(_render("--set", "llm.endpoint="))
    assert "ANALYZER_LLM_ENDPOINT" not in env


# --- ⑦ TTL sweeper CronJob --------------------------------------------------
#
# The contract: report-only, off by default, and never able to claim a green it
# did not earn.


def test_sweeper_is_off_by_default():
    assert "CronJob" not in _kinds(_render())


def test_sweeper_renders_report_only():
    docs = _render("--set", "orphanSweeper.enabled=true")
    (cron,) = [d for d in docs if d["kind"] == "CronJob"]
    container = cron["spec"]["jobTemplate"]["spec"]["template"]["spec"]["containers"][0]
    flat = " ".join(container["command"] + [str(a) for a in container.get("args", [])])
    assert "sweep_orphan_clusters.py" in flat
    assert "--delete" not in flat, "destructive actions are approval-gated (D5)"


def test_sweeper_does_not_retry_itself_into_silence():
    """Forbid overlap and keep failed history: a red run must stay visible."""
    docs = _render("--set", "orphanSweeper.enabled=true")
    (cron,) = [d for d in docs if d["kind"] == "CronJob"]
    assert cron["spec"]["concurrencyPolicy"] == "Forbid"
    assert cron["spec"]["failedJobsHistoryLimit"] >= 1
    assert cron["spec"]["jobTemplate"]["spec"]["template"]["spec"]["restartPolicy"] == "Never"


def test_sweeper_provider_scope_is_passed_through():
    docs = _render(
        "--set", "orphanSweeper.enabled=true",
        "--set", "orphanSweeper.providers={gcp}",
        "--set", "orphanSweeper.protect={keep-me}",
    )
    (cron,) = [d for d in docs if d["kind"] == "CronJob"]
    args = [str(a) for a in cron["spec"]["jobTemplate"]["spec"]["template"]["spec"]["containers"][0]["args"]]
    assert args.count("--provider") == 1 and "gcp" in args
    assert "--protect" in args and "keep-me" in args


# --- ⑥ Pod Security Standards `restricted` ----------------------------------
#
# The namespace label is Phase 2's (Capsule owns those namespaces). This is the
# half that has to be true BEFORE the label exists, because the alternative is
# discovering the gap when a rollout starts getting rejected.


def _pod_specs(docs: list[dict]) -> dict[str, dict]:
    specs = {}
    for d in docs:
        if d["kind"] in ("Deployment", "Job"):
            specs[d["metadata"]["name"]] = d["spec"]["template"]["spec"]
        elif d["kind"] == "CronJob":
            specs[d["metadata"]["name"]] = d["spec"]["jobTemplate"]["spec"]["template"]["spec"]
    return specs


def test_every_workload_satisfies_restricted():
    """One uncovered pod is enough to make the namespace label reject the release."""
    docs = _render("--set", "router.enabled=true", "--set", "orphanSweeper.enabled=true")
    specs = _pod_specs(docs)
    assert len(specs) == 3, f"expected webhook+router+sweeper, got {sorted(specs)}"
    for name, spec in specs.items():
        pod_sc = spec.get("securityContext", {})
        assert pod_sc.get("runAsNonRoot") is True, name
        assert pod_sc.get("seccompProfile", {}).get("type") == "RuntimeDefault", name
        for container in spec["containers"]:
            sc = container.get("securityContext", {})
            assert sc.get("allowPrivilegeEscalation") is False, name
            assert sc.get("capabilities", {}).get("drop") == ["ALL"], name


def test_fsgroup_matches_the_image_uid_or_the_pvc_becomes_unwritable():
    docs = _render()
    spec = next(iter(_pod_specs(docs).values()))
    sc = spec["securityContext"]
    dockerfile = (
        CHART.parents[1] / "onprem" / "Dockerfile"
    ).read_text(encoding="utf-8")
    assert f"USER {sc['runAsUser']}:{sc['runAsGroup']}" in dockerfile, (
        "chart UID and image USER must agree — a mismatch only shows up at runtime"
    )
    assert sc["fsGroup"] == sc["runAsUser"], "JSONL PVC must stay writable by the runtime user"


def test_security_context_is_on_by_default():
    """Off is not a neutral default here; it is the state that breaks later."""
    spec = next(iter(_pod_specs(_render()).values()))
    assert spec.get("securityContext", {}).get("runAsNonRoot") is True


# --- Cosign: what the signature actually covers -----------------------------
#
# Live finding that drove this: a cosign signature binds to a DIGEST. Two tags
# on one digest both verify (the second was never signed by name), and moving a
# tag to a different image fails with "no signatures found". Verifying a tag and
# then deploying that tag is therefore not the same guarantee as deploying what
# was verified.


def _images(docs: list[dict]) -> list[str]:
    return [
        c["image"]
        for spec in _pod_specs(docs).values()
        for c in spec["containers"]
    ]


def test_tag_is_the_default_reference():
    assert all(img.endswith(":0.1.0") for img in _images(_render()))


def test_digest_pin_wins_over_tag():
    digest = "sha256:7cfc8a4dafa6b7d35d8d515edb52a73c06efa42f9c5b1a35b28d1409a7b4a476"
    images = _images(_render("--set", f"image.digest={digest}", "--set", "router.enabled=true"))
    assert images, "expected at least one workload"
    for img in images:
        assert img.endswith("@" + digest), img
        assert ":0.1.0" not in img, "a digest-pinned ref must not also carry the mutable tag"
