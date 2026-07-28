"""
Guards for the tracing seam (src/agents/observability/tracing.py).

Two contracts:
  1. **Off by default** — no OTLP endpoint means a no-op that is still safe to
     call, because On-Prem must run fully offline with no tracing backend.
  2. **Real spans when on** — verified against an in-memory exporter, so the
     wiring is proven without a Tempo/collector running.
"""

from __future__ import annotations

import importlib.util

import pytest

from src.agents.observability import tracing

_OTEL_PRESENT = importlib.util.find_spec("opentelemetry.sdk") is not None


@pytest.fixture(autouse=True)
def _clean_tracer_state(monkeypatch):
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    tracing.reset_tracer_cache()
    yield
    tracing.reset_tracer_cache()


class TestDisabledByDefault:
    def test_no_endpoint_means_disabled(self):
        assert tracing.otlp_endpoint() == ""
        assert tracing.tracing_enabled() is False

    def test_span_is_a_safe_noop(self):
        with tracing.span("x", attr="v") as current:
            assert current is None

    def test_set_attributes_tolerates_noop_span(self):
        tracing.set_attributes(None, anything="v")  # must not raise

    def test_no_trace_id_when_off(self):
        assert tracing.current_trace_id() is None

    def test_exceptions_still_propagate_through_a_noop_span(self):
        """Tracing must not swallow failures — it is diagnostics, not control flow."""
        with pytest.raises(ValueError):
            with tracing.span("x"):
                raise ValueError("boom")

    def test_blank_endpoint_is_treated_as_unset(self, monkeypatch):
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "   ")
        tracing.reset_tracer_cache()
        assert tracing.tracing_enabled() is False


@pytest.mark.skipif(not _OTEL_PRESENT, reason="opentelemetry sdk not installed")
class TestEnabledEmitsSpans:
    """Uses an in-memory exporter — no collector, no network, no Tempo required."""

    @pytest.fixture
    def exporter(self, monkeypatch):
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
        from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
            InMemorySpanExporter,
        )

        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        # _build_tracer only installs its own provider when none is set, so
        # seeding one here makes it adopt ours (and export in-memory).
        monkeypatch.setattr(trace, "_TRACER_PROVIDER", provider, raising=False)
        monkeypatch.setattr(trace, "_TRACER_PROVIDER_SET_ONCE", None, raising=False)
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
        tracing.reset_tracer_cache()
        yield exporter
        exporter.clear()

    def test_span_is_exported_with_attributes(self, exporter):
        with tracing.span("onprem.analyze", {"analyzer.severity": "P2"}):
            pass
        spans = exporter.get_finished_spans()
        assert [s.name for s in spans] == ["onprem.analyze"]
        assert spans[0].attributes["analyzer.severity"] == "P2"

    def test_nested_spans_share_one_trace(self, exporter):
        """Stage spans must roll up under the pipeline root, not be orphans."""
        with tracing.span("onprem.incident_pipeline"):
            with tracing.span("onprem.detect"):
                pass
            with tracing.span("onprem.analyze"):
                pass
        spans = exporter.get_finished_spans()
        assert {s.name for s in spans} == {
            "onprem.incident_pipeline",
            "onprem.detect",
            "onprem.analyze",
        }
        assert len({s.context.trace_id for s in spans}) == 1, "all stages share one trace"

    def test_trace_id_is_available_inside_a_span(self, exporter):
        with tracing.span("onprem.incident_pipeline"):
            trace_id = tracing.current_trace_id()
        assert trace_id is not None
        assert len(trace_id) == 32, "hex-encoded 128-bit trace id"
        assert trace_id == format(exporter.get_finished_spans()[0].context.trace_id, "032x")

    def test_none_attributes_are_dropped_not_stringified(self, exporter):
        with tracing.span("s", present="v", absent=None):
            pass
        attributes = exporter.get_finished_spans()[0].attributes
        assert attributes["present"] == "v"
        assert "absent" not in attributes

    def test_non_scalar_attributes_are_coerced(self, exporter):
        with tracing.span("s", {"actions": ["a", "b"]}):
            pass
        # OTel rejects heterogeneous/complex values; coercion keeps the span valid.
        assert exporter.get_finished_spans()[0].attributes["actions"] == "['a', 'b']"


