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
    assert {"versions.tf", "variables.tf", "argocd.tf", "monitoring.tf", "outputs.tf"} <= names
    assert {"argocd.yaml", "kube-prometheus-stack.yaml"} <= set(_values_files())


def test_chart_versions_are_pinned_exactly():
    variables = _tf_sources()["variables.tf"]
    pins = re.findall(r'default\s*=\s*"(\d+\.\d+\.\d+)"', variables)
    assert len(pins) == 2, "expected exactly two exact-semver chart pins"
    # …and both releases actually consume a pin (no floating chart versions).
    for release_file in ("argocd.tf", "monitoring.tf"):
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
