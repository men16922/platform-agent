"""
`record_incident`'s five defaults are policy, and nothing was asking about them.

Found 2026-09-01 while classifying mypy's output for the pending "should static
analysis join the gate" decision. Ten of the fifteen `arg-type` errors came from
one caller:

    src/agents/ai/onprem_webhook_api.py:143: Argument "severity" to
        "record_incident" has incompatible type "Any | None"; expected "str"

The signature said `severity: str` — required. The body said otherwise:

    "severity":  severity or "P3",
    "mode":      remediation_mode or "MANUAL",
    "alarm_name": alarm_name or "on-prem incident",
    ...

**The code was right and the declaration was false**, which is this repo's
recurring finding turned on a function signature. The fix was to say `str | None`,
because rejecting `None` at the door would turn a degraded incident into *no*
incident — strictly worse than a defaulted one.

⚠️ And `None` is reachable, not theoretical. The pipeline result always *has*
these keys, but their values are themselves `.get()` results, and the pipeline
writes

    incident = detector_out.get("normalized_incident") or {}

which is its own statement that the normalised incident can be absent. When it is,
`service` is `None` and arrives here as `alarm_name`.

⚠️ **Why this file exists at all.** Correcting an annotation changes nothing that
runs. What runs is the defaulting, and `git grep record_incident -- tests/` found
seven files, **none** of which passes `None` for any of the five. The values that
decide how a degraded incident is triaged were unasserted:

  * **`MANUAL`** is the load-bearing one. It is the mode that does *not* execute.
    An incident that arrived with no decision defaulting to `AUTO` would be
    remediated with nobody having chosen to — the exact failure M39 was about,
    reached from the other side.
  * **`P3`** is the bottom of the severity scale. Defaulting to `P1` would page a
    human for every incident whose analyzer output was incomplete.

Both defaults are the *safe* end of their axis. That is the property worth pinning
— not the strings themselves, which is why the two tests below say which end they
are checking and why.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from src.agents.ai import onprem_incidents

# The five fields whose value is `x or "<default>"` in `record_incident`.
DEFAULTS = {
    "alarm_name": "on-prem incident",
    "severity": "P3",
    "mode": "MANUAL",
    "root_cause": "On-prem Day-2 incident.",
    "runbook_id": "generic-recovery",
}

# Field name in the written record -> keyword argument that feeds it. They differ
# for one of the five (`remediation_mode` is written as `mode`), which is the kind
# of mismatch a test that only read the record would never notice.
ARGUMENT_FOR = {
    "alarm_name": "alarm_name",
    "severity": "severity",
    "mode": "remediation_mode",
    "root_cause": "root_cause",
    "runbook_id": "runbook_id",
}


@pytest.fixture
def isolated_store(tmp_path, monkeypatch):
    """`record_incident` appends to a real file; point it at a temp one.

    `PLATFORM_INCIDENT_FILE` is the same knob `_store_path` reads, so this
    exercises the production path rather than a patched stand-in.
    """
    store = tmp_path / "incidents.jsonl"
    monkeypatch.setenv("PLATFORM_INCIDENT_FILE", str(store))
    monkeypatch.setattr(onprem_incidents.state_store, "configured_store", lambda: None)
    return store


def _record_with_nothing(**overrides: Any) -> dict[str, Any]:
    # Annotated because an inferred `dict[str, bool | None]` here would be exactly
    # the kind of quiet type lie this file's subject is about.
    kwargs: dict[str, Any] = dict(
        severity=None,
        alarm_name=None,
        root_cause=None,
        runbook_id=None,
        remediation_mode=None,
        resolved=False,
    )
    kwargs.update(overrides)
    return onprem_incidents.record_incident(**kwargs)


def test_the_signature_accepts_none_at_all(isolated_store):
    """Vacuity guard, and the thing the annotation now admits.

    Before 2026-09-01 this call was a type error every caller was already making.
    If someone re-tightens the signature to `str`, this is what says the callers
    would have to change too.
    """
    record = _record_with_nothing()
    assert record["PK"] == "INCIDENT"
    assert isolated_store.exists(), "the record was not persisted"


@pytest.mark.parametrize("field", sorted(DEFAULTS))
def test_a_missing_field_gets_its_documented_default(isolated_store, field):
    record = _record_with_nothing()
    assert record[field] == DEFAULTS[field], {
        "field": field,
        "fed by keyword": ARGUMENT_FOR[field],
        "got": record[field],
        "expected": DEFAULTS[field],
        "why": (
            "these five defaults are what a degraded incident is triaged as. "
            "Changing one is a policy change, not a tidy-up — say so in the "
            "comment above the signature and update this test in the same commit."
        ),
    }


def test_a_missing_mode_does_not_become_auto(isolated_store):
    """The one that matters most, asserted as a property rather than a string.

    `MANUAL` is the mode that does **not** execute. An incident that arrived with
    no decision — which is exactly when `remediation_mode` is `None` — must not be
    remediated by default. M39 was the same failure from the other side: a report
    of an action nobody performed. This is an action nobody chose.
    """
    record = _record_with_nothing()
    assert record["mode"] != "AUTO", (
        "an incident with no remediation mode now defaults to AUTO. That means an "
        "incident whose decision stage produced nothing would be executed against "
        "the cluster with no human and no policy having selected it."
    )
    assert record["mode"] == "MANUAL", record["mode"]


def test_a_missing_severity_does_not_become_the_paging_end(isolated_store):
    """The other axis. `P3` is the bottom; `P1` pages.

    Defaulting upward would page a human every time the analyzer returned an
    incomplete result — which trains people to ignore the page, and that is how a
    severity scale stops meaning anything.
    """
    record = _record_with_nothing()
    assert record["severity"] not in ("P1", "P2"), (
        f"a missing severity now defaults to {record['severity']!r}. An incomplete "
        "analyzer output is not evidence of a serious incident."
    )


def test_a_value_that_is_given_is_not_overwritten(isolated_store):
    """The other half of every defaulting test — a function that ignores its
    arguments passes all of the above."""
    record = _record_with_nothing(
        severity="P1", remediation_mode="AUTO", alarm_name="orders-api",
        root_cause="oom", runbook_id="eks-pod-oom",
    )
    assert record["severity"] == "P1"
    assert record["mode"] == "AUTO"
    assert record["alarm_name"] == "orders-api"
    assert record["root_cause"] == "oom"
    assert record["runbook_id"] == "eks-pod-oom"


def test_the_defaults_reach_the_store_not_just_the_return_value(isolated_store):
    """`record_incident` both returns the record and appends it.

    A test that only read the return value would pass while the persisted row
    carried `null` — and the dashboard timeline reads the file, not the return.
    """
    _record_with_nothing()
    written = [json.loads(line) for line in isolated_store.read_text().splitlines() if line.strip()]
    assert len(written) == 1, written
    for field, default in DEFAULTS.items():
        assert written[0][field] == default, (field, written[0][field], default)
