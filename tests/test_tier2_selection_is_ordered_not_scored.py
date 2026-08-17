"""
Tier 2 on GCP/Azure is decided by catalog order. AWS scores. Asked with the input
the platform actually produces.

`NEXT_PLAN` carried this as capability 스캔 ⓒ — *"티어 2는 첫 매치가 이긴다(AWS는
점수제) — 테스트가 고정했으니 우연이 아니라 결정이다"*. Measured 2026-08-17: the
first half is exactly right and **the second half was not true of the production
path**.

`test_capability_catalog_scan.py::test_recommended_capabilities_select_the_matching
_runbook` pins one runbook per case by feeding capability sets that only one
catalog entry declares (`["rollback_release"]` → health-check-failure,
`["drain_node"]` → network-latency-high). **No signal adapter ever emits those
sets.** For `kubernetes-workload` all four emit some superset of
``restart_workload``/``scale_out``, which overlaps **three** catalog entries at
once — so the case that decides production was never asked, and first-match and a
hypothetical scored implementation agree on every case that was. Risk 12⑤: 기본값과
같은 값을 고른 픽스처는 가드가 아니다.

What the three candidates differ by is what the operator is shown:

    eks-pod-oom            rto_sec 180
    health-check-failure   rto_sec 240
    network-latency-high   rto_sec 180

Measured with the real recommendation set, on `kubernetes-workload`:

    incident kind    AWS                          GCP / Azure
    OOM              eks-pod-oom          (180)   eks-pod-oom  (180)
    health check     health-check-failure (240)   eks-pod-oom  (180)
    latency          network-latency-high (180)   eks-pod-oom  (180)

AWS separates them on namespace (+2) and keywords (+1), and `catalog.py` documents
that tuning — `health-check-failure` deliberately omits `AWS/EKS` so an OOM alarm
cannot be stolen from `eks-pod-oom`. GCP and Azure have no scoring at all, so every
Kubernetes workload incident reports `eks-pod-oom` and its RTO, whatever it was.

⚠️ **These tests pin the measured status quo; they do not bless it.** Whether
GCP/Azure should disambiguate — `gcp._capabilities` already receives `signal_type`,
which is the obvious handle — is a design decision recorded as open in `NEXT_PLAN`.
Pinning it is the point: `NEXT_PLAN` claimed a test made this a decision rather than
an accident, and until now nothing did.
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
from src.agents.runbooks.catalog import BUILTIN_RUNBOOKS
from src.agents.runbooks.schema import fits_resource

RESOURCE_TYPE = "kubernetes-workload"

#: Read from the adapters rather than written out, so the guard's input moves when
#: production's does. A hand-picked set is what made the existing guard miss this.
GCP_RECOMMENDED = gcp_signals._capabilities(RESOURCE_TYPE, "reliability")
AZURE_RECOMMENDED = azure_signals._capabilities(RESOURCE_TYPE)


def _analyzer(provider: str, capabilities: list[str], namespace: str, metric: str, root_cause: str):
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
                recommended_capabilities=capabilities,
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
    """The premise. If it overlapped one, order could not decide anything."""
    candidates = [
        rb_id
        for rb_id, rb in BUILTIN_RUNBOOKS.items()
        if fits_resource(rb, RESOURCE_TYPE)
        and set(rb.get("capabilities", ())) & set(GCP_RECOMMENDED)
    ]
    assert len(candidates) > 1, (
        f"only {candidates} overlap the set the GCP adapter emits "
        f"({GCP_RECOMMENDED}); this whole file is about the ambiguity, so the "
        "premise has changed and the docstring needs re-measuring"
    )
    assert set(GCP_RECOMMENDED) == set(AZURE_RECOMMENDED), (
        "GCP and Azure no longer recommend the same set for a Kubernetes "
        f"workload ({GCP_RECOMMENDED} vs {AZURE_RECOMMENDED}) — the cases below "
        "assume one input for both"
    )


@pytest.mark.parametrize("provider", ["gcp", "azure"])
@pytest.mark.parametrize(
    "kind,namespace,metric,root_cause",
    [
        ("oom", "kubernetes.io/container", "memory/used_bytes", "container OOMKilled"),
        ("health-check", "kubernetes.io/container", "probe_failures", "readiness probe failing"),
        ("latency", "kubernetes.io/container", "request_latencies", "p99 latency up"),
    ],
)
def test_capability_overlap_returns_the_first_entry_whatever_the_incident_is(
    provider, kind, namespace, metric, root_cause
):
    """One answer for three different incidents, because order is the only input.

    Not a bug being asserted as correct — the actions come from the recommendations
    and are the same either way. What differs is the `runbook_id` and `rto_sec`
    reported to the operator: a readiness-probe failure is reported as an OOM
    runbook with a 180s RTO instead of health-check-failure's 240s.
    """
    recommended = GCP_RECOMMENDED if provider == "gcp" else AZURE_RECOMMENDED
    runbook_id, rto = _select(
        provider, _analyzer(provider, recommended, namespace, metric, root_cause)
    )
    assert (runbook_id, rto) == ("eks-pod-oom", 180), (
        f"{provider} returned {runbook_id!r}/{rto} for a {kind} incident. If this "
        "changed on purpose — GCP/Azure gaining a scored or signal_type-aware "
        "match — update this file and `NEXT_PLAN`'s ⓒ together; the point of the "
        "guard is that the answer is a decision, not catalog order by accident."
    )


@pytest.mark.parametrize(
    "kind,namespace,metric,root_cause,expected",
    [
        ("oom", "AWS/EKS", "pod_restart", "container OOMKilled", "eks-pod-oom"),
        (
            "health-check",
            "AWS/ApplicationELB",
            "UnHealthyHostCount",
            "readiness probe failing",
            "health-check-failure",
        ),
        (
            "latency",
            "AWS/NetworkELB",
            "TargetResponseTime",
            "p99 latency up",
            "network-latency-high",
        ),
    ],
)
def test_aws_separates_the_same_three_because_it_scores(
    kind, namespace, metric, root_cause, expected
):
    """The other side of the asymmetry, asked with the same recommendation set.

    Without this the file would read as "tier 2 cannot tell these apart", when in
    fact one provider can and two cannot — which is the repo's standard for a real
    gap rather than a quirk (`NEXT_PLAN` 유지 규약: 읽는 쪽의 provider 간 비대칭).
    """
    alarm_analyzer = _analyzer("aws", GCP_RECOMMENDED, namespace, metric, root_cause)
    runbook_id, _rto = _select("aws", alarm_analyzer)
    assert runbook_id == expected, (
        f"AWS returned {runbook_id!r} for a {kind} alarm; its namespace/keyword "
        "scoring is what distinguishes these three, and `catalog.py` documents the "
        "tuning that makes it work"
    )


@pytest.mark.parametrize("provider", ["gcp", "azure"])
def test_a_runbook_inserted_before_the_others_steals_every_selection(provider):
    """`catalog.py`'s "appending cannot change a selection" is AWS-scoped.

    That comment justifies itself with AWS's score-tie rule
    (`_match_runbook_registry` keeps the first entry on a tie). On GCP/Azure there
    is no score, so order decides outright: a new entry placed *before* the others
    with any overlapping capability takes every Kubernetes workload selection, RTO
    included. Nothing enforces append-only, so this test is the enforcement — and
    it is why the comment now says which provider the property holds for.
    """
    module = importlib.import_module(f"src.agents.operations.{provider}.decision")
    recommended = GCP_RECOMMENDED if provider == "gcp" else AZURE_RECOMMENDED
    thief = {
        "runbook_id": "thief",
        "namespaces": ["Nothing/Matches"],
        "keywords": ["nothing-matches"],
        "capabilities": ["restart_workload"],
        "actions": ["GCP-RolloutRestartGKEWorkload"],
        "resource_types": [RESOURCE_TYPE],
        "rto_sec": 9999,
    }
    analyzer = _analyzer(provider, recommended, "kubernetes.io/container", "m", "rc")

    with mock.patch.object(module, "BUILTIN_RUNBOOKS", {"thief": thief, **BUILTIN_RUNBOOKS}):
        first_id, first_rto = _select(provider, analyzer)
    with mock.patch.object(module, "BUILTIN_RUNBOOKS", {**BUILTIN_RUNBOOKS, "thief": thief}):
        appended_id, _ = _select(provider, analyzer)

    assert (first_id, first_rto) == ("thief", 9999), (
        f"{provider}: inserting before the catalog no longer steals the selection "
        "— if scoring was added, this file's premise changed"
    )
    assert appended_id == "eks-pod-oom", (
        f"{provider}: appending changed the selection to {appended_id!r}. The "
        "catalog convention is that appending is safe; on this provider that "
        "holds only because order is the whole algorithm."
    )
