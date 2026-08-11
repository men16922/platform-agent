"""Real-DynamoDB round trip for the incident attributes that had only ever met a mock.

Why this exists. `tenant`, `env`, `triggered_at`, `confidence`, `reconciliation` and
`resolved_at` were each added to the cloud incident writer with unit coverage that
stops at `put_item.call_args` — the assertion is about the dict handed to boto3, not
about what a table accepts, stores and gives back. That gap is not theoretical here:
`confidence` is the one attribute that must be a `Decimal`, boto3's resource layer
rejects Python floats outright, and `_record_incident` wraps its whole body in
`except Exception` — so the wrong type does not degrade one field, it silently drops
the entire row. A mock accepts a float without complaint.

This drives the PRODUCTION writer against the PRODUCTION table, reads back with the
production reader, and deletes the probe row. It is read-mostly and self-cleaning,
but it does write one row to a real table — run it deliberately.

    python scripts/probe_incident_roundtrip.py
"""

from __future__ import annotations

import pathlib
import sys
from decimal import Decimal

# Same as scripts/probe_scope_reachability.py: run as `python scripts/...` from the
# repo root, which does not put the root on the path.
REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

# `_report_logging` lives beside this file; `watch_cloud_spend` imports its sibling
# the same way. Needed because sys.path[0] is only `scripts/` when the script is
# run directly — a test that imports it by path gets neither.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from _report_logging import send_library_logs_to_the_report  # noqa: E402

from src.agents.models import (  # noqa: E402
    AlarmContext,
    AnalyzerOutput,
    DecisionOutput,
    DetectorOutput,
    NormalizedIncident,
    RemediationMode,
    Severity,
)
from src.agents.operations.aws import reporting  # noqa: E402
from src.agents.operations.aws.executor import _record_incident  # noqa: E402

#: Sorts to the end of the table and names itself, so a row left behind by a crashed
#: run is obvious rather than looking like a real incident on the dashboard.
ALARM = "zz-roundtrip-probe"
INCIDENT_ID = "INC-ROUNDTRIP-PROBE"

FIRED_AT = "2026-08-08T00:00:00Z"
RECONCILIATION = {"gate": "passed", "detail": "argocd in sync"}


def _decision() -> DecisionOutput:
    """Every attribute populated — an unset field cannot falsify its own storage."""
    alarm = AlarmContext(
        alarm_name=ALARM,
        alarm_arn=f"arn:aws:cloudwatch:us-east-1:000000000000:alarm:{ALARM}",
        namespace="AWS/EKS",
        metric_name="pod_memory_utilization",
        dimensions={"ClusterName": "orders"},
        reason="round-trip probe",
        state="ALARM",
        triggered_at=FIRED_AT,
    )
    normalized = NormalizedIncident(
        provider="aws",
        service="orders-api",
        resource_type="kubernetes-workload",
        resource_id="orders-api",
        signal_type="memory-high",
        severity_hint="P1",
        tenant="acme",
        env="dev",
        source_metadata={"region": "us-east-1"},
        triggered_at=FIRED_AT,
    )
    analyzer = AnalyzerOutput(
        detector=DetectorOutput(alarm=alarm, normalized_incident=normalized),
        root_cause="memory leak",
        severity=Severity.P1,
        confidence=0.98,
    )
    return DecisionOutput(
        analyzer=analyzer,
        runbook_id="eks-pod-oom",
        remediation_mode=RemediationMode.AUTO,
        actions=["AWS-RestartEKSPod"],
        reconciliation=RECONCILIATION,
    )


def main() -> int:
    send_library_logs_to_the_report()
    table = reporting._DYNAMO.Table(reporting._INCIDENT_TABLE)
    key = {"alarm_name": ALARM, "incident_id": INCIDENT_ID}
    failures: list[str] = []

    print(f"table: {reporting._INCIDENT_TABLE}")
    print("=" * 72)
    print("1. WRITE — production writer, production table")
    print("=" * 72)
    _record_incident(
        incident_id=INCIDENT_ID, decision=_decision(),
        executed=["AWS-RestartEKSPod"], resolved=True,
    )

    raw = table.get_item(Key=key).get("Item")
    if raw is None:
        print("!! NOTHING LANDED — `_record_incident`'s `except Exception` swallowed it.")
        print("   This is the failure the Decimal comment predicts; a mock cannot show it.")
        return 1
    print(f"   row landed, {len(raw)} attributes\n")

    print("=" * 72)
    print("2. RAW READ-BACK — presence and type after a real round trip")
    print("=" * 72)
    expected: dict[str, tuple[object, type]] = {
        "triggered_at": (FIRED_AT, str),
        "confidence": (Decimal("0.98"), Decimal),
        "reconciliation": (RECONCILIATION, dict),
        "tenant": ("acme", str),
        "env": ("dev", str),
    }
    for name, (want, want_type) in expected.items():
        got = raw.get(name, "<ABSENT>")
        ok = name in raw and isinstance(got, want_type) and got == want
        if not ok:
            failures.append(f"{name}: got {got!r} ({type(got).__name__})")
        print(f"   {'OK  ' if ok else 'FAIL'} {name:15}= {got!r}  ({type(got).__name__})")

    resolved_ok = isinstance(raw.get("resolved_at"), str) and bool(raw.get("resolved_at"))
    if not resolved_ok:
        failures.append(f"resolved_at: {raw.get('resolved_at')!r}")
    print(f"   {'OK  ' if resolved_ok else 'FAIL'} {'resolved_at':15}= "
          f"{raw.get('resolved_at')!r}")

    # The dashboard reads `confidence` as `typeof item.confidence === 'number'`.
    # A DynamoDB N is what makes that true on the JS side; a stored string would
    # render "n/a" forever while looking correct here.
    n_typed = isinstance(raw.get("confidence"), Decimal)
    if not n_typed:
        failures.append("confidence is not a DynamoDB number — dashboard renders n/a")

    print()
    print("=" * 72)
    print("3. PRODUCTION READER — does the projection see what landed?")
    print("=" * 72)
    fetched = [
        r for r in reporting._fetch_incidents_from_dynamo(days=7)
        if r.get("alarm_name") == ALARM
    ]
    if not fetched:
        failures.append("reader returned nothing for the probe row")
        print("   FAIL reader did not return the row")
    else:
        row = fetched[0]
        started_ok = row["started_at"] == FIRED_AT
        if not started_ok:
            failures.append(f"started_at came from the wrong field: {row['started_at']!r}")
        print(f"   {'OK  ' if started_ok else 'FAIL'} started_at = {row['started_at']!r} "
              "(must be triggered_at, not created_at)")
        print(f"   OK   resolved_at= {row['resolved_at']!r}")
        print(f"   OK   runbook_id = {row['runbook_id']!r}")

    print()
    print("=" * 72)
    print("4. CLEANUP")
    print("=" * 72)
    table.delete_item(Key=key)
    gone = table.get_item(Key=key).get("Item") is None
    if not gone:
        failures.append("probe row not deleted")
    print(f"   {'OK  ' if gone else 'FAIL'} probe row removed")

    print()
    print("=" * 72)
    print("RESULT:", "ALL CHECKS PASSED" if not failures else f"{len(failures)} FAILURE(S)")
    for failure in failures:
        print("  -", failure)
    print("=" * 72)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
