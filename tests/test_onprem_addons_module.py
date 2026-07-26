"""Guards for the on-prem add-on stack root (infra/onprem/addons).

Mirrors the aws-production guard pattern: static checks always run;
``terraform validate`` only when the binary is present and the root is
init-ed. The two contracts this module advertises are (a) chart versions are
pinned exactly so applies are reproducible, and (b) the low-footprint values
keep every CPU request small enough for the local Docker VM budget.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

MODULE = Path(__file__).resolve().parents[1] / "infra" / "onprem" / "addons"

# The local budget contract: no single component may request more CPU than
# this (millicores). JOURNEY ch6.2 taught us the stack only fits when requests
# are trimmed; the guard keeps future values edits honest.
MAX_CPU_REQUEST_MILLI = 50


def _tf_sources() -> dict[str, str]:
    return {p.name: p.read_text(encoding="utf-8") for p in MODULE.glob("*.tf")}


def _values_files() -> dict[str, dict]:
    return {
        p.name: yaml.safe_load(p.read_text(encoding="utf-8"))
        for p in (MODULE / "values").glob("*.yaml")
    }


def test_module_ships_the_advertised_pieces():
    names = set(_tf_sources())
    assert {
        "versions.tf", "variables.tf", "argocd.tf", "monitoring.tf",
        "gitops.tf", "rollouts.tf", "logging.tf", "tracing.tf", "tenancy.tf", "outputs.tf",
    } <= names
    assert {
        "argocd.yaml", "kube-prometheus-stack.yaml", "argo-rollouts.yaml",
        "loki.yaml", "fluent-bit.yaml", "tempo.yaml", "capsule.yaml",
    } <= set(_values_files())


def test_chart_versions_are_pinned_exactly():
    variables = _tf_sources()["variables.tf"]
    pins = re.findall(r'default\s*=\s*"(\d+\.\d+\.\d+)"', variables)
    assert len(pins) == 7, (
        "expected exactly seven exact-semver chart pins "
        "(argocd, kps, rollouts, loki, fluent-bit, tempo, capsule)"
    )
    # …and every remote release actually consumes a pin (no floating chart versions).
    for release_file in ("argocd.tf", "monitoring.tf", "rollouts.tf", "logging.tf", "tracing.tf",
                         "tenancy.tf"):
        assert "version" in _tf_sources()[release_file]


def _iter_cpu_requests(node, path=""):
    if isinstance(node, dict):
        requests = node.get("resources", {}).get("requests", {}) if isinstance(node.get("resources"), dict) else {}
        if "cpu" in requests:
            yield path, str(requests["cpu"])
        for key, child in node.items():
            yield from _iter_cpu_requests(child, f"{path}.{key}" if path else key)


def test_values_honour_the_low_footprint_cpu_contract():
    for name, values in _values_files().items():
        cpu_requests = list(_iter_cpu_requests(values))
        assert cpu_requests, f"{name}: expected explicit CPU requests"
        for path, cpu in cpu_requests:
            assert cpu.endswith("m"), f"{name}:{path}: CPU request must be in millicores, got {cpu}"
            assert int(cpu[:-1]) <= MAX_CPU_REQUEST_MILLI, (
                f"{name}:{path}: {cpu} exceeds the {MAX_CPU_REQUEST_MILLI}m local budget contract"
            )


def test_unreachable_control_plane_scrapes_are_disabled():
    kps = _values_files()["kube-prometheus-stack.yaml"]
    for component in ("kubeEtcd", "kubeScheduler", "kubeControllerManager", "kubeProxy"):
        assert kps[component]["enabled"] is False, f"{component} scrape must stay off on kind/k3s"


def test_alertmanager_routes_into_the_platform_agent_loop():
    kps = _values_files()["kube-prometheus-stack.yaml"]
    config = kps["alertmanager"]["config"]
    assert config["route"]["receiver"] == "platform-agent"
    urls = [
        hook["url"]
        for receiver in config["receivers"]
        if receiver["name"] == "platform-agent"
        for hook in receiver["webhook_configs"]
    ]
    # The URL is a templatefile var so monitoring.tf owns the actual endpoint.
    assert urls == ["${webhook_url}"]
    # The always-firing Watchdog heartbeat must not reach the incident loop.
    assert any(
        route.get("receiver") == "null" and any("Watchdog" in m for m in route.get("matchers", []))
        for route in config["route"]["routes"]
    )


def test_demo_crashloop_rule_is_present_and_fast():
    kps = _values_files()["kube-prometheus-stack.yaml"]
    groups = kps["additionalPrometheusRulesMap"]["platform-agent-demo"]["groups"]
    rules = [r for g in groups for r in g["rules"]]
    (rule,) = [r for r in rules if r["alert"] == "PlatformDemoCrashLoop"]
    assert "kube_pod_container_status_restarts_total" in rule["expr"]
    assert rule["for"] == "1m"  # demo latency contract — not the stock 15m


# --- Phase 3: GitOps -------------------------------------------------------

APP_CHART = MODULE / "charts" / "platform-agent-app"


def test_gitops_application_chart_is_shipped():
    assert (APP_CHART / "Chart.yaml").is_file()
    assert (APP_CHART / "templates" / "application.yaml").is_file()


def test_gitops_release_is_ordered_after_argocd():
    # The Application CRD is installed by the argo-cd release, so the wrapper
    # release must depend_on it — otherwise apply races the CRD registration.
    gitops = _tf_sources()["gitops.tf"]
    assert "helm_release.argocd" in gitops, "gitops release must depend_on the argo-cd release"
    assert "charts/platform-agent-app" in gitops


def test_gitops_application_targets_repo_and_self_heals():
    manifest = (APP_CHART / "templates" / "application.yaml").read_text(encoding="utf-8")
    assert "kind: Application" in manifest
    # Source is git-driven (values-injected repo/path/revision, not hard-coded).
    for field in (".Values.repoURL", ".Values.targetRevision", ".Values.chartPath", ".Values.valuesFile"):
        assert field in manifest, f"Application source must be driven by {field}"
    # The drift-restore demo relies on both automation switches being on.
    for policy in ("selfHeal: true", "prune: true"):
        assert policy in manifest, f"syncPolicy must set {policy}"


def test_gitops_repo_url_default_is_a_git_remote():
    variables = _tf_sources()["variables.tf"]
    (repo_url,) = re.findall(r'gitops_repo_url"\s*\{[^}]*?default\s*=\s*"([^"]+)"', variables, re.DOTALL)
    assert repo_url.endswith(".git"), "gitops_repo_url must point at a git remote"


# --- Phase 4: progressive delivery (Argo Rollouts) -------------------------

ROLLOUTS_DEMO = MODULE / "charts" / "rollouts-demo"


def test_rollouts_demo_chart_is_shipped():
    assert (ROLLOUTS_DEMO / "Chart.yaml").is_file()
    assert (ROLLOUTS_DEMO / "templates" / "rollout.yaml").is_file()
    assert "helm_release.argo_rollouts" in _tf_sources()["rollouts.tf"], (
        "the demo release must depend_on the rollouts controller (Rollout CRD ordering)"
    )


def test_rollouts_demo_is_a_canary_with_a_manual_gate():
    manifest = (ROLLOUTS_DEMO / "templates" / "rollout.yaml").read_text(encoding="utf-8")
    assert "kind: Rollout" in manifest
    assert "canary:" in manifest and "setWeight:" in manifest, "must use a weighted canary strategy"
    # An indefinite `pause: {}` is the promote/abort gate the live demo drives.
    assert "pause: {}" in manifest, "canary must pause indefinitely for a manual promote/abort gate"


# --- Metric-based canary judgment (AnalysisTemplate + Prometheus) -----------
#
# Contract: the analysis is ADDITIVE to the manual gate above (D19 keeps the
# runner and Rollouts in separate layers; Phase 4's live evidence rests on the
# manual path), and it is OFF until a live run verifies it.


def _demo_chart_values() -> dict:
    return yaml.safe_load((ROLLOUTS_DEMO / "values.yaml").read_text(encoding="utf-8"))


def test_analysis_template_is_shipped():
    assert (ROLLOUTS_DEMO / "templates" / "analysis.yaml").is_file()
    analysis = (ROLLOUTS_DEMO / "templates" / "analysis.yaml").read_text(encoding="utf-8")
    assert "kind: AnalysisTemplate" in analysis
    assert "prometheus:" in analysis, "stage 1 judgment must use the Prometheus provider"


def test_analysis_defaults_off_so_the_verified_demo_is_unchanged():
    """Auto-abort is unverified live; shipping it on by default would risk the demo."""
    assert _demo_chart_values()["analysis"]["enabled"] is False


def test_analysis_is_additive_not_a_replacement_of_the_manual_gate():
    manifest = (ROLLOUTS_DEMO / "templates" / "rollout.yaml").read_text(encoding="utf-8")
    # Background analysis lives under canary alongside steps, and the indefinite
    # pause must survive — replacing it would regress the promote/abort demo.
    assert "analysis:" in manifest
    assert "pause: {}" in manifest
    assert "podTemplateHashValue: Latest" in manifest, (
        "canary-hash must come from the Rollout so only canary pods are scored"
    )


def test_analysis_query_scopes_to_canary_pods_only():
    analysis = (ROLLOUTS_DEMO / "templates" / "analysis.yaml").read_text(encoding="utf-8")
    # The hash arg is what separates canary from stable; without it the query
    # would score stable pods too and could never fail a bad canary.
    assert "{{args.canary-hash}}" in analysis
    assert "{{args.namespace}}" in analysis
    assert "kube_pod_container_status_restarts_total" in analysis, (
        "restart count comes from kube-state-metrics (ships with kps) — no app instrumentation"
    )


def test_analysis_treats_no_data_as_passing_not_error():
    analysis = (ROLLOUTS_DEMO / "templates" / "analysis.yaml").read_text(encoding="utf-8")
    assert "or vector(0)" in analysis, (
        "an empty Prometheus result scores as Error in Rollouts — must fall back to 0"
    )


def test_analysis_prometheus_address_is_values_driven():
    """kps names the Service from its own helpers, so a mismatch must be a values fix."""
    analysis = (ROLLOUTS_DEMO / "templates" / "analysis.yaml").read_text(encoding="utf-8")
    assert ".Values.analysis.prometheusAddress" in analysis
    address = _demo_chart_values()["analysis"]["prometheusAddress"]
    assert address.startswith("http://") and ":9090" in address


def test_analysis_tolerates_a_single_scrape_blip():
    values = _demo_chart_values()["analysis"]
    assert values["failureLimit"] >= 1, "one bad measurement must not abort a healthy canary"
    assert values["initialDelay"], "first measurement must be delayed past normal container start"


# --- Phase 5: logging (Loki + Fluent Bit) ----------------------------------


def test_loki_is_single_binary_and_caches_are_off():
    loki = _values_files()["loki.yaml"]
    assert loki["deploymentMode"] == "SingleBinary"
    # Scalable targets off — SingleBinary owns everything on the local budget.
    for target in ("backend", "read", "write"):
        assert loki[target]["replicas"] == 0, f"{target} must be scaled to 0 in SingleBinary mode"
    # memcached caches default to multi-Gi requests — the local footprint trap.
    assert loki["chunksCache"]["enabled"] is False
    assert loki["resultsCache"]["enabled"] is False


def test_fluent_bit_ships_to_the_loki_gateway():
    outputs = _values_files()["fluent-bit.yaml"]["config"]["outputs"]
    assert "Name loki" in outputs, "fluent-bit must have a loki output"
    assert "loki-gateway.monitoring.svc" in outputs, "must target the in-cluster Loki gateway"


def test_grafana_registers_loki_as_a_datasource():
    kps = _values_files()["kube-prometheus-stack.yaml"]
    sources = kps["grafana"]["additionalDataSources"]
    (loki_ds,) = [d for d in sources if d["type"] == "loki"]
    assert "loki-gateway.monitoring.svc" in loki_ds["url"]


@pytest.mark.skipif(
    shutil.which("terraform") is None or not (MODULE / ".terraform").exists(),
    reason="terraform not installed or module not initialised",
)
def test_terraform_validate_passes():
    proc = subprocess.run(
        ["terraform", "validate", "-no-color"],
        cwd=MODULE,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


# --- Phase 6: tracing (Tempo) ----------------------------------------------
#
# What is traced is the agent's own 4-step pipeline, so the contract here is the
# ingest/query port pair — both were wrong on the first attempt and only
# `helm template` caught it.


def test_tempo_ingests_otlp_grpc_only():
    tempo = _values_files()["tempo.yaml"]["tempo"]
    protocols = tempo["receivers"]["otlp"]["protocols"]
    assert "grpc" in protocols and protocols["grpc"]["endpoint"].endswith(":4317")
    # Jaeger/Zipkin/OpenCensus stay out of the *config* (the chart's Service
    # publishes those legacy ports regardless — config-level narrowing only).
    assert set(tempo["receivers"]) == {"otlp"}


def test_tempo_resources_are_nested_under_the_tempo_key():
    """A top-level `resources:` is silently dropped by this chart (renders {})."""
    values = _values_files()["tempo.yaml"]
    assert "resources" not in values, "top-level resources is ignored — must be tempo.resources"
    assert values["tempo"]["resources"]["requests"]["cpu"].endswith("m")


def test_tempo_storage_is_local_and_bounded():
    tempo = _values_files()["tempo.yaml"]["tempo"]
    assert tempo["storage"]["trace"]["backend"] == "local"
    assert tempo["retention"], "traces are the most voluminous signal — retention must be bounded"
    assert _values_files()["tempo.yaml"]["persistence"]["enabled"] is False


def test_grafana_registers_tempo_on_the_query_port_not_the_ingest_port():
    kps = _values_files()["kube-prometheus-stack.yaml"]
    (tempo_ds,) = [d for d in kps["grafana"]["additionalDataSources"] if d["type"] == "tempo"]
    # 3200 = Tempo 2.x http_listen_port. 3100 is the pre-2.x default and is NOT
    # exposed by this chart's Service; 4317 is OTLP ingest.
    assert tempo_ds["url"].endswith(":3200"), "must point at the query API port"
    assert "4317" not in tempo_ds["url"] and "3100" not in tempo_ds["url"]


def test_grafana_has_all_three_signals():
    kps = _values_files()["kube-prometheus-stack.yaml"]
    types = {d["type"] for d in kps["grafana"]["additionalDataSources"]}
    # Prometheus is the chart's own default datasource; Loki + Tempo are ours.
    assert {"loki", "tempo"} <= types, "metrics + logs + traces must share one Grafana"


# --- Soft-tier data-plane isolation (NetworkPolicy) -------------------------
#
# These policies used to live in a `tenancy-netpol` Helm chart here. It was retired
# in favour of registry-driven rendering (src/agents/platform/tenancy.py) because
# the chart carried its own hand-maintained tenant/env/capability lists whose
# cartesian product (16 namespaces) did not match the registry's actual
# subscriptions (6) — and no `helm_release` ever installed it, so the isolation it
# described applied to nothing. The guards below pin both halves of that lesson so
# the chart cannot quietly come back.
#
# Behavioural guards for the renderer live in tests/test_tenancy.py.

NETPOL_CHART = MODULE / "charts" / "tenancy-netpol"


def test_retired_netpol_chart_is_gone():
    """A chart nothing installs is not a security control, whatever it renders."""
    assert not NETPOL_CHART.exists(), (
        "tenancy-netpol was retired: NetworkPolicies are rendered from the registry "
        "by src/agents/platform/tenancy.py so the policy set equals the namespace set "
        "by construction"
    )


def test_every_shipped_chart_has_an_installer():
    """The gap that made the retired chart dead code, generalised.

    A chart in this module with no `helm_release` referencing it is inert: it looks
    like shipped capability in a review and does nothing on a cluster.
    """
    sources = "\n".join(_tf_sources().values())
    for chart in (MODULE / "charts").iterdir():
        if not chart.is_dir():
            continue
        assert chart.name in sources, (
            f"chart {chart.name} is not referenced by any Terraform resource — "
            "nothing installs it"
        )


# --- Phase 2: Capsule (soft isolation tier) --------------------------------


def test_capsule_is_off_by_default():
    """It installs webhooks intercepting every namespace create on the cluster."""
    variables = _tf_sources()["variables.tf"]
    block = variables.split('variable "capsule_enabled"')[1].split("}")[0]
    assert "default = false" in block


def test_capsule_chart_version_is_pinned():
    variables = _tf_sources()["variables.tf"]
    assert 'default = "0.13.10"' in variables.split('variable "capsule_chart_version"')[1]


def test_capsule_protects_the_platforms_own_namespaces():
    """Without this the tenancy operator can arbitrate argocd/monitoring/default —
    a tenancy layer turning into a cluster-wide outage."""
    values = _values_files()["capsule.yaml"]
    pattern = values["manager"]["options"]["protectedNamespaceRegex"]
    for namespace in ("kube-system", "argocd", "monitoring", "default"):
        assert namespace.split("-")[0] in pattern, f"{namespace} must be protected"


def test_capsule_does_not_require_cert_manager():
    """The chart defaults to cert-manager, which would be a hidden prerequisite."""
    values = _values_files()["capsule.yaml"]
    assert values["certManager"]["generateCertificates"] is False
    assert values["tls"]["create"] is True
    # Without the controller the cert exists but nothing injects the CA bundle,
    # and every namespace create fails.
    assert values["tls"]["enableController"] is True


def test_capsule_registers_an_administrator_for_the_iac_flow():
    """Capsule refuses to adopt an admin-created namespace unless the applying
    identity is a declared administrator — verified live by the refusal
    ("namespace can not be patched into a tenant")."""
    values = _values_files()["capsule.yaml"]
    assert values["manager"]["options"]["administrators"], (
        "an IaC flow applies as an admin identity, not as each tenant"
    )
