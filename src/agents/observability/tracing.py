"""
Distributed tracing seam for the Day-2 pipeline.

We already answer "what is wrong" (Prometheus) and "what was logged" (Loki). The
missing signal is **where the time went**: the On-Prem loop advertises
"provision→deploy→validate ~39s" and an incident MTTR, but neither is decomposed,
so "how much of it is local-LLM inference?" is currently unanswerable.

Design constraints this module exists to satisfy:

1. **No hard dependency.** On-Prem's identity is running fully offline; a missing
   ``opentelemetry`` package must not break the pipeline. Import failures and a
   missing endpoint both degrade to a no-op tracer that is still safe to call.
2. **Opt-in by endpoint, like every other backend seam here.** Tracing turns on
   when ``OTEL_EXPORTER_OTLP_ENDPOINT`` is set (mirrors ``ANALYZER_LLM_ENDPOINT``
   for the LLM backend and ``PLATFORM_STATE_DSN`` for the state store). Unset =
   off, so default behaviour is unchanged.
3. **Vendor-neutral.** The app only knows OTLP; the receiving backend is swapped
   by env var (on-prem Tempo, AWS ADOT/X-Ray, GCP Cloud Trace) — the same
   cloud-neutral rule the execution adapters follow.

Span boundaries follow the "system or responsibility boundary" rule: one span per
pipeline stage and one around the LLM call, not one per function.
"""

from __future__ import annotations

import importlib.util
import os
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

_SERVICE_NAME_DEFAULT = "platform-agent"

# Resolved lazily so tests (and the pipeline) can flip env vars between calls.
_TRACER: Any | None = None
_TRACER_RESOLVED_FOR: str | None = None


def otlp_endpoint() -> str:
    """The configured OTLP endpoint, or "" when tracing is off."""
    return os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()


def tracing_enabled() -> bool:
    """True when an OTLP endpoint is configured *and* the SDK is importable."""
    if not otlp_endpoint():
        return False
    # find_spec probes availability without importing (and without an unused-name lint).
    try:
        return importlib.util.find_spec("opentelemetry.trace") is not None
    except (ImportError, ValueError):  # pragma: no cover - broken/partial install
        return False


def reset_tracer_cache() -> None:
    """Drop the memoised tracer (tests flip env vars; production calls this never)."""
    global _TRACER, _TRACER_RESOLVED_FOR
    _TRACER = None
    _TRACER_RESOLVED_FOR = None


def _build_tracer() -> Any | None:
    """
    Build an OTLP-exporting tracer, or return None to mean "no-op".

    Every failure path here is deliberate: a broken/absent tracing backend must
    never take down remediation. Tracing is diagnostics, not control flow.
    """
    endpoint = otlp_endpoint()
    if not endpoint:
        return None
    try:  # pragma: no cover - exercised only where the SDK + endpoint exist
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        provider = trace.get_tracer_provider()
        # Only install our provider if nobody else did (a host app may own it).
        if not isinstance(provider, TracerProvider):
            resource = Resource.create(
                {"service.name": os.getenv("OTEL_SERVICE_NAME", _SERVICE_NAME_DEFAULT)}
            )
            provider = TracerProvider(resource=resource)
            provider.add_span_processor(
                BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True))
            )
            trace.set_tracer_provider(provider)
        return trace.get_tracer(__name__)
    except Exception:
        return None


def _tracer() -> Any | None:
    global _TRACER, _TRACER_RESOLVED_FOR
    endpoint = otlp_endpoint()
    if _TRACER_RESOLVED_FOR != endpoint:
        _TRACER = _build_tracer()
        _TRACER_RESOLVED_FOR = endpoint
    return _TRACER


def _coerce_attribute(value: Any) -> Any:
    """OTel accepts str/bool/int/float (and homogeneous sequences); coerce the rest."""
    if isinstance(value, (str, bool, int, float)):
        return value
    return str(value)


@contextmanager
def span(name: str, **attributes: Any) -> Generator[Any]:
    """
    Start a span, or do nothing when tracing is off.

    Yields the span object when tracing is live and ``None`` otherwise, so callers
    must treat the yielded value as optional (use :func:`set_attributes`).
    Exceptions propagate either way — the span is closed by the SDK's own
    context manager, and the no-op path adds no behaviour at all.
    """
    tracer = _tracer()
    if tracer is None:
        yield None
        return
    clean = {k: _coerce_attribute(v) for k, v in attributes.items() if v is not None}
    with tracer.start_as_current_span(name, attributes=clean) as current:
        yield current


def set_attributes(current: Any, **attributes: Any) -> None:
    """Attach attributes to a span that may be the no-op ``None``."""
    if current is None:
        return
    for key, value in attributes.items():
        if value is not None:
            try:
                current.set_attribute(key, _coerce_attribute(value))
            except Exception:
                # Diagnostics must never break the caller.
                return


def current_trace_id() -> str | None:
    """
    Hex trace id of the active span, for correlating an incident record to a trace.

    Returns None when tracing is off or no span is active — an incident detail view
    should then show no trace link rather than a dead one.
    """
    try:  # pragma: no cover - depends on SDK presence
        from opentelemetry import trace
    except Exception:
        return None
    ctx = trace.get_current_span().get_span_context()
    if not getattr(ctx, "is_valid", False):
        return None
    return format(ctx.trace_id, "032x")
