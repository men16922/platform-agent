"""Recallable memory tier — distilled, signature-keyed lessons from deploy traces (⑨ B-1).

``deploy_recorder`` persists the *full* trace of every run. This sits beside it and
distills each run into a compact, signature-keyed record — "provider P deploying
service S failed at step X with symptom Y" — so a future run can recall what
happened last time (⑨ B-2 wires that recall into execution; this module is only the
tier itself).

Design mirrors the rest of the codebase:

* **Offline and deterministic.** The signature is a stable hash of
  ``{provider, service, failed_step}`` — no LLM, no clock, no randomness — so the
  same run always distills to the same key and the tier is exercised in
  ``make check`` with no external dependency.
* **Secrets never stored.** :func:`scrub` strips obvious credential/PII shapes from
  any symptom text *before* it is kept, so the memory tier cannot become an
  exfiltration sink.
* **Injectable store.** :class:`MemoryStore` is an in-memory, count-consolidating
  dict by default (tests, and a caller that persists via
  :meth:`MemoryStore.to_dicts`); real JSONL/Dynamo persistence is the caller's
  opt-in, not baked in here.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, replace
from typing import Any

# Obvious secret / PII shapes redacted before any symptom text is stored.
_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)\b(password|passwd|secret|token|api[_-]?key|authorization)\b\s*[:=]\s*\S+"),
    re.compile(r"\b(?:AKIA|ghp_|gho_|sk-)[A-Za-z0-9_\-]{8,}\b"),  # aws key / github / openai
    re.compile(r"\bBearer\s+\S+"),
    re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),  # email
)

_MAX_SYMPTOM = 200


def scrub(text: str) -> str:
    """Redact obvious credentials/PII from ``text`` before it is stored."""
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub("[redacted]", text)
    return text


def signature(provider: str, service: str, failed_step: str) -> str:
    """Stable 16-hex key for ``{provider, service, failed_step}`` (case-insensitive).

    A successful run has an empty ``failed_step``, so all of a service's clean runs
    share one signature and its failures key by the step that broke.
    """
    raw = f"{provider}|{service}|{failed_step}".lower()
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class DistilledMemory:
    """One compact lesson distilled from a deploy run."""

    signature: str
    provider: str
    service: str
    ok: bool
    failed_step: str = ""  # "" when the run succeeded
    symptom: str = ""  # scrubbed, capped; "" when the run succeeded
    seen: int = 1  # times this signature has been recorded (consolidation count)

    def to_dict(self) -> dict[str, Any]:
        return {
            "signature": self.signature,
            "provider": self.provider,
            "service": self.service,
            "ok": self.ok,
            "failed_step": self.failed_step,
            "symptom": self.symptom,
            "seen": self.seen,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "DistilledMemory":
        return cls(
            signature=d["signature"],
            provider=d["provider"],
            service=d["service"],
            ok=bool(d["ok"]),
            failed_step=d.get("failed_step", ""),
            symptom=d.get("symptom", ""),
            seen=d.get("seen", 1),
        )


def _first_failure(record: dict[str, Any]) -> tuple[str, str]:
    """The first failing step's ``(name, message)`` from a deploy record's steps,
    falling back to the record summary when no step is explicitly marked failed."""
    for step in record.get("steps") or []:
        if isinstance(step, dict) and (step.get("ok") is False or step.get("error")):
            name = str(step.get("tool") or step.get("name") or "unknown")
            message = str(step.get("error") or step.get("summary") or step.get("result") or "")
            return name, message
    return "unknown", str(record.get("summary", ""))


def distill(record: dict[str, Any]) -> DistilledMemory:
    """Distil one ``deploy_recorder``-shaped record into a :class:`DistilledMemory`.

    Reads defensively (``provider``/``service``/``ok``/``steps``) so a schema drift
    degrades to ``"unknown"`` rather than raising. A failed run captures the first
    failing step and a scrubbed, capped symptom; a clean run captures neither.
    """
    provider = str(record.get("provider") or "unknown")
    service = str(record.get("service") or record.get("service_name") or "unknown")
    ok = bool(record.get("ok", False))

    failed_step, symptom = "", ""
    if not ok:
        failed_step, raw_symptom = _first_failure(record)
        symptom = scrub(raw_symptom)[:_MAX_SYMPTOM]

    return DistilledMemory(
        signature=signature(provider, service, failed_step),
        provider=provider,
        service=service,
        ok=ok,
        failed_step=failed_step,
        symptom=symptom,
    )


class MemoryStore:
    """In-memory, count-consolidating store keyed by signature.

    :meth:`remember` merges a repeated signature by bumping ``seen`` and keeping the
    latest symptom — a light consolidation so the tier does not grow one row per run
    (⑨ B-3 adds periodic cross-signature consolidation on top of this).
    """

    def __init__(self, memories: list[DistilledMemory] | None = None):
        self._by_sig: dict[str, DistilledMemory] = {}
        for m in memories or []:
            self.remember(m)

    def remember(self, memory: DistilledMemory) -> DistilledMemory:
        existing = self._by_sig.get(memory.signature)
        if existing is not None:
            merged = replace(
                existing,
                seen=existing.seen + memory.seen,
                symptom=memory.symptom or existing.symptom,
                ok=memory.ok,
            )
            self._by_sig[memory.signature] = merged
            return merged
        self._by_sig[memory.signature] = memory
        return memory

    def record(self, deploy_record: dict[str, Any]) -> DistilledMemory:
        """Distil a deploy record and remember it in one step."""
        return self.remember(distill(deploy_record))

    def recall(self, sig: str) -> DistilledMemory | None:
        """The consolidated memory for a signature, or ``None`` if never seen."""
        return self._by_sig.get(sig)

    def recall_for(self, provider: str, service: str, failed_step: str = "") -> DistilledMemory | None:
        """Recall by the raw fields, hashing to the signature for the caller."""
        return self.recall(signature(provider, service, failed_step))

    def recall_failures(self, provider: str) -> list[DistilledMemory]:
        """All recorded *failures* for a provider — the run-start recall query, when
        the failing step of the new run is not yet known (most-seen first)."""
        rows = [m for m in self._by_sig.values() if not m.ok and m.provider.lower() == provider.lower()]
        return sorted(rows, key=lambda m: m.seen, reverse=True)

    def all(self) -> list[DistilledMemory]:
        return list(self._by_sig.values())

    def to_dicts(self) -> list[dict[str, Any]]:
        """Serialise for the caller to persist (JSONL/Dynamo) — persistence is opt-in."""
        return [m.to_dict() for m in self._by_sig.values()]

    @classmethod
    def from_dicts(cls, rows: list[dict[str, Any]]) -> "MemoryStore":
        return cls([DistilledMemory.from_dict(r) for r in rows])


# --- recall & advisory injection (⑨ B-2) -------------------------------------
# The run-start half: find the failures relevant to a new request and format them
# as a *non-binding* hint. The hint is advisory only — it never overrides the
# current run's own checks (the Guardian/reconciliation gates stay authoritative).


def relevant_memories(store: MemoryStore, provider: str, instruction: str) -> list[DistilledMemory]:
    """Past failures for ``provider`` whose service name appears in ``instruction``.

    A substring match on the service name avoids needing to parse the free-text
    request — a run mentioning "orders-api" surfaces orders-api's prior failures.
    """
    text = instruction.lower()
    return [m for m in store.recall_failures(provider) if m.service.lower() in text]


def advisory_block(memories: list[DistilledMemory]) -> str:
    """Format matching failures as a non-binding advisory block, or ``""`` if none."""
    if not memories:
        return ""
    lines = ["[Advisory — past runs, non-binding; do not override current checks]"]
    for m in memories:
        seen = f" (seen {m.seen}x)" if m.seen > 1 else ""
        symptom = f": {m.symptom}" if m.symptom else ""
        lines.append(f"- {m.service} previously failed at {m.failed_step}{symptom}{seen}")
    return "\n".join(lines)


def augment_instruction(instruction: str, store: MemoryStore | None, provider: str) -> str:
    """Prepend the advisory block for matching past failures to ``instruction``.

    Opt-in: with ``store`` ``None`` — or no matching memory — the instruction is
    returned unchanged, so the default execution path is untouched.
    """
    if store is None:
        return instruction
    block = advisory_block(relevant_memories(store, provider, instruction))
    return f"{block}\n\n{instruction}" if block else instruction


# --- periodic consolidation (⑨ B-3) ------------------------------------------
# The store already dedups per signature on write; consolidation is the *periodic*
# pass on top: drop transient one-offs, and surface the recurring pain point per
# service. Both are pure — the caller schedules them (cron/loop); there is no clock
# or scheduler baked in here.


def consolidate(store: MemoryStore, *, min_seen: int = 2) -> MemoryStore:
    """A new store keeping only *recurring* failures (``seen >= min_seen``) plus all
    successes — transient one-off failures are pruned so the tier stays long-term."""
    kept = [m for m in store.all() if m.ok or m.seen >= min_seen]
    return MemoryStore(kept)


def dominant_failures(store: MemoryStore) -> dict[tuple[str, str], DistilledMemory]:
    """The most-seen failure per ``(provider, service)`` — its recurring pain point."""
    out: dict[tuple[str, str], DistilledMemory] = {}
    for m in store.all():
        if m.ok:
            continue
        key = (m.provider, m.service)
        if key not in out or m.seen > out[key].seen:
            out[key] = m
    return out


__all__ = [
    "DistilledMemory",
    "MemoryStore",
    "advisory_block",
    "augment_instruction",
    "consolidate",
    "distill",
    "dominant_failures",
    "relevant_memories",
    "scrub",
    "signature",
]
