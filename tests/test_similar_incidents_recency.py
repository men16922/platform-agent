"""
"Past similar incidents" must actually be the recent ones.

Why this file exists (2026-08-15). The AWS lookup queried DynamoDB with
``ScanIndexForward=False`` under the comment "most recent first". The sort key is
`incident_id` (`src/stacks/incident_agent_stack.ts:30`) and that is
`INC-<random hex>` (`executor.py:62`), so descending sort-key order is descending
**hex**, unrelated to time.

The failure is worse than arbitrary because it is *stable*: a newly written
incident joins the list only if its random id beats the current fifth-largest,
odds that fall as ``5/N``. The list therefore **freezes as the alarm accumulates
history** — and a human reads it in the Slack approval message
(`executor.py`, "Past similar incidents") while deciding whether to let a
remediation run unattended.

GCP (Firestore ``order_by("created_at", DESCENDING)``) and Azure (Cosmos
``ORDER BY c.created_at DESC``) already ordered on time. These guards pin AWS to
the same contract and ask the question of all three siblings (Risk 12⑥).
"""

from __future__ import annotations

import inspect
from unittest.mock import MagicMock, patch

import pytest

from src.agents.operations.aws.analyzer import (
    _SIMILAR_LIMIT,
    _SIMILAR_SCAN_CAP,
    _find_similar_incidents,
)


def _rows(pairs):
    """[(incident_id, created_at)] -> DynamoDB-shaped items."""
    return [{"incident_id": i, "created_at": c} for i, c in pairs]


# incident_id order and created_at order deliberately disagree: the lexically
# largest ids are the OLDEST rows. Ordering by the sort key returns exactly the
# wrong five.
SCRAMBLED = _rows([
    ("INC-FFFFFF01", "2026-05-01T00:00:00Z"),
    ("INC-EEEEEE02", "2026-05-02T00:00:00Z"),
    ("INC-DDDDDD03", "2026-05-03T00:00:00Z"),
    ("INC-CCCCCC04", "2026-05-04T00:00:00Z"),
    ("INC-BBBBBB05", "2026-05-05T00:00:00Z"),
    ("INC-0000AA06", "2026-05-06T00:00:00Z"),
    ("INC-0000BB07", "2026-05-07T00:00:00Z"),
    ("INC-0000CC08", "2026-05-08T00:00:00Z"),
    ("INC-0000DD09", "2026-05-09T00:00:00Z"),
    ("INC-0000EE10", "2026-05-10T00:00:00Z"),
])

NEWEST_FIVE = ["INC-0000EE10", "INC-0000DD09", "INC-0000CC08", "INC-0000BB07", "INC-0000AA06"]
LEXICALLY_LARGEST_FIVE = ["INC-FFFFFF01", "INC-EEEEEE02", "INC-DDDDDD03", "INC-CCCCCC04", "INC-BBBBBB05"]


def _dynamo(pages):
    """Fake resource whose Table().query() yields the given pages in order."""
    table = MagicMock()
    table.query.side_effect = list(pages)
    dynamo = MagicMock()
    dynamo.Table.return_value = table
    return dynamo, table


class TestRecency:
    def test_returns_the_newest_not_the_lexically_largest(self):
        dynamo, _ = _dynamo([{"Items": SCRAMBLED}])
        with patch("src.agents.operations.aws.analyzer._DYNAMO", dynamo):
            assert _find_similar_incidents("checkout-5xx") == NEWEST_FIVE

    def test_the_old_behaviour_is_pinned_as_wrong(self):
        """If this ever equals the lexical order again, the defect is back."""
        dynamo, _ = _dynamo([{"Items": SCRAMBLED}])
        with patch("src.agents.operations.aws.analyzer._DYNAMO", dynamo):
            got = _find_similar_incidents("checkout-5xx")
        assert got != LEXICALLY_LARGEST_FIVE
        assert not set(got) & set(LEXICALLY_LARGEST_FIVE)

    def test_does_not_order_by_the_sort_key(self):
        """`ScanIndexForward` cannot mean recency here, so it must not be asked for."""
        dynamo, table = _dynamo([{"Items": SCRAMBLED}])
        with patch("src.agents.operations.aws.analyzer._DYNAMO", dynamo):
            _find_similar_incidents("checkout-5xx")
        assert "ScanIndexForward" not in table.query.call_args.kwargs

    def test_caps_the_returned_count(self):
        dynamo, _ = _dynamo([{"Items": SCRAMBLED}])
        with patch("src.agents.operations.aws.analyzer._DYNAMO", dynamo):
            assert len(_find_similar_incidents("checkout-5xx")) == _SIMILAR_LIMIT


