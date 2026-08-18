"""
Tier 2 scores, and the three providers score the same. Asked with production input.

History, because the shape of the mistake is the point. `NEXT_PLAN` carried this as
capability 스캔 ⓒ — *"티어 2는 첫 매치가 이긴다(AWS는 점수제) — 테스트가 고정했으니
우연이 아니라 결정이다"*. Measured 2026-08-17: the first half was right and the
second was not true of the production path.

`test_capability_catalog_scan.py::test_recommended_capabilities_select_the_matching
_runbook` pins one runbook per case by feeding capability sets that only one catalog
entry declares (`["rollback_release"]` → health-check-failure, `["drain_node"]` →
network-latency-high). **No signal adapter emits those sets** — for
`kubernetes-workload` all four emit some superset of
``restart_workload``/``scale_out``, which overlaps **three** entries at once. So the
only cases exercised were the ones where first-match and scoring agree, which is
Risk 12⑤. Worse, `["rollback_release"]` is a set aws/gcp/azure do not recommend at
all (measured the same day), so that case was unreachable in production entirely.

Asked with the real set, GCP and Azure returned `eks-pod-oom` and its 180s RTO for
OOM, probe-failure and latency alike, while AWS separated all three. The keyword
vocabularies were already cloud-neutral by design — `catalog.py` says the stems are
chosen to appear "in kube-prometheus-stack names (KubePodNotReady) and in probe
failure text" — so what was missing was a reader, not data. Scoring moved to
`runbooks/schema.py::score_runbook` and all three providers now read it.

Measuring that exposed a second, worse thing in the same tier: it resolved its
**actions** from `recommended_capabilities` with no condition evaluation, while tier 1
of the same module evaluated them and excluded escalation steps. Same provider, two
entry points, opposite semantics (M21's shape). `scale_database_read` and
`rebalance_consumer` exist in the catalog *only* behind `previous_step_failed: true`
and are recommended for their resource types, so the escalation remedy was this
tier's first response. Tier 2 now reads the winner's steps, as AWS and tier 1 do.
Nothing in the suite went red when that behaviour changed — no test asserted this
tier's actions at all — which is what the last two tests here are for.
"""

from __future__ import annotations

import importlib
from unittest import mock

import pytest

from src.agents.adapters.signals import azure as azure_signals
from src.agents.adapters.signals import gcp as gcp_signals
from src.agents.models import (
    AlarmContext,
    AnalyzerOutput,
    DetectorOutput,
    NormalizedIncident,
    Severity,
)
from src.agents.adapters.registry import get_execution_adapter
from src.agents.runbooks.catalog import BUILTIN_RUNBOOKS, CAPABILITY_RUNBOOKS
from src.agents.runbooks.schema import fits_resource

RESOURCE_TYPE = "kubernetes-workload"
PROVIDERS = ("aws", "gcp", "azure")

#: Read from the adapter rather than written out, so the guard's input moves when
#: production's does. A hand-picked set is what let the older guard miss this.
RECOMMENDED = gcp_signals._capabilities(RESOURCE_TYPE, "reliability")

#: One incident, described the way each provider's monitoring describes it. The
#: namespaces differ on purpose: AWS catalog namespaces are `AWS/*` and score +2,
#: while a GCP/Azure incident scores on keywords alone — which is exactly the case
#: that used to have no answer.
CASES = [
    ("oom", "eks-pod-oom", 180, {
        "aws": ("AWS/EKS", "pod_restart"),
        "gcp": ("kubernetes.io/container", "memory/used_bytes"),
        "azure": ("AZURE/kubernetes-workload", "memory_working_set"),
    }, "container OOMKilled repeatedly"),
    ("health-check", "health-check-failure", 240, {
        "aws": ("AWS/ApplicationELB", "UnHealthyHostCount"),
        "gcp": ("kubernetes.io/container", "probe_failures"),
        "azure": ("AZURE/kubernetes-workload", "probe_failures"),
    }, "readiness probe failing"),
    ("latency", "network-latency-high", 180, {
        "aws": ("AWS/NetworkELB", "TargetResponseTime"),
        "gcp": ("kubernetes.io/container", "request_latencies"),
        "azure": ("AZURE/kubernetes-workload", "request_latency"),
    }, "p99 latency up"),
]


