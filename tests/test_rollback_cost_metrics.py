"""A rolled-back deployment lost the cost panel it had before the rollback.

`record_deploy` attaches `cost_metrics`; `record_rollback` did not. Both write an
ACTIVITY row under the *same* deployment_id, and the dashboard's `mergeActivity`
unions the traces but takes every other field from the newest row. So the moment
a deployment was rolled back, the detail page stopped rendering tool-call,
reasoning and token counts entirely — directly above a trace that had just grown
to list both runs' tool calls. Nothing threw; the panel is conditional, so it
simply was not there.

Two halves, so two guards:
  1. the writer must produce the sub-metrics (it already had the steps),
  2. the reader must aggregate them across the rows it folds together, or the
     fixed writer would just report the rollback's cost as the deployment's.
"""

import ast
import json
import pathlib
import re

from src.agents.ai.deploy_recorder import record_deploy, record_rollback

REPO = pathlib.Path(__file__).resolve().parents[1]
ACTIVITY_DATA = REPO / "dashboard" / "src" / "lib" / "activity-data.ts"
SRC_AGENTS = REPO / "src" / "agents"


class _FakeTable:
    def __init__(self):
        self.items = []

    def put_item(self, Item):
        self.items.append(Item)


def _activity(table, deployment_id=None):
    rows = [i for i in table.items if i["PK"] == "ACTIVITY"]
    if deployment_id:
        rows = [i for i in rows if i.get("deployment_id") == deployment_id]
    return rows


# ---------------------------------------------------------------------------
# 1. The writer
# ---------------------------------------------------------------------------

class TestRollbackRecordsItsOwnCost:
    def _rollback(self, table, steps):
        return record_rollback(
            deployment_id="DEP-ABC12345",
            kind="deploy",
            cluster="platform-agent",
            service="orders-api",
            version="v1",
            provider="onprem",
            environment="production",
            model="local-qwen",
            action="rollback orders-api",
            summary="reverted to v1",
            steps=steps,
            ok=True,
            table=table,
        )

    def test_rollback_activity_carries_cost_metrics(self):
        table = _FakeTable()
        self._rollback(table, [{"tool": "rollback_service"}, {"tool": "validate_deployment"}])
        activity = _activity(table)[0]
        assert "cost_metrics" in activity, (
            "the rollback ACTIVITY row is the newest row for its deployment_id, so "
            "omitting this erases the panel rather than under-reporting it"
        )
        assert activity["cost_metrics"]["tool_calls_by_name"] == {
            "rollback_service": 1,
            "validate_deployment": 1,
        }
        assert activity["cost_metrics"]["tool_calls_total"] == 2

    def test_rollback_with_no_steps_reports_zero_not_absence(self):
        """Zeros are honest here — the panel is hidden on all-zero, and a rollback
        that ran no tools genuinely has nothing to show."""
        table = _FakeTable()
        self._rollback(table, [])
        metrics = _activity(table)[0]["cost_metrics"]
        assert metrics["tool_calls_total"] == 0
        assert metrics["total_tokens"] == 0

    def test_the_deployment_keeps_a_populated_row_after_being_rolled_back(self):
        """End to end over the two rows the detail page actually folds together."""
        table = _FakeTable()
        deploy_steps = [
            {"tool": "build_image", "args": {"service_name": "orders-api", "version": "v2"}},
            {"tool": "deploy_service", "args": {"service_name": "orders-api", "version": "v2"}},
        ]
        result = record_deploy(
            instruction="deploy orders-api v2",
            model="local-qwen",
            provider="onprem",
            summary="rolled out",
            steps=deploy_steps,
            ok=True,
            trace=[
                {"kind": "reasoning", "usage": {"input_tokens": 800, "output_tokens": 120}},
                *[{"kind": "tool", **s} for s in deploy_steps],
            ],
            table=table,
        )
        dep_id = result["deployment_id"]
        record_rollback(
            deployment_id=dep_id,
            kind="deploy",
            cluster="platform-agent",
            service="orders-api",
            version="v1",
            provider="onprem",
            environment="production",
            model="local-qwen",
            action="rollback orders-api",
            summary="reverted",
            steps=[{"tool": "rollback_service"}],
            ok=True,
            table=table,
        )
        rows = _activity(table, dep_id)
        assert len(rows) == 2
        assert all("cost_metrics" in r for r in rows), (
            "both rows feed one merged view; a row without the sub-metrics wins the "
            "merge by being newest"
        )
        # What the summed panel must come to, checked against the merged trace.
        total_tools = sum(r["cost_metrics"]["tool_calls_total"] for r in rows)
        trace_tools = sum(
            1 for r in rows for e in json.loads(r["trace"]) if e.get("kind") == "tool"
        )
        assert total_tools == trace_tools == 3


