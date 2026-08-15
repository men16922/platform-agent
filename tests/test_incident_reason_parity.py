"""
`reason` is the words downstream keyword matching reads — and it must not depend
on which entry point handled the incident.

Why this file exists (2026-08-15). `_incident_reason` was written provider-neutral:
its docstring names GCP's `policy_name`/`condition_name` and Azure's `alert_rule`,
and every signal adapter writes exactly those keys. But only `aws/detector.py`
called it. So the repo already had the right answer for GCP and Azure — in one
path:

    GCP alert -> aws.detector.lambda_handler   -> _synthetic_alarm -> _incident_reason  (rich)
    GCP alert -> gcp.detector.cloud_function_handler -> _build_alarm_context            (thin)

The same incident got two different `reason` values depending on deployment path.
The thin one dropped the rule name, which matters because consumers score keywords
over this string: AWS runbook selection (`aws/decision.py`) and — the sharp edge —
the GCP/Azure `_fallback_analysis`, which grades severity by looking for
"outage"/"crash"/"down". A policy an operator named "checkout service outage" was
graded **P3** (human approval required) instead of **P1** (auto-execute).

These guards ask the question of *every* sibling, because the last four defects in
this repo were all "the guard walked a proper subset" (M17-M20).
"""

from __future__ import annotations

import dataclasses

import pytest

from src.agents.adapters.base import incident_reason
from src.agents.adapters.signals.azure import AzureMonitorSignalAdapter
from src.agents.adapters.signals.gcp import GcpMonitoringSignalAdapter
from src.agents.models import DetectorOutput, Severity
from src.agents.operations.aws.detector import _synthetic_alarm
from src.agents.operations.azure.analyzer import _fallback_analysis as azure_fallback
from src.agents.operations.azure.detector import _build_alarm_context as azure_alarm
from src.agents.operations.gcp.analyzer import _fallback_analysis as gcp_fallback
from src.agents.operations.gcp.detector import _build_alarm_context as gcp_alarm


def _gcp_event(policy: str, condition: str, summary: str) -> dict:
    return {
        "incident": {
            "policy_name": policy,
            "condition_name": condition,
            "summary": summary,
            "state": "open",
            "started_at": "2026-08-15T00:00:00Z",
            "incident_id": "i1",
            "scoping_project_id": "p1",
            "url": "https://example/incident",
            "resource": {"type": "gce_instance", "labels": {"instance_id": "checkout-1"}},
            "metric": {"type": "custom.googleapis.com/probe/status"},
        }
    }


def _azure_event(rule: str, description: str) -> dict:
    return {
        "data": {
            "essentials": {
                "alertRule": rule,
                "description": description,
                "monitorCondition": "Fired",
                "firedDateTime": "2026-08-15T00:00:00Z",
                "alertId": "a1",
                "targetResourceType": "VirtualMachines",
                "alertTargetIDs": ["/vm-1"],
                "signalType": "Metric",
            },
            "alertContext": {
                "condition": {
                    "allOf": [
                        {
                            "metricName": "ProbeStatus",
                            "dimensions": [{"name": "vm", "value": "checkout-1"}],
                        }
                    ]
                }
            },
        }
    }


def _gcp_pair(policy="checkout service outage", condition="probe failing", summary="Threshold exceeded"):
    """(normalized, alarm-from-native-path) for GCP."""
    event = _gcp_event(policy, condition, summary)
    normalized = GcpMonitoringSignalAdapter().normalise(event)
    return normalized, gcp_alarm(event["incident"], normalized)


def _azure_pair(rule="checkout service outage", description="Threshold exceeded"):
    """(normalized, alarm-from-native-path) for Azure."""
    event = _azure_event(rule, description)
    normalized = AzureMonitorSignalAdapter().normalise(event)
    return normalized, azure_alarm(event["data"]["essentials"], normalized, event)


PROVIDERS = ("gcp", "azure")
_PAIR = {"gcp": _gcp_pair, "azure": _azure_pair}
_FALLBACK = {"gcp": gcp_fallback, "azure": azure_fallback}


