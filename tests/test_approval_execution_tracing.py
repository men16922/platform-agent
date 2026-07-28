"""
The executor stage produces a span on the paths a real alert actually takes.

`test_tracing.py` proved the four stage spans by calling
`run_incident_pipeline(execute=True)`. Nothing reaches the pipeline that way in
production: the webhook — the On-Prem PATH B entry point — calls it with
`execute=False` and executes afterwards, on **both** the AUTO path and the
approval path. Both of those executions happened after the pipeline's root span
had already closed, so the one stage that changes the cluster was the one stage
emitting no span on every real path. The existing tests could not see it because
they entered one layer below the gap.

So these enter at the webhook handler.

The approval case has a modelling decision worth pinning down: the execution
that resumes a parked remediation is a **new trace linked** to the incident, not
a child of it. The interval between them is a human deciding — folding that into
the incident's span tree would produce a span whose duration is mostly someone
reading Slack, and every latency number derived from the trace would be wrong.
"""

from __future__ import annotations

import importlib.util

import pytest

from src.agents.ai import onprem_approvals as approvals
from src.agents.ai import onprem_incident_pipeline as pipeline_mod
from src.agents.ai import onprem_webhook_api as webhook_mod
from src.agents.observability import tracing

_OTEL_PRESENT = importlib.util.find_spec("opentelemetry.sdk") is not None

pytestmark = pytest.mark.skipif(not _OTEL_PRESENT, reason="opentelemetry sdk not installed")

PAYLOAD = {
    "status": "firing",
    "groupLabels": {"alertname": "KubePodCrashLooping"},
    "commonLabels": {
        "alertname": "KubePodCrashLooping",
        "severity": "critical",
        "namespace": "payments",
        "service": "payments-api",
    },
    "commonAnnotations": {"summary": "Pod crash looping"},
    "alerts": [{"status": "firing", "labels": {"alertname": "KubePodCrashLooping"}}],
}


def _stub_analyze(severity: str):
    def _fn(detector_out, _ctx):
        return {
            "detector": detector_out,
            "root_cause": "heuristic: pod crash loop (OOM)",
            "severity": severity,
            "confidence": 0.5,
            "similar_incidents": [],
        }

    return _fn


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    monkeypatch.setenv("PLATFORM_ACTIVITY_FILE", str(tmp_path / "activity.jsonl"))
    monkeypatch.setenv("PLATFORM_APPROVALS_FILE", str(tmp_path / "approvals.jsonl"))
    monkeypatch.setenv("PLATFORM_INCIDENT_FILE", str(tmp_path / "incidents.jsonl"))


@pytest.fixture
def exporter(monkeypatch):
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(trace, "_TRACER_PROVIDER", provider, raising=False)
    monkeypatch.setattr(trace, "_TRACER_PROVIDER_SET_ONCE", None, raising=False)
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
    tracing.reset_tracer_cache()
    yield exporter
    exporter.clear()
    tracing.reset_tracer_cache()


def _names(exporter):
    return [s.name for s in exporter.get_finished_spans()]


def _by_name(exporter):
    return {s.name: s for s in exporter.get_finished_spans()}


class TestAutoPathIsTraced:
    def test_immediate_execution_is_in_the_same_trace_as_the_decision(
        self, exporter, monkeypatch
    ):
        """The AUTO gap: execution happened after the pipeline root closed.

        Without a request-level root this span would be an orphan trace with no
        way back to the detect/analyze/decide legs that chose the action.
        """
        monkeypatch.setattr(pipeline_mod, "_analyze", _stub_analyze("P1"))
        webhook_mod._handle_incident(PAYLOAD)

        names = _names(exporter)
        assert "onprem.execute" in names, "the stage that changes the cluster must be traced"
        assert "onprem.webhook.incident" in names
        assert len({s.context.trace_id for s in exporter.get_finished_spans()}) == 1, (
            "the executor span must not be an orphan trace"
        )

    def test_executor_attributes_are_recorded(self, exporter, monkeypatch):
        monkeypatch.setattr(pipeline_mod, "_analyze", _stub_analyze("P1"))
        webhook_mod._handle_incident(PAYLOAD)
        execute = _by_name(exporter)["onprem.execute"]
        assert "executor.resolved" in execute.attributes
        assert "executor.executed_count" in execute.attributes


