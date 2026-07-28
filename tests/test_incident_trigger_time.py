"""
The alert's own fire time survives to the record — and to a reader.

Found by the 2026-07-29 sweep for declared-but-unconsumed fields.
`NormalizedIncident.triggered_at` is filled by all four signal adapters from the
source's own timestamp (`startsAt`, `firedDateTime`, `started_at`) and was read
by nothing, so an incident row knew only `created_at` — *when we wrote it*. The
gap between "it broke" and "we noticed" was therefore not derivable, and the
timeline placed each incident at the moment it happened to be processed.

The write half is asserted here; the read half — `describeDetectionGap` — is
executed rather than grepped, for the same reason `visibility.ts` is: an
inverted comparison leaves every string a grep test looks for exactly where it
is, while the screen shows a negative duration.

Fixing this without a consumer would have recreated the very defect the sweep
exists to find, so the badge on the incident detail is part of the change.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from src.agents.ai import onprem_incidents as incidents

SRC = Path("dashboard/src/lib/incident-time.ts")


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    monkeypatch.setenv("PLATFORM_INCIDENT_FILE", str(tmp_path / "incidents.jsonl"))
    monkeypatch.delenv("PLATFORM_STATE_DSN", raising=False)


class TestTheRecordKeepsTheFireTime:
    def test_triggered_at_is_stored_when_the_source_reported_one(self):
        record = incidents.record_incident(
            severity="P2", alarm_name="payments-api", root_cause="crash loop",
            runbook_id="eks-pod-oom", remediation_mode="APPROVE", resolved=True,
            triggered_at="2026-07-29T06:40:00Z",
        )
        assert record["triggered_at"] == "2026-07-29T06:40:00Z"

    def test_created_at_is_still_the_write_time_not_the_fire_time(self):
        """They are different facts and must not collapse into one."""
        record = incidents.record_incident(
            severity="P2", alarm_name="a", root_cause="r", runbook_id="rb",
            remediation_mode="APPROVE", resolved=True,
            triggered_at="2026-07-29T06:40:00Z",
        )
        assert record["created_at"] != record["triggered_at"]

    def test_absent_when_the_source_reported_none(self):
        """Absent, not empty and not epoch — a defaulted value would assert a
        fire time that never happened, which is worse than admitting ignorance."""
        record = incidents.record_incident(
            severity="P3", alarm_name="a", root_cause="r", runbook_id="rb",
            remediation_mode="MANUAL", resolved=False,
        )
        assert "triggered_at" not in record


pytestmark_ts = pytest.mark.skipif(
    shutil.which("npx") is None or not SRC.is_file(),
    reason="npx/incident-time.ts unavailable — cannot execute the policy",
)


def _run(script: str):
    with tempfile.TemporaryDirectory() as out:
        subprocess.run(
            ["npx", "tsc", str(SRC), "--outDir", out, "--module", "commonjs",
             "--target", "es2020", "--skipLibCheck"],
            capture_output=True, text=True, timeout=180,
        )
        emitted = Path(out) / "incident-time.js"
        assert emitted.is_file(), "incident-time.ts did not emit"
        proc = subprocess.run(
            ["node", "-e", f"const t=require({str(emitted)!r});{script}"],
            capture_output=True, text=True, timeout=60,
        )
        assert proc.returncode == 0, proc.stderr
        return json.loads(proc.stdout.strip())


def _gap(triggered, created):
    def js(v):
        return "undefined" if v is None else f"'{v}'"

    return _run(
        f"console.log(JSON.stringify(t.describeDetectionGap({js(triggered)},{js(created)})))"
    )


@pytestmark_ts
class TestDetectionGapRefusesToOverstate:
    def test_a_real_gap_is_reported(self):
        assert _gap("2026-07-29T06:40:00Z", "2026-07-29T06:40:08Z") == {
            "seconds": 8, "label": "8s"
        }

    def test_no_fire_time_renders_nothing_rather_than_zero(self):
        assert _gap(None, "2026-07-29T06:40:08Z") is None

    def test_a_record_written_before_it_fired_is_not_a_negative_duration(self):
        """Clock skew between a spoke and the hub is normal. "detected -3s" on
        screen destroys trust in every number beside it; an absent badge does not."""
        assert _gap("2026-07-29T06:40:08Z", "2026-07-29T06:40:05Z") is None

    def test_unparseable_input_is_not_guessed(self):
        assert _gap("not-a-date", "2026-07-29T06:40:05Z") is None

    @pytest.mark.parametrize(
        "seconds,label",
        [(59, "59s"), (60, "1m"), (3599, "59m"), (3600, "1h"), (7500, "2h 5m")],
    )
    def test_labels_stay_honest_across_scales(self, seconds, label):
        from datetime import datetime, timedelta, timezone

        fired = datetime(2026, 7, 29, 6, 40, tzinfo=timezone.utc)
        recorded = fired + timedelta(seconds=seconds)
        got = _gap(fired.isoformat().replace("+00:00", "Z"),
                   recorded.isoformat().replace("+00:00", "Z"))
        assert got["label"] == label, (
            "a rounded label like '2h' for 2h59m reads as precision that is not there"
        )