class TestEntryPointParity:
    """The same incident must get the same `reason` whichever handler saw it."""

    @pytest.mark.parametrize("provider", PROVIDERS)
    def test_native_handler_agrees_with_the_aws_unified_path(self, provider):
        normalized, native = _PAIR[provider]()
        unified = _synthetic_alarm(normalized, provider)
        assert native.reason == unified.reason, (
            f"{provider}: native detector and the AWS unified path disagree — "
            f"native={native.reason!r} unified={unified.reason!r}"
        )

    @pytest.mark.parametrize("provider", PROVIDERS)
    def test_operator_rule_name_reaches_reason(self, provider):
        _, alarm = _PAIR[provider]()
        assert "outage" in alarm.reason.lower(), (
            f"{provider}: the word the operator named the rule with never reached "
            f"`reason` — got {alarm.reason!r}"
        )

    def test_gcp_also_carries_the_condition_name(self):
        """GCP names a rule across two fields; both are the operator's words."""
        _, alarm = _gcp_pair()
        assert "probe failing" in alarm.reason


class TestReasonReachesTheGrader:
    """The consumer, not the shape — `reason` decides AUTO vs human approval."""

    @pytest.mark.parametrize("provider", PROVIDERS)
    def test_rule_name_alone_can_raise_severity(self, provider):
        """Operator writes the symptom in the rule name; the summary is neutral."""
        normalized, alarm = _PAIR[provider]()
        _, severity, _ = _FALLBACK[provider](
            DetectorOutput(alarm=alarm, normalized_incident=normalized)
        )
        assert severity is Severity.P1, (
            f"{provider}: a rule named 'outage' graded {severity.value}, not P1"
        )

    @pytest.mark.parametrize("provider", PROVIDERS)
    def test_dropping_the_rule_name_downgrades_two_levels(self, provider):
        """The defect, pinned: this is what the thin `reason` used to produce."""
        normalized, alarm = _PAIR[provider]()
        description_only = dataclasses.replace(alarm, reason="Threshold exceeded")
        _, severity, _ = _FALLBACK[provider](
            DetectorOutput(alarm=description_only, normalized_incident=normalized)
        )
        assert severity is Severity.P3


class TestReasonContract:
    """Reverse directions — the enrichment must not invent or erase."""

    def test_description_still_reaches_reason(self):
        """Enriching must not replace what was already there."""
        _, alarm = _gcp_pair(summary="Disk usage is high")
        assert "Disk usage is high" in alarm.reason

    @pytest.mark.parametrize("provider", PROVIDERS)
    def test_no_rule_name_falls_back_to_signal_type(self, provider):
        """An adapter carrying none of the keys must not hand matching "" ."""
        normalized, _ = _PAIR[provider]()
        bare = dataclasses.replace(normalized, source_metadata={}, observations={})
        assert incident_reason(bare) == bare.signal_type
        assert incident_reason(bare) != ""

    def test_rule_name_is_not_duplicated_when_condition_repeats_it(self):
        """Empty parts are dropped rather than producing double spaces."""
        _, alarm = _gcp_pair(condition="")
        assert "  " not in alarm.reason


class TestSingleCopy:
    """M19's rule: a shared *contract* lives in one module, not one copy per provider.

    Two copies is the shape where the next fix reaches only one of them — which is
    exactly how this defect survived: `aws/detector.py` held the only copy and the
    other two providers grew their own thinner inline version.
    """

    def test_only_the_contract_module_defines_the_keys(self):
        import pathlib

        root = pathlib.Path(__file__).resolve().parents[1] / "src"
        definers = [
            path.relative_to(root).as_posix()
            for path in root.rglob("*.py")
            if "_RULE_NAME_KEYS = (" in path.read_text(encoding="utf-8")
        ]
        assert definers == ["agents/adapters/base.py"], definers

    @pytest.mark.parametrize("module", [
        "src.agents.operations.aws.detector",
        "src.agents.operations.gcp.detector",
        "src.agents.operations.azure.detector",
    ])
    def test_every_detector_reads_the_contract(self, module):
        """The import line is the scope — prose claiming neutrality is not."""
        import importlib

        assert hasattr(importlib.import_module(module), "incident_reason")
