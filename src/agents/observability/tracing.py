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
from dataclasses import dataclass
from typing import Any

_SERVICE_NAME_DEFAULT = "platform-agent"


@dataclass(frozen=True)
class SpanOrigin:
    """Where some later work came from — enough to link back to it.

    A trace id alone cannot form a link (OTel needs a span id too), which is why
    this is a pair and not the bare id already stored on incident records.
    """

    trace_id: str
    span_id: str

    def to_dict(self) -> dict[str, str]:
        return {"trace_id": self.trace_id, "span_id": self.span_id}

    @classmethod
    def from_dict(cls, payload: Any) -> "SpanOrigin | None":
        """Rebuild from a stored record; None when either half is missing.

        Records written before tracing existed — or while it was off — carry
        neither, and that must read as "no origin" rather than a malformed one.
        """
        if not isinstance(payload, dict):
            return None
        trace_id = payload.get("trace_id")
        span_id = payload.get("span_id")
        if not isinstance(trace_id, str) or not isinstance(span_id, str):
            return None
        if not trace_id or not span_id:
            return None
        return cls(trace_id=trace_id, span_id=span_id)

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


def _build_link(origin: "SpanOrigin | None") -> Any | None:
    """An OTel Link to a span we recorded earlier, or None.

    Both ids are required. A link carrying a zero span id is *invalid*, and an
    invalid link renders as a dead reference in the trace UI — the same failure
    `current_trace_id` already refuses to produce ("show no trace link rather
    than a dead one"). So a half-known origin yields no link at all; the caller
    still records the origin as an attribute, which is honest about being a
    breadcrumb rather than a traversable edge.
    """
    if origin is None or not origin.trace_id or not origin.span_id:
        return None
    try:  # pragma: no cover - depends on SDK presence
        from opentelemetry import trace

        return trace.Link(
            trace.SpanContext(
                trace_id=int(origin.trace_id, 16),
                span_id=int(origin.span_id, 16),
                is_remote=True,
                trace_flags=trace.TraceFlags(trace.TraceFlags.SAMPLED),
            )
        )
    except Exception:
        return None


@contextmanager
def span(
    name: str,
    attributes: dict[str, Any] | None = None,
    *,
    link: "SpanOrigin | None" = None,
    **kwattributes: Any,
) -> Generator[Any]:
    """
    Start a span, or do nothing when tracing is off.

    Yields the span object when tracing is live and ``None`` otherwise, so callers
    must treat the yielded value as optional (use :func:`set_attributes`).
    Exceptions propagate either way — the span is closed by the SDK's own
    context manager, and the no-op path adds no behaviour at all.

    ``link`` marks a *causal* relationship to work that finished earlier — used
    for a remediation approved hours after the incident that proposed it. It is
    deliberately a link and not a parent: re-parenting under a span that closed
    long ago would produce one span whose duration is mostly a human reading
    Slack, which poisons every latency figure the trace exists to provide.

    Attributes may be passed as a dict or as keywords. The dict form exists
    because OTel attribute keys are dotted (`executor.resolved`) and therefore
    not valid Python identifiers, so callers were writing ``**{"a.b": v}`` — and
    a ``**`` unpack can collide with the named parameters, which would mean an
    attribute called "link" silently became a span link instead of an attribute.
    """
    tracer = _tracer()
    if tracer is None:
        yield None
        return
    merged = {**(attributes or {}), **kwattributes}
    clean = {k: _coerce_attribute(v) for k, v in merged.items() if v is not None}
    built = _build_link(link)
    with tracer.start_as_current_span(
        name, attributes=clean, links=[built] if built else None
    ) as current:
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


def current_origin() -> SpanOrigin | None:
    """The active span as a linkable origin, or None when tracing is off.

    Captured at the moment work is *parked* so the execution that resumes it —
    possibly hours later, certainly in another request — can point back at the
    exact span that proposed it, not merely at its trace.
    """
    try:  # pragma: no cover - depends on SDK presence
        from opentelemetry import trace
    except Exception:
        return None
    ctx = trace.get_current_span().get_span_context()
    if not getattr(ctx, "is_valid", False):
        return None
    return SpanOrigin(
        trace_id=format(ctx.trace_id, "032x"), span_id=format(ctx.span_id, "016x")
    )