class TestPaging:
    def test_follows_last_evaluated_key(self):
        """A server-side Limit of 5 was what made recency unanswerable."""
        pages = [
            {"Items": SCRAMBLED[:5], "LastEvaluatedKey": {"incident_id": "INC-BBBBBB05"}},
            {"Items": SCRAMBLED[5:]},
        ]
        dynamo, table = _dynamo(pages)
        with patch("src.agents.operations.aws.analyzer._DYNAMO", dynamo):
            assert _find_similar_incidents("checkout-5xx") == NEWEST_FIVE
        assert table.query.call_count == 2
        assert "ExclusiveStartKey" in table.query.call_args.kwargs

    def test_stops_at_the_cap_and_says_so(self):
        """Truncated ordering must be loud, not silent."""
        big = _rows([(f"INC-{n:08d}", f"2026-05-01T00:00:{n % 60:02d}Z") for n in range(_SIMILAR_SCAN_CAP)])
        pages = [{"Items": big, "LastEvaluatedKey": {"incident_id": "INC-99999999"}}]
        dynamo, table = _dynamo(pages)
        with patch("src.agents.operations.aws.analyzer._DYNAMO", dynamo), \
             patch("src.agents.operations.aws.analyzer.logger") as log:
            _find_similar_incidents("checkout-5xx")
        assert table.query.call_count == 1
        assert any("scan_capped" in str(c) for c in log.warning.call_args_list)


class TestDegradedRows:
    def test_rows_without_created_at_sort_last_and_do_not_crash(self):
        """Rows predating `created_at` must not take the newest slots."""
        rows = _rows([("INC-NEW", "2026-05-09T00:00:00Z")]) + [{"incident_id": "INC-OLD"}]
        dynamo, _ = _dynamo([{"Items": rows}])
        with patch("src.agents.operations.aws.analyzer._DYNAMO", dynamo):
            assert _find_similar_incidents("checkout-5xx") == ["INC-NEW", "INC-OLD"]

    def test_query_failure_returns_empty_not_raises(self):
        dynamo = MagicMock()
        dynamo.Table.side_effect = RuntimeError("no table")
        with patch("src.agents.operations.aws.analyzer._DYNAMO", dynamo):
            assert _find_similar_incidents("checkout-5xx") == []


class TestProviderParity:
    """The three lookups answer the same question and must take the same input.

    AWS carried a `severity` parameter its body never read while GCP and Azure
    never took one — a declared input with no meaning, and the shape that lets
    the three drift apart.
    """

    @pytest.mark.parametrize("module", [
        "src.agents.operations.aws.analyzer",
        "src.agents.operations.gcp.analyzer",
        "src.agents.operations.azure.analyzer",
    ])
    def test_same_signature(self, module):
        import importlib

        fn = importlib.import_module(module)._find_similar_incidents
        assert list(inspect.signature(fn).parameters) == ["alarm_name"]

    @pytest.mark.parametrize("module,marker", [
        ("src.agents.operations.gcp.analyzer", "created_at"),
        ("src.agents.operations.azure.analyzer", "created_at"),
    ])
    def test_the_other_two_still_order_on_time(self, module, marker):
        """Guards the providers that were already right, so a later edit can't quietly flip them."""
        import importlib

        assert marker in inspect.getsource(importlib.import_module(module)._find_similar_incidents)