@pytest.mark.skipif(not _OTEL_PRESENT, reason="opentelemetry sdk not installed")
class TestPipelineIsInstrumented:
    """
    The whole point of ② is decomposing the incident wall-clock, so the four
    stage spans must actually appear when the real pipeline runs.
    """

    @pytest.fixture
    def exporter(self, monkeypatch):
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
        from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
            InMemorySpanExporter,
        )

        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        monkeypatch.setattr(trace, "_TRACER_PROVIDER", provider, raising=False)
        monkeypatch.setattr(trace, "_TRACER_PROVIDER_SET_ONCE", None, raising=False)
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
        tracing.reset_tracer_cache()
        yield exporter
        exporter.clear()

    @staticmethod
    def _run(monkeypatch, *, execute: bool):
        """Drive the pipeline with the four handlers stubbed — spans are the subject."""
        from src.agents.ai import onprem_incident_pipeline as pipeline

        monkeypatch.setattr(
            pipeline, "_detect", lambda e, c: {"normalized_incident": {"provider": "onprem"}}
        )
        monkeypatch.setattr(
            pipeline, "_analyze", lambda e, c: {"severity": "P2", "confidence": 0.95}
        )
        monkeypatch.setattr(
            pipeline, "_decide", lambda e, c: {"runbook_id": "rb", "remediation_mode": "APPROVE"}
        )
        monkeypatch.setattr(
            pipeline,
            "_execute",
            lambda e, c: {"resolved": True, "executed_actions": ["A"], "skipped_actions": []},
        )
        return pipeline.run_incident_pipeline({"alerts": []}, execute=execute)

    def test_four_stage_spans_under_one_trace(self, exporter, monkeypatch):
        self._run(monkeypatch, execute=True)
        names = {s.name for s in exporter.get_finished_spans()}
        assert names == {
            "onprem.incident_pipeline",
            "onprem.detect",
            "onprem.analyze",
            "onprem.decide",
            "onprem.execute",
        }
        assert len({s.context.trace_id for s in exporter.get_finished_spans()}) == 1

    def test_parked_incident_has_no_execute_span(self, exporter, monkeypatch):
        """execute=False parks for approval — an execute span would be a lie."""
        self._run(monkeypatch, execute=False)
        names = {s.name for s in exporter.get_finished_spans()}
        assert "onprem.execute" not in names
        assert "onprem.decide" in names

    def test_stage_attributes_explain_the_incident(self, exporter, monkeypatch):
        self._run(monkeypatch, execute=True)
        by_name = {s.name: s for s in exporter.get_finished_spans()}
        assert by_name["onprem.analyze"].attributes["analyzer.confidence"] == 0.95
        assert by_name["onprem.decide"].attributes["decision.remediation_mode"] == "APPROVE"
        assert by_name["onprem.execute"].attributes["executor.resolved"] is True
        assert by_name["onprem.incident_pipeline"].attributes["incident.provider"] == "onprem"

    def test_result_carries_the_trace_id_for_deep_linking(self, exporter, monkeypatch):
        result = self._run(monkeypatch, execute=True)
        root = [s for s in exporter.get_finished_spans() if s.name == "onprem.incident_pipeline"][0]
        assert result["trace_id"] == format(root.context.trace_id, "032x")


class TestPipelineWithoutTracing:
    def test_result_trace_id_is_none_when_tracing_off(self, monkeypatch):
        """Default offline path: same result shape, no trace link."""
        result = TestPipelineIsInstrumented._run(monkeypatch, execute=True)
        assert result["trace_id"] is None
        assert result["resolved"] is True, "pipeline output must be unchanged by tracing"