def _analyzer(provider: str, namespace: str, metric: str, root_cause: str):
    return AnalyzerOutput(
        detector=DetectorOutput(
            alarm=AlarmContext(
                alarm_name="tier2-alarm",
                alarm_arn="arn:...",
                state="ALARM",
                reason="threshold crossed",
                metric_name=metric,
                namespace=namespace,
            ),
            normalized_incident=NormalizedIncident(
                provider=provider,
                service="checkout",
                resource_type=RESOURCE_TYPE,
                resource_id="deploy/api",
                signal_type="reliability",
                recommended_capabilities=RECOMMENDED,
                source_metadata={"alarm_name": "tier2-alarm"},
            ),
        ),
        root_cause=root_cause,
        severity=Severity.P2,
        confidence=0.9,
    )


def _select(provider: str, analyzer):
    module = importlib.import_module(f"src.agents.operations.{provider}.decision")
    result = module._select_runbook(analyzer)
    # AWS returns a fourth element (the resolved steps); the other two do not.
    return result[0], result[2]


def test_the_real_recommendation_set_overlaps_more_than_one_runbook():
    """The premise. If it overlapped one, scoring would have nothing to decide."""
    candidates = [
        rb_id
        for rb_id, rb in BUILTIN_RUNBOOKS.items()
        if fits_resource(rb, RESOURCE_TYPE)
        and set(rb.get("capabilities", ())) & set(RECOMMENDED)
    ]
    assert len(candidates) > 1, (
        f"only {candidates} overlap the set the adapters emit ({RECOMMENDED}); the "
        "ambiguity this file is about is gone, so re-measure the docstring"
    )
    assert set(RECOMMENDED) == set(azure_signals._capabilities(RESOURCE_TYPE)), (
        "GCP and Azure no longer recommend the same set for a Kubernetes workload; "
        "the cases below assume one input for both"
    )


@pytest.mark.parametrize("provider", PROVIDERS)
@pytest.mark.parametrize(
    "kind,expected_id,expected_rto,namespaces,root_cause",
    CASES,
    ids=[c[0] for c in CASES],
)
def test_all_three_providers_pick_the_runbook_the_incident_describes(
    provider, kind, expected_id, expected_rto, namespaces, root_cause
):
    """The load-bearing case: same incident, same answer, on every provider.

    This is what first-match could not do. GCP and Azure reported `eks-pod-oom`
    (RTO 180) for a readiness-probe failure whose runbook declares 240, because
    order was the whole algorithm and the OOM entry comes first in the catalog.
    """
    namespace, metric = namespaces[provider]
    runbook_id, rto = _select(
        provider, _analyzer(provider, namespace, metric, root_cause)
    )
    assert (runbook_id, rto) == (expected_id, expected_rto), (
        f"{provider} returned {runbook_id!r}/{rto} for a {kind} incident, expected "
        f"{expected_id!r}/{expected_rto}. The three providers read one scoring "
        "function (`schema.score_runbook`); a difference here means one of them "
        "stopped."
    )


def _escalation_only_capabilities() -> set[str]:
    """Capabilities the catalog declares **only** behind a condition.

    Derived, not listed: a hand-maintained set is how the next runbook's
    escalation step gets missed. Currently `expand_storage`,
    `rebalance_consumer`, `rollback_release`, `scale_database_read`.
    """
    conditioned, unconditioned = set(), set()
    for raw in CAPABILITY_RUNBOOKS.values():
        for step in raw.get("steps") or []:
            target = conditioned if step.get("condition") else unconditioned
            target.add(step.get("capability"))
    return conditioned - unconditioned


