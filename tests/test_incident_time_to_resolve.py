"""Time-to-resolve is derivable — and the number the weekly report ships is real.

Follow-on to the 2026-07-29 fire-time work, and the same defect family: a value
is declared, stored, and then either nobody reads it or what reads it cannot
tell it apart from a default.

Three defects, one chain, all of them invisible to the existing suite:

1. **The writers defaulted `resolved_at` to the row's own write time.** The cloud
   writer set it unconditionally to `created_at` — including on unresolved rows,
   which then carried a resolution timestamp. The on-prem writer never set it.

2. **`_fetch_incidents_from_dynamo` read `resolved_at` into BOTH `started_at`
   and `resolved_at`.** Every incident it produced began and ended at the same
   instant, so `average_mttr_minutes` has been a structural 0.0 in every weekly
   on-call report ever sent — and `mttr_delta_minutes` a structural 0 on top of
   it. `TestOncallReporter` passes because it hands `summarize_incidents` a
   fixture with two different timestamps, which is a shape the only real
   producer could not emit. Asserting the producer's output would have caught
   nothing; asserting the *fixture* caught nothing for as long as it existed.

3. **The dashboard's Scan projection did not name the fields its readers read.**
   `triggered_at`, `confidence`, `reconciliation` and `trace_id` were fetched as
   undefined no matter how carefully `mapIncidentRecord` handled them — so this
   morning's writer fix (gate 1496) stopped one layer short of the badge built
   to display it, and cloud incidents had rendered "confidence n/a" since the
   detail view shipped.

The MTTR assertions below go through `_fetch_incidents_from_dynamo`, not around
it. That is the whole lesson of this file: the previous tests were green against
an input shape production never produced.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.agents.ai import onprem_incidents as incidents
from src.agents.operations.aws import reporting
from src.agents.operations.oncall_reporter import build_weekly_oncall_report, summarize_incidents

INCIDENT_DATA = Path("dashboard/src/lib/incident-data.ts")
INCIDENT_TIME = Path("dashboard/src/lib/incident-time.ts")


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    monkeypatch.setenv("PLATFORM_INCIDENT_FILE", str(tmp_path / "incidents.jsonl"))
    monkeypatch.delenv("PLATFORM_STATE_DSN", raising=False)


# ---------------------------------------------------------------------------
# 1. The writers
# ---------------------------------------------------------------------------

def _cloud_item(resolved: bool) -> dict:
    """One row exactly as the shared cloud executor writes it."""
    from src.agents.operations.aws.executor import _record_incident

    from tests.test_dashboard_incident_persistence import _decision

    table = MagicMock()
    with patch("src.agents.operations.aws.executor._DYNAMO") as dynamo:
        dynamo.Table.return_value = table
        _record_incident(
            incident_id="INC-12345678",
            decision=_decision(),
            executed=["AWS-RestartEKSPod"],
            resolved=resolved,
        )
    return table.put_item.call_args.kwargs["Item"]


class TestTheCloudRowOnlyClaimsAResolutionItHad:
    def test_a_resolved_incident_records_when_it_finished(self):
        item = _cloud_item(resolved=True)
        assert item["resolved_at"], "a resolved incident must carry its resolution time"

    def test_an_open_incident_carries_no_resolution_time(self):
        """
        This is the defect. `resolved_at` was set unconditionally, so an
        incident that resolved nothing still reported a resolution — at exactly
        its own creation time, which downstream reads as "fixed instantly".
        """
        item = _cloud_item(resolved=False)
        assert "resolved_at" not in item

    def test_created_at_is_still_written_for_open_incidents(self):
        """Removing the default must not take the row's write time with it."""
        assert _cloud_item(resolved=False)["created_at"]


class TestTheOnPremRowRecordsItToo:
    def test_resolved_incident_gets_a_resolution_time(self):
        record = incidents.record_incident(
            severity="P1", alarm_name="payments-api", root_cause="crash loop",
            runbook_id="eks-pod-oom", remediation_mode="AUTO", resolved=True,
            triggered_at="2026-07-29T06:40:00Z",
        )
        assert record["resolved_at"] == record["created_at"]

    def test_incident_parked_on_the_approval_gate_has_none(self):
        """A P2 waiting for a human is not an incident resolved when it was filed."""
        record = incidents.record_incident(
            severity="P2", alarm_name="payments-api", root_cause="crash loop",
            runbook_id="eks-pod-oom", remediation_mode="APPROVE", resolved=False,
            triggered_at="2026-07-29T06:40:00Z",
        )
        assert "resolved_at" not in record


# ---------------------------------------------------------------------------
# 2. The reader that made MTTR structurally zero
# ---------------------------------------------------------------------------

def _fetch(rows: list[dict]) -> list[dict]:
    """Run the real producer. Not a fixture shaped like its output."""
    with patch.object(reporting, "_DYNAMO") as dynamo, \
         patch.object(reporting, "paginated_scan", return_value=rows):
        dynamo.Table.return_value = MagicMock()
        return reporting._fetch_incidents_from_dynamo(days=7)