# ---------------------------------------------------------------------------
# 2. The invariant, derived from the reader's own selection rule
# ---------------------------------------------------------------------------

class TestEveryDeploymentScopedActivityRowCarriesCost:
    """Derived, not a list of functions.

    `deployment_id` is precisely what routes an ACTIVITY row into `mergeActivity`
    and onto the detail page, so that key — not the module it was written in — is
    what obliges a row to carry the sub-metrics. Rows without it (the route and
    provider-activity writers) never reach that page and are correctly exempt;
    adding the field there would create exactly the unconsumed field this repo
    keeps paying for. A new writer that does carry a deployment_id fails here.
    """

    def _activity_row_literals(self):
        rows = []
        for path in SRC_AGENTS.rglob("*.py"):
            if "cdk.out" in str(path):
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                for sub in ast.walk(node):
                    if not isinstance(sub, ast.Dict):
                        continue
                    pairs = {
                        k.value: v
                        for k, v in zip(sub.keys, sub.values)
                        if isinstance(k, ast.Constant) and isinstance(k.value, str)
                    }
                    pk = pairs.get("PK")
                    if isinstance(pk, ast.Constant) and pk.value == "ACTIVITY":
                        rows.append((f"{path.name}:{node.name}", set(pairs)))
        return rows

    def test_the_sweep_still_finds_the_activity_writers(self):
        """Guards the guard — an AST walk that matches nothing passes vacuously."""
        rows = self._activity_row_literals()
        assert len(rows) >= 4, f"expected the known ACTIVITY writers, found {rows}"

    def test_deployment_scoped_rows_carry_cost_metrics(self):
        offenders = [
            where
            for where, keys in self._activity_row_literals()
            if "deployment_id" in keys and "cost_metrics" not in keys
        ]
        assert not offenders, (
            f"{offenders} write an ACTIVITY row the deployment detail page merges, "
            "without the sub-metrics that page renders — being the newest row, it "
            "would blank the panel for the whole deployment"
        )


# ---------------------------------------------------------------------------
# 3. The reader must aggregate, not inherit
# ---------------------------------------------------------------------------

class TestMergeActivityAggregatesCost:
    """No TS runner in this repo, so this reads the source — same approach the
    incident projection guard uses. It is a structural check, not an execution:
    it asserts the merge derives the sub-metrics from every matched row rather
    than inheriting them from the newest one via the spread.
    """

    def _merge_body(self) -> str:
        src = ACTIVITY_DATA.read_text(encoding="utf-8")
        start = src.index("function mergeActivity")
        end = src.index("\n}", start)
        return src[start:end]

    def test_cost_metrics_is_set_explicitly_in_the_merge(self):
        body = self._merge_body()
        assert re.search(r"cost_metrics:\s*\w+\(", body), (
            "mergeActivity returns `{...latest}`; unless it overrides cost_metrics "
            "the panel shows only the newest row's numbers under a merged trace"
        )

    def test_the_aggregate_reads_every_matched_row(self):
        body = self._merge_body()
        call = re.search(r"cost_metrics:\s*(\w+)\((\w+)\)", body)
        assert call, "expected cost_metrics to be assigned from a call over the rows"
        _, argument = call.groups()
        assert argument == "matches", (
            f"the sub-metrics are aggregated over `{argument}`, but the trace right "
            "beside them unions `matches` — the two panels must describe the same rows"
        )

    def test_the_aggregate_sums_rather_than_picks(self):
        src = ACTIVITY_DATA.read_text(encoding="utf-8")
        start = src.index("function sumCostMetrics")
        body = src[start : src.index("\n}\n", start)]
        assert "reduce" in body, "expected the totals to be summed across rows"
        assert "tool_calls_by_name" in body, "the per-tool breakdown must merge too"
