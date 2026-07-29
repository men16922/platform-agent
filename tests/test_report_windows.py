"""The report windows were measured with the retention field, not a clock.

`ttl` on an incident row is the write time PLUS ninety days. Both fetches in
`operations/aws/reporting.py` treated it as a timestamp:

  * the daily SLO fetch filtered `ttl >= now - 24h`. `ttl` is always ~90 days in
    the future, and the cutoff is in the past, so the condition was true for
    every row that had not already expired. The "last 24 hours" was the whole
    retention window, and the failure counts feeding the SLO report were
    inflated by however much history the table held.
  * the weekly on-call fetch recovered the write time as `ttl - 90 days`, which
    is right only until someone changes the writer's retention — and a row with
    no `ttl` defaulted to `now`, landing 90 days in the past and dropping out of
    every report without a sound.

Both now read `created_at`, which every writer stamps unconditionally, and a row
that can be placed in time by neither is excluded rather than guessed at.

These assertions go through the real fetch functions, not around them — the
lesson from the MTTR bug, where a hand-built fixture asserted a shape the only
producer could not emit.
"""

import ast
import pathlib
import time
from unittest.mock import MagicMock, patch

from boto3.dynamodb.conditions import Attr

import src.agents.operations.aws.reporting as reporting

DAY = 86400
REPO = pathlib.Path(__file__).resolve().parents[1]
EXECUTOR = REPO / "src" / "agents" / "operations" / "aws" / "executor.py"


def _row(age_days: float, **over):
    """A row exactly as `aws/executor._record_incident` writes it."""
    created = int(time.time()) - int(age_days * DAY)
    row = {
        "alarm_name": f"svc-{age_days}",
        "incident_id": f"INC-{age_days}",
        "severity": "P2",
        "root_cause": "pod OOM",
        "runbook_id": "eks-pod-oom",
        "resolved": False,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(created)),
        "ttl": created + 90 * DAY,
    }
    row.update(over)
    return row


def _slo(rows):
    with patch.object(reporting, "_DYNAMO") as dynamo, \
         patch.object(reporting, "paginated_scan", return_value=rows):
        dynamo.Table.return_value = MagicMock()
        return reporting._fetch_slo_metrics_from_dynamo(hours=24)


def _weekly(rows, **kw):
    with patch.object(reporting, "_DYNAMO") as dynamo, \
         patch.object(reporting, "paginated_scan", return_value=rows):
        dynamo.Table.return_value = MagicMock()
        return reporting._fetch_incidents_from_dynamo(**kw)


# ---------------------------------------------------------------------------
# 1. The daily SLO window
# ---------------------------------------------------------------------------

class TestTheDailyWindowIsADay:
    def test_ninety_days_of_history_does_not_count_as_twenty_four_hours(self):
        """The regression itself: one incident per day for 90 days.

        `failed_requests` is the raw incident count (`total_requests` is the
        synthesised x100). An earlier draft of this assertion divided by 100 and
        so passed on the unfixed code — 90 // 100 is 0. Compare the number the
        function actually reports.
        """
        rows = [_row(d) for d in range(90)]
        counted = sum(r["failed_requests"] for r in _slo(rows))
        assert counted <= 2, (
            f"{counted} of 90 rows fell inside a 24-hour window — the filter is "
            "matching everything that has not expired"
        )

    def test_a_row_from_today_is_counted(self):
        result = _slo([_row(0)])
        assert sum(r["failed_requests"] for r in result) == 1

    def test_a_row_from_last_week_is_not(self):
        result = _slo([_row(7)])
        # Falls back to the "no incidents" shape rather than counting the old row.
        assert result == [
            {"service_name": "platform", "total_requests": 1000, "failed_requests": 0}
        ]

    def test_the_scan_filters_on_the_timestamp_not_the_retention_field(self):
        captured = {}

        def _capture(_table, **kw):
            captured.update(kw)
            return []

        with patch.object(reporting, "_DYNAMO") as dynamo, \
             patch.object(reporting, "paginated_scan", side_effect=_capture):
            dynamo.Table.return_value = MagicMock()
            reporting._fetch_slo_metrics_from_dynamo(hours=24)

        expr = captured.get("FilterExpression")
        assert expr is not None, "the scan must still filter server-side"
        built = expr.get_expression()
        attr = built["values"][0]
        assert isinstance(attr, type(Attr("x")))
        assert attr.name == "created_at", (
            f"the scan filters on `{attr.name}`; `ttl` is a retention field and "
            "comparing it against a past cutoff is true for every live row"
        )


