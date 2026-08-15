"""
The egress block in `conftest.py` must itself be load-bearing.

A fixture nobody checks is the shape this repo keeps finding: the safety net that
was already removed while everything stayed green (Risk 12③). So these assert the
block fires, that loopback still works (the on-prem webhook tests need it), and
that the analyzer whose live call this caught now takes its documented offline
path deterministically.

Context: D45 decided the gate does not depend on live cloud. Nothing enforced it,
so `gcp/analyzer.py::_analyse` had been issuing real billable
`gemini-2.5-flash:generateContent` calls — one per test, 200s of a 288s gate,
and only on a machine that happened to hold gcloud credentials. Full gate after
the block: **288.56s -> 38.69s, same 2021 passed / 2 skipped.**
"""

from __future__ import annotations

import socket

import pytest

from tests.conftest import OutboundNetworkBlocked


class TestTheBlockFires:
    def test_outbound_connect_is_refused(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        with pytest.raises(OutboundNetworkBlocked) as exc:
            s.connect(("142.250.0.1", 443))
        assert "142.250.0.1" in str(exc.value), "the error must name where it tried to go"
        s.close()

    def test_connect_ex_is_refused_too(self):
        """`connect_ex` is a separate entry point — a guard on one is half a guard."""
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        with pytest.raises(OutboundNetworkBlocked):
            s.connect_ex(("142.250.0.1", 443))
        s.close()

    def test_the_error_says_what_to_do(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        with pytest.raises(OutboundNetworkBlocked) as exc:
            s.connect(("34.117.59.81", 443))
        assert "D45" in str(exc.value)
        s.close()


class TestLoopbackStillWorks:
    """On-prem webhook tests bind and call real local ports — do not break them."""

    def test_localhost_connect_is_allowed(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        port = server.getsockname()[1]
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            client.connect(("127.0.0.1", port))  # must not raise
        finally:
            client.close()
            server.close()


class TestTheAnalyzerTakesItsOfflinePath:
    """The call this caught: `_analyse` must reach its documented fallback, not the wire."""

    def test_gcp_analyse_falls_back_without_the_network(self):
        from src.agents.models import Severity
        from src.agents.operations.gcp.analyzer import _analyse

        detector = _detector()
        root_cause, severity, confidence = _analyse(detector)

        assert "Heuristic analysis (LLM unavailable)" in root_cause
        assert isinstance(severity, Severity)
        assert confidence == 0.3, "the fallback's own confidence, not a model's"

    def test_the_fallback_is_not_silently_empty(self):
        """A fallback that returns nothing would also 'pass' — pin that it carries the alarm."""
        from src.agents.operations.gcp.analyzer import _analyse

        root_cause, _, _ = _analyse(_detector(reason="checkout service outage"))
        assert "checkout service outage" in root_cause


def _detector(reason: str = "Threshold exceeded"):
    from src.agents.models import AlarmContext, DetectorOutput

    return DetectorOutput(
        alarm=AlarmContext(
            alarm_name="checkout-5xx",
            alarm_arn="",
            state="ALARM",
            reason=reason,
            metric_name="probe/status",
            namespace="GCP/gce_instance",
        )
    )
