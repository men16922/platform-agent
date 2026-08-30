"""
The two values that decide what Phase 4a costs must not drift on a comment alone.

`docs/plans/2026-08-15-4a-remote-write-allowlist.md` names them: **the allowlist
and the scrape interval**. Everything else about 4a is opinion; these two are
arithmetic, and the arithmetic has a 325× range:

    four metrics @ 60s (this file's contract)   15.8 M samples/mo    39.5% of free tier
    all of kube-state-metrics                    ~4,188 series → 181 M/mo    452%
    no filter at all                            5,131 M samples/mo      12,828%

⚠️ **Measured 2026-08-30: the bill is $0.00, and that does not weaken this file.**
AMP's free tier is `Always Free` — 40 M ingested samples per month — which the
plan's §3 had reasoned its way *out of* on a premise that turned out false
(it assumed a 12-month window). So the cliff moved: it is no longer the $0.90/10M
rate, it is the **40 M limit**, and the percentages above are the real reading of
the table. The contract's 15.8 M sits at 39.5%; no filter overruns it by **128×**
and pays list price from there (≈$180/mo). Authority: the plan's **§10** and
`docs/evidence/amp-actual-bill-is-zero-and-the-free-tier-reason-was-inverted.log`.

"AMP is free anyway" is therefore the one wrong summary of that measurement.
Widening the regex past this list does not make 4a more expensive — it **erases
the reason 4a was chosen over 4b**, and now it is also the only thing standing
between $0 and a real bill.

This repository has already been wrong here, by 100×: three entry-point documents
copied "≈$5/월" from a plan whose series count was never measured, and the number
survived all the way to an approval before anyone counted the cluster (52,438
series, `docs/evidence/4a-cost-assumed-a-hundredth-of-the-cluster.log`). The
values file now carries the correct numbers **in comments**. Comments do not fail
a gate.

⚠️ Deliberately not a cost calculation. A test that recomputed the bill would be
asserting its own arithmetic, and the arithmetic is not what drifts — the *list*
drifts, one metric at a time, each addition individually reasonable. So this pins
identity: exactly these four names, `action: keep`, exactly one destination, and
the interval that the plan's §8 chose after measuring where the series come from.
Adding a fifth metric is allowed — it just has to be a decision someone makes on
purpose, with this file and the plan updated together.
"""

from __future__ import annotations

import pathlib

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
VALUES = ROOT / "infra/onprem/addons/values/kube-prometheus-stack.yaml"

# The allowlist approved 2026-08-16 and measured live 2026-08-17: 308 of the
# cluster's 52,438 series (0.59%). Counts are from AMP itself, not from intent.
APPROVED_METRICS = frozenset({
    "kube_pod_container_status_restarts_total",   # the demo alarm rule reads this
    "kube_pod_status_phase",                      # what state the pod is in
    "kube_deployment_status_replicas_unavailable",  # did it reach availability
    "up",                                         # proof the pipe is alive
})

# 287 of the 308 come from this one ServiceMonitor, which is why the interval
# lives here rather than on `prometheusSpec.scrapeInterval`: raising it globally
# would also halve the resolution of metrics the allowlist never ships.
KSM_INTERVAL = "60s"


def _values() -> dict:
    return yaml.safe_load(VALUES.read_text(encoding="utf-8"))


def _remote_writes() -> list[dict]:
    spec = _values().get("prometheus", {}).get("prometheusSpec", {})
    return spec.get("remoteWrite") or []


def test_there_is_exactly_one_destination():
    """Two writers double the bill, and the second is easy to add without noticing."""
    targets = _remote_writes()
    assert len(targets) == 1, [t.get("url") for t in targets]


def test_the_destination_is_the_approved_workspace():
    url = _remote_writes()[0]["url"]
    assert "aps-workspaces" in url and "/api/v1/remote_write" in url, url
    assert "ws-929b8da9-b0db-49f8-aadb-2ed1a70f699f" in url, (
        "remote_write points at a different AMP workspace than the one 4a "
        f"provisioned and priced: {url}"
    )