@pytest.mark.parametrize("provider", ["gcp", "azure"])
@pytest.mark.parametrize(
    "resource_type,namespace,metric,root_cause",
    # ⚠️ No `kubernetes-workload` case: its only escalation-only capability is
    # `rollback_release`, which GCP and Azure do not recommend (the open policy gap
    # in `test_signal_capability_parity.py::JUSTIFIED_GAPS`). The anti-vacuous
    # assertion below caught that the case could not detect the defect — it would
    # have passed for the wrong reason. If that policy changes, add it back here.
    [
        ("database-instance", "cloudsql.googleapis.com", "cpu/utilization", "cpu saturated"),
        ("streaming-consumer", "pubsub.googleapis.com", "num_undelivered", "consumer lag growing"),
    ],
)
def test_tier2_never_emits_an_escalation_only_remediation_as_first_response(
    provider, resource_type, namespace, metric, root_cause
):
    """Nothing asserted tier 2's *actions* before this, which is how it got here.

    This tier resolved `recommended_capabilities` directly, with no condition
    evaluation, while tier 1 of the same module evaluated them and excluded
    escalation steps — same provider, two entry points, opposite semantics (M21's
    shape). Measured 2026-08-17: `scale_database_read` and `rebalance_consumer`
    exist in the catalog *only* behind `previous_step_failed: true` and are both
    recommended for their resource types, so the escalation remedy was the first
    thing this tier ran. AWS and on-prem never resolve actions from
    recommendations, which is why the same lists are harmless there.

    The fix made this tier read the winner's steps. This test is what makes that
    load-bearing: the whole suite stayed green when the behaviour changed.
    """
    module = importlib.import_module(f"src.agents.operations.{provider}.decision")
    signals = gcp_signals if provider == "gcp" else azure_signals
    recommended = (
        signals._capabilities(resource_type, "saturation")
        if provider == "gcp"
        else signals._capabilities(resource_type)
    )
    analyzer = AnalyzerOutput(
        detector=DetectorOutput(
            alarm=AlarmContext(
                alarm_name="tier2-actions",
                alarm_arn="arn:...",
                state="ALARM",
                reason="threshold crossed",
                metric_name=metric,
                namespace=namespace,
            ),
            normalized_incident=NormalizedIncident(
                provider=provider,
                service="checkout",
                resource_type=resource_type,
                resource_id="deploy/api",
                signal_type="saturation",
                recommended_capabilities=recommended,
                source_metadata={"alarm_name": "tier2-actions"},
            ),
        ),
        root_cause=root_cause,
        severity=Severity.P2,
        confidence=0.9,
    )
    runbook_id, actions, _rto = module._select_runbook(analyzer)

    adapter = get_execution_adapter(provider)
    forbidden = {
        adapter.resolve_action(cap, analyzer.detector.normalized_incident)["action"]
        for cap in _escalation_only_capabilities()
        if cap in recommended
    }
    assert forbidden, (
        f"{provider}/{resource_type}: no escalation-only capability is recommended "
        "here, so this case cannot detect the defect — re-measure the fixture"
    )
    assert not (set(actions) & forbidden), (
        f"{provider} chose {runbook_id!r} and emitted {sorted(set(actions) & forbidden)} "
        "as a first response. Those capabilities exist in the catalog only behind "
        "`previous_step_failed: true` — running them up front is applying the "
        "escalation remedy when nothing has failed."
    )
    assert actions, f"{provider}/{resource_type} produced no actions at all"


@pytest.mark.parametrize("provider", ["gcp", "azure"])
def test_scoring_makes_catalog_order_stop_mattering_for_a_scored_incident(provider):
    """Insertion used to steal every selection. Now it only steals unscored ones.

    `catalog.py` documents "append, never insert", and until scoring existed that
    convention was the *only* thing protecting GCP/Azure selections — a new entry
    placed first with any overlapping capability took them all, RTO included. With
    scoring, a decoy that matches no namespace and no keyword loses to a runbook the
    incident actually describes.

    The second half is the part that keeps the convention alive: when **nothing**
    scores, every candidate is 0 and the first entry still wins, so an inserted
    entry does take those. That is the same rule AWS has (a tie keeps the first
    entry), which is why the convention stays in `catalog.py`.
    """
    module = importlib.import_module(f"src.agents.operations.{provider}.decision")
    decoy = {
        "runbook_id": "decoy",
        "namespaces": ["Nothing/Matches"],
        "keywords": ["nothing-matches"],
        "capabilities": ["restart_workload"],
        "actions": ["GCP-RolloutRestartGKEWorkload"],
        "resource_types": [RESOURCE_TYPE],
        "rto_sec": 9999,
    }
    inserted_first = {"decoy": decoy, **BUILTIN_RUNBOOKS}

    scored = _analyzer(provider, "kubernetes.io/container", "probe_failures", "readiness probe failing")
    with mock.patch.object(module, "BUILTIN_RUNBOOKS", inserted_first):
        runbook_id, rto = _select(provider, scored)
    assert (runbook_id, rto) == ("health-check-failure", 240), (
        f"{provider}: a decoy inserted before the catalog took a scored incident "
        f"({runbook_id!r}/{rto}) — scoring is not deciding"
    )

    unscored = _analyzer(provider, "kubernetes.io/container", "no-keyword-here", "nothing familiar")
    with mock.patch.object(module, "BUILTIN_RUNBOOKS", inserted_first):
        first_id, _ = _select(provider, unscored)
    with mock.patch.object(module, "BUILTIN_RUNBOOKS", {**BUILTIN_RUNBOOKS, "decoy": decoy}):
        appended_id, _ = _select(provider, unscored)
    assert (first_id, appended_id) == ("decoy", "eks-pod-oom"), (
        f"{provider}: with nothing scoring, insertion order should still decide "
        f"(got {first_id!r} inserted-first, {appended_id!r} appended) — this is why "
        "`catalog.py` still says append, never insert"
    )