def _row(**over) -> dict:
    row = {
        "alarm_name": "orders-api-latency",
        "severity": "P1",
        "root_cause": "pod OOM",
        "runbook_id": "eks-pod-oom",
        "resolved": True,
        "created_at": "2026-07-29T00:30:00Z",
        "resolved_at": "2026-07-29T00:30:00Z",
        "triggered_at": "2026-07-29T00:00:00Z",
        "ttl": int(time.time()) + 90 * 86400,
    }
    row.update(over)
    return row


class TestTheWeeklyReportMeasuresSomething:
    def test_start_is_the_fire_time_not_the_resolution_time(self):
        fetched = _fetch([_row()])
        assert fetched[0]["started_at"] == "2026-07-29T00:00:00Z"
        assert fetched[0]["resolved_at"] == "2026-07-29T00:30:00Z"

    def test_mttr_is_the_real_duration(self):
        """
        30 min and 60 min -> 45.0. This assertion is the point of the file: it
        was 0.0, and the suite's own `test_summarizes_incidents` asserted 45.0
        the whole time off a hand-written fixture.
        """
        fetched = _fetch([
            _row(triggered_at="2026-07-29T00:00:00Z", resolved_at="2026-07-29T00:30:00Z"),
            _row(triggered_at="2026-07-29T01:00:00Z", resolved_at="2026-07-29T02:00:00Z",
                 created_at="2026-07-29T02:00:00Z"),
        ])
        assert summarize_incidents(fetched)["average_mttr_minutes"] == 45.0

    def test_row_without_a_fire_time_falls_back_to_when_we_wrote_it(self):
        """Understates the duration, never invents time we cannot account for."""
        fetched = _fetch([_row(triggered_at=None, created_at="2026-07-29T00:10:00Z",
                               resolved_at="2026-07-29T00:30:00Z")])
        assert fetched[0]["started_at"] == "2026-07-29T00:10:00Z"
        assert summarize_incidents(fetched)["average_mttr_minutes"] == 20.0

    def test_recurring_patterns_group_by_runbook_not_alarm(self):
        """
        `runbook_id` was populated with the alarm name, collapsing the grouping
        back to per-alarm and hiding what it exists to show: distinct alarms
        landing on one runbook.
        """
        fetched = _fetch([
            _row(alarm_name="orders-api-latency", runbook_id="eks-pod-oom"),
            _row(alarm_name="billing-timeout", runbook_id="eks-pod-oom"),
        ])
        assert summarize_incidents(fetched)["recurring_patterns"] == [
            {"pattern": "eks-pod-oom", "count": 2}
        ]

    def test_trend_delta_is_no_longer_structurally_zero(self):
        current = _fetch([_row(triggered_at="2026-07-29T00:00:00Z",
                               resolved_at="2026-07-29T01:00:00Z")])
        previous = _fetch([_row(triggered_at="2026-07-29T00:00:00Z",
                                resolved_at="2026-07-29T00:30:00Z")])
        report = build_weekly_oncall_report(current, previous)
        assert report["trend"]["mttr_delta_minutes"] == 30.0


class TestMttrRefusesSamplesItCannotCompute:
    """None, not 0.0 — a zero-minute sample is a claim, and it drags the average."""

    def test_open_incident_is_not_a_zero_minute_resolution(self):
        summary = summarize_incidents([
            {"service_name": "a", "severity": "P1",
             "started_at": "2026-07-29T00:00:00Z", "resolved_at": "2026-07-29T00:30:00Z"},
            {"service_name": "b", "severity": "P2",
             "started_at": "2026-07-29T00:00:00Z"},  # still open
        ])
        assert summary["total_incidents"] == 2
        assert summary["average_mttr_minutes"] == 30.0

    def test_clock_skew_is_not_an_instant_recovery(self):
        """
        Resolved *before* it fired. Spoke/hub skew is normal; clamping it to 0
        counted skew as a perfect recovery and pulled the average down — the
        exact bias this change exists to remove.
        """
        summary = summarize_incidents([
            {"started_at": "2026-07-29T00:30:00Z", "resolved_at": "2026-07-29T00:00:00Z"},
        ])
        assert summary["average_mttr_minutes"] == 0.0  # no samples at all
        assert summarize_incidents([
            {"started_at": "2026-07-29T00:00:00Z", "resolved_at": "2026-07-29T00:30:00Z"},
            {"started_at": "2026-07-29T00:30:00Z", "resolved_at": "2026-07-29T00:00:00Z"},
        ])["average_mttr_minutes"] == 30.0

    @pytest.mark.parametrize(
        "started,resolved",
        [
            ("not-a-date", "2026-07-29T00:30:00Z"),
            ("2026-07-29T00:00:00Z", "not-a-date"),
            ("2026-07-29T00:00:00", "2026-07-29T00:30:00Z"),  # naive vs aware
            (1753000000, "2026-07-29T00:30:00Z"),             # epoch int, not a str
        ],
    )
    def test_unparseable_timestamps_do_not_take_the_report_down(self, started, resolved):
        """
        Four signal adapters feed `triggered_at` straight from `startsAt` /
        `firedDateTime` / `started_at`. Format variance is reachable live now
        that the value actually flows, and a raise here used to kill the whole
        weekly report rather than one incident.
        """
        summary = summarize_incidents([{"started_at": started, "resolved_at": resolved}])
        assert summary["total_incidents"] == 1
        assert summary["average_mttr_minutes"] == 0.0