# ---------------------------------------------------------------------------
# 2. The weekly on-call window
# ---------------------------------------------------------------------------

class TestTheWeeklyWindow:
    def test_rows_inside_and_outside_the_week_are_separated(self):
        rows = [_row(1), _row(3), _row(6), _row(20)]
        got = _weekly(rows, days=7)
        assert len(got) == 3, [g["alarm_name"] for g in got]

    def test_the_previous_week_offset_selects_the_older_rows(self):
        rows = [_row(1), _row(9), _row(12)]
        got = _weekly(rows, days=7, offset_days=7)
        assert {g["alarm_name"] for g in got} == {"svc-9", "svc-12"}

    def test_a_row_with_a_timestamp_but_no_ttl_is_still_reported(self):
        """The case that separates the two implementations.

        The old code read `item.get("ttl", now) - 90 days`, so a row with no
        `ttl` was placed ninety days before now and silently left every weekly
        report — even though its `created_at` says plainly that it is two days
        old. Every other row in these tests has a `ttl` consistent with its
        `created_at`, which is why reverting the window alone kept them green.
        """
        row = _row(2)
        del row["ttl"]
        got = _weekly([row], days=7)
        assert len(got) == 1, (
            "a row that states when it was created was dropped for lacking a "
            "retention field"
        )

    def test_created_at_wins_when_the_two_disagree(self):
        """`ttl` written with a different retention must not move the row."""
        row = _row(2)
        row["ttl"] = int(time.time()) + 30 * DAY  # as if retention were 30 days
        assert len(_weekly([row], days=7)) == 1
        old = _row(30)
        old["ttl"] = int(time.time()) + 89 * DAY  # would invert to ~1 day old
        assert _weekly([old], days=7) == []

    def test_a_row_with_no_timestamp_at_all_is_excluded_not_guessed(self):
        """Undateable rows leave the window rather than landing in `now`."""
        row = _row(1)
        del row["created_at"]
        del row["ttl"]
        assert _weekly([row], days=7) == []

    def test_a_legacy_row_with_only_ttl_is_still_placed(self):
        """Kept deliberately: dropping it would silently shrink the report.

        Coupled to the writer's retention constant, which is why the next test
        derives that constant instead of trusting this one.
        """
        row = _row(2)
        del row["created_at"]
        assert len(_weekly([row], days=7)) == 1


# ---------------------------------------------------------------------------
# 3. The fallback's coupling, derived from the writer
# ---------------------------------------------------------------------------

def test_the_legacy_retention_matches_what_the_writer_stamps():
    """`_LEGACY_RETENTION_SEC` inverts `ttl`, so it must equal the writer's.

    Derived from `_record_incident`'s own expression rather than restated: if
    someone changes the retention there, the reporter's fallback silently shifts
    every legacy row by the difference, and nothing else would notice.
    """
    tree = ast.parse(EXECUTOR.read_text(encoding="utf-8"))
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        for key, value in zip(node.keys, node.values):
            if isinstance(key, ast.Constant) and key.value == "ttl":
                # `int(time.time()) + 90 * 86400`
                for sub in ast.walk(value):
                    if isinstance(sub, ast.BinOp) and isinstance(sub.op, ast.Mult):
                        left, right = sub.left, sub.right
                        if (
                            isinstance(left, ast.Constant)
                            and isinstance(right, ast.Constant)
                            and isinstance(left.value, int)
                            and isinstance(right.value, int)
                        ):
                            found.append(left.value * right.value)

    assert found, "could not find the ttl retention the incident writer stamps"
    assert set(found) == {reporting._LEGACY_RETENTION_SEC}, (
        f"the writer stamps {sorted(set(found))}s of retention but the reporter "
        f"inverts {reporting._LEGACY_RETENTION_SEC}s — legacy rows would shift"
    )