def _keep_rule() -> dict:
    rules = _remote_writes()[0].get("writeRelabelConfigs") or []
    keeps = [r for r in rules if r.get("action") == "keep"]
    assert len(keeps) == 1, (
        f"expected exactly one `keep` rule, found {len(keeps)}. With no `keep` at "
        "all Prometheus ships **everything** — 5.13B samples/mo, 128× the 40 M "
        "free tier, ≥$180."
    )
    return keeps[0]


def test_the_filter_keeps_rather_than_drops():
    """`action: drop` with this regex is the exact inversion: it would ship the
    52,130 series this list exists to exclude and drop the four it wants."""
    rule = _keep_rule()
    assert rule["sourceLabels"] == ["__name__"], rule


def test_the_allowlist_is_exactly_the_approved_four():
    regex = _keep_rule()["regex"]
    declared = set(regex.split("|"))
    assert declared == set(APPROVED_METRICS), {
        "extra": sorted(declared - APPROVED_METRICS),
        "missing": sorted(APPROVED_METRICS - declared),
        "why": (
            "each addition looks small and the bill is not linear in obviousness: "
            "all of kube-state-metrics is 4,188 series → 181 M samples/mo, which is "
            "4.5\u00d7 the 40 M free tier and the point where this pipe starts "
            "charging at all (~$12.7/mo of overage; $16.3 gross). Update the plan's "
            "\u00a72 and \u00a74 in the same commit."
        ),
    }


def test_the_regex_has_no_wildcard():
    """Prometheus anchors the regex, so `kube_.*` is not a typo that fails loudly —
    it is a working expression that quietly matches thousands of series."""
    regex = _keep_rule()["regex"]
    for metachar in (".*", ".+", "[", "?", "(?"):
        assert metachar not in regex, (
            f"the allowlist regex contains {metachar!r}: {regex}. A pattern instead "
            "of a list means nobody can read the bill off this file."
        )


def test_the_scrape_interval_is_pinned_where_the_series_are():
    monitor = _values().get("kube-state-metrics", {}).get("prometheus", {}).get("monitor", {})
    assert monitor.get("interval") == KSM_INTERVAL, (
        f"kube-state-metrics ServiceMonitor interval is {monitor.get('interval')!r}, "
        f"not {KSM_INTERVAL!r}. 287 of the 308 shipped series are scraped here, so "
        "this value is the other half of the volume: at 30s the same allowlist "
        "ships 28.2 M samples/mo instead of 15.8 M — still under the 40 M free "
        "tier, but it spends 70% of the headroom the next metric will want."
    )


def test_the_global_scrape_interval_is_not_used_as_the_cost_handle():
    """The rejected alternative, pinned so it stays rejected on purpose.

    Setting `prometheusSpec.scrapeInterval: 60s` would also reach 13.3 M/mo — and
    would halve the resolution of every metric in the cluster, including the
    52,130 series that cost nothing because they are never shipped. Interval is a
    volume handle here, not an observability decision.
    """
    spec = _values().get("prometheus", {}).get("prometheusSpec", {})
    assert "scrapeInterval" not in spec, (
        "a global scrapeInterval appeared. If that is intentional, say so in the "
        "plan's §8 table and delete this test — but do not reach for it as the "
        "cheap way to cut the AMP bill."
    )


@pytest.mark.parametrize("credential_field", ["accessKey", "secretKey"])
def test_credentials_are_referenced_not_embedded(credential_field):
    """The IAM user behind this pipe can only `aps:RemoteWrite` to one workspace,
    but a key pasted into a values file is a key in git forever."""
    sigv4 = _remote_writes()[0].get("sigv4") or {}
    ref = sigv4.get(credential_field)
    assert isinstance(ref, dict) and "name" in ref and "key" in ref, (
        f"sigv4.{credential_field} must reference a Secret by name, got {ref!r}"
    )