class TestApprovalPathIsTraced:
    def _park(self, monkeypatch):
        monkeypatch.setattr(pipeline_mod, "_analyze", _stub_analyze("P2"))
        result = webhook_mod._handle_incident(PAYLOAD)
        assert result.status == "pending_approval"
        return result.approval_id

    def test_parking_still_emits_no_execute_span(self, exporter, monkeypatch):
        """Nothing ran — an execute span here would be a claim that it did."""
        self._park(monkeypatch)
        assert "onprem.execute" not in _names(exporter)

    def test_approval_emits_an_execute_span(self, exporter, monkeypatch):
        """The measurement that was owed: the post-approval execution path."""
        approval_id = self._park(monkeypatch)
        exporter.clear()

        webhook_mod._apply_approval(approval_id)

        names = _names(exporter)
        assert "onprem.execute" in names
        assert "onprem.webhook.approve" in names

    def test_the_approved_execution_links_back_to_the_incident(self, exporter, monkeypatch):
        """A link, not a parent — and it must actually resolve to the incident."""
        approval_id = self._park(monkeypatch)
        incident_root = _by_name(exporter)["onprem.incident_pipeline"]
        incident_trace = incident_root.context.trace_id
        incident_span = incident_root.context.span_id
        exporter.clear()

        webhook_mod._apply_approval(approval_id)
        execute = _by_name(exporter)["onprem.execute"]

        assert execute.context.trace_id != incident_trace, (
            "a human decision sat in between; re-parenting would make the "
            "incident span mostly measure someone reading Slack"
        )
        assert len(execute.links) == 1, "without the link the execution is unattributable"
        linked = execute.links[0].context
        assert linked.trace_id == incident_trace
        assert linked.span_id == incident_span, (
            "the link must point at the span that proposed this remediation, "
            "not merely at its trace"
        )

    def test_the_origin_is_persisted_with_the_parked_approval(self, exporter, monkeypatch):
        """The link survives a restart because it is stored, not held in memory."""
        approval_id = self._park(monkeypatch)
        record = approvals.get(approval_id)
        origin = tracing.SpanOrigin.from_dict(record.get("origin"))
        assert origin is not None
        assert origin.trace_id == format(
            _by_name(exporter)["onprem.incident_pipeline"].context.trace_id, "032x"
        )


class TestRecordsWithoutAnOrigin:
    """Approvals parked before this existed — or while tracing was off."""

    def test_execution_is_still_traced_without_a_link(self, exporter, monkeypatch):
        monkeypatch.setattr(pipeline_mod, "_analyze", _stub_analyze("P2"))
        approval_id = self._park_without_origin(monkeypatch)
        exporter.clear()

        webhook_mod._apply_approval(approval_id)

        execute = _by_name(exporter)["onprem.execute"]
        assert execute.links == (), "a half-known origin must not become a dead link"
        assert execute.attributes["executor.executed_count"] >= 0, "the span is still useful"

    @staticmethod
    def _park_without_origin(monkeypatch):
        result = pipeline_mod.run_incident_pipeline(PAYLOAD, execute=False)
        record = approvals.create_pending(result["stages"]["decision"], {"severity": "P2"})
        assert "origin" not in record, "absent must stay absent, not become an empty dict"
        return record["approval_id"]


class TestTracingOffChangesNothing:
    def test_the_approval_path_works_with_no_endpoint(self, monkeypatch):
        """Offline is the default identity of On-Prem; tracing is diagnostics."""
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
        tracing.reset_tracer_cache()
        monkeypatch.setattr(pipeline_mod, "_analyze", _stub_analyze("P2"))

        parked = webhook_mod._handle_incident(PAYLOAD)
        approved = webhook_mod._apply_approval(parked.approval_id)

        assert approved.status == "approved"
        assert approved.incident_id, "execution must be unaffected by tracing being off"