# ---------------------------------------------------------------------------
# 3. The projection that dropped the fields its own readers read
# ---------------------------------------------------------------------------

class TestTheScanFetchesWhatTheMapperReads:
    """
    Derived, not a keyword list. A hand-maintained list of expected attributes
    would have been written to match the projection as it stood and would have
    stayed green through exactly this bug. This asks the mapper what it reads
    and requires the Scan to fetch it — so it fails for the *next* field too.
    """

    def _source(self) -> str:
        assert INCIDENT_DATA.is_file()
        return INCIDENT_DATA.read_text(encoding="utf-8")

    def _projected(self, src: str) -> set[str]:
        expr = re.search(r'ProjectionExpression:\s*\n?\s*"([^"]+)"', src)
        assert expr, "could not locate the ProjectionExpression"
        names = dict(re.findall(r'"(#\w+)":\s*"(\w+)"', src))
        out = set()
        for raw in expr.group(1).split(","):
            token = raw.strip()
            out.add(names.get(token, token.lstrip("#")))
        return out

    def _read_by_mapper(self, src: str) -> set[str]:
        body = src[src.index("export function mapIncidentRecord"):]
        body = body[: body.index("\nfunction mapReconciliation")]
        return set(re.findall(r"\bitem\.(\w+)", body))

    def test_every_attribute_the_mapper_reads_is_projected(self):
        src = self._source()
        missing = self._read_by_mapper(src) - self._projected(src)
        assert not missing, (
            f"the Scan drops {sorted(missing)} before the mapper sees them — "
            "a reader cannot recover an attribute the projection did not fetch"
        )

    def test_the_fields_added_this_week_are_actually_among_them(self):
        """Guards the specific four that were being dropped, by name."""
        projected = self._projected(self._source())
        for field in ("triggered_at", "confidence", "reconciliation", "trace_id"):
            assert field in projected, f"{field} is written and rendered but never fetched"

    def test_aliases_resolve_rather_than_leaking_the_hash(self):
        projected = self._projected(self._source())
        assert "mode" in projected and "env" in projected
        assert not any(name.startswith("#") for name in projected)


# ---------------------------------------------------------------------------
# 4. The badge — executed, not grepped
# ---------------------------------------------------------------------------

pytestmark_ts = pytest.mark.skipif(
    shutil.which("npx") is None or not INCIDENT_TIME.is_file(),
    reason="npx/incident-time.ts unavailable — cannot execute the policy",
)


def _ttr(triggered, created, resolved):
    def js(v):
        return "undefined" if v is None else f"'{v}'"

    with tempfile.TemporaryDirectory() as out:
        subprocess.run(
            ["npx", "tsc", str(INCIDENT_TIME), "--outDir", out, "--module", "commonjs",
             "--target", "es2020", "--skipLibCheck"],
            capture_output=True, text=True, timeout=180,
        )
        emitted = Path(out) / "incident-time.js"
        assert emitted.is_file(), "incident-time.ts did not emit"
        proc = subprocess.run(
            ["node", "-e",
             f"const t=require({str(emitted)!r});"
             f"console.log(JSON.stringify(t.describeTimeToResolve("
             f"{js(triggered)},{js(created)},{js(resolved)})))"],
            capture_output=True, text=True, timeout=60,
        )
        assert proc.returncode == 0, proc.stderr
        return json.loads(proc.stdout.strip())


@pytestmark_ts
class TestTimeToResolveBadgeRefusesToOverstate:
    def test_measured_from_the_fire_time_when_there_is_one(self):
        assert _ttr("2026-07-29T00:00:00Z", "2026-07-29T00:10:00Z",
                    "2026-07-29T00:30:00Z") == {"seconds": 1800, "label": "30m"}

    def test_falls_back_to_the_write_time_when_the_source_gave_none(self):
        assert _ttr(None, "2026-07-29T00:10:00Z",
                    "2026-07-29T00:30:00Z") == {"seconds": 1200, "label": "20m"}

    def test_open_incident_renders_no_badge_rather_than_zero(self):
        assert _ttr("2026-07-29T00:00:00Z", "2026-07-29T00:10:00Z", None) is None

    def test_resolution_before_the_fire_time_is_not_rendered(self):
        assert _ttr("2026-07-29T00:30:00Z", "2026-07-29T00:35:00Z",
                    "2026-07-29T00:00:00Z") is None

    def test_unparseable_input_is_not_guessed(self):
        assert _ttr("not-a-date", "2026-07-29T00:10:00Z", "2026-07-29T00:30:00Z") is None
