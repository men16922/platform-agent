"""The deployment tier was invented at two layers, with two different answers.

The dashboard's natural-language deploy sends `{instruction, model, provider}` —
no environment at all. `DeployRequest.environment` defaulted to `"dev"`, so every
row that path wrote claimed a tier the operator never chose. And when the value
was missing further along, the dashboard's own mapper defaulted it to
`"production"`. One unknown, two confident and contradictory guesses, neither of
them the operator's.

Absence is now preserved end to end (DECISIONS D36): the boundary stops
defaulting, the writer stores the key only when a tier was declared, and the read
side renders nothing rather than a tier.

This is the same rule `tenant`, `triggered_at` and `resolved_at` already follow
here, and for the same reason: "not declared" is a different fact from any
particular value, and only one of them can be acted on.
"""

import pathlib
import re

from src.agents.ai.deploy_recorder import record_deploy, record_rollback

REPO = pathlib.Path(__file__).resolve().parents[1]
DASHBOARD = REPO / "dashboard" / "src"


class _FakeTable:
    def __init__(self):
        self.items = []

    def put_item(self, Item):
        self.items.append(Item)


def _deploy_row(table):
    return next(i for i in table.items if i["PK"] == "DEPLOY")


STEPS = [{"tool": "deploy_service", "args": {"service_name": "orders-api", "version": "v1"}}]


class TestTheWriterStoresOnlyWhatWasDeclared:
    def test_no_environment_declared_means_no_attribute(self):
        table = _FakeTable()
        record_deploy(
            instruction="deploy orders-api",
            model="local-qwen",
            provider="onprem",
            summary="ok",
            steps=STEPS,
            ok=True,
            table=table,
        )
        row = _deploy_row(table)
        assert "environment" not in row, (
            f"the row claims environment={row.get('environment')!r}, which no caller "
            "declared — this is the default the NL deploy path used to stamp on every row"
        )

    def test_a_declared_tier_is_kept_verbatim(self):
        table = _FakeTable()
        record_deploy(
            instruction="deploy orders-api",
            model="local-qwen",
            provider="onprem",
            summary="ok",
            steps=STEPS,
            ok=True,
            environment="production",
            table=table,
        )
        assert _deploy_row(table)["environment"] == "production"

    def test_empty_string_is_absence_not_a_tier(self):
        """A form that submits "" declared nothing; it did not declare "" as a tier."""
        table = _FakeTable()
        record_deploy(
            instruction="deploy orders-api",
            model="local-qwen",
            provider="onprem",
            summary="ok",
            steps=STEPS,
            ok=True,
            environment="",
            table=table,
        )
        assert "environment" not in _deploy_row(table)

    def test_rollback_follows_the_same_rule(self):
        table = _FakeTable()
        record_rollback(
            deployment_id="DEP-ABC12345",
            kind="deploy",
            cluster="platform-agent",
            service="orders-api",
            version="v1",
            provider="onprem",
            environment=None,
            model="local-qwen",
            action="rollback orders-api",
            summary="reverted",
            steps=[{"tool": "rollback_service"}],
            ok=True,
            table=table,
        )
        assert "environment" not in _deploy_row(table)


class TestNoLayerReinventsIt:
    """Structural, on the two boundaries that each had their own default.

    No TS runner here, so the read side is checked by reading it — the same
    approach the incident projection guard uses.
    """

    def test_the_http_boundary_does_not_default_the_tier(self):
        src = (REPO / "src" / "agents" / "ai" / "local_deploy_api.py").read_text(encoding="utf-8")
        for m in re.finditer(r"environment:\s*([^\n=]+)=\s*Field\(([^,)]+)", src):
            annotation, default = m.group(1).strip(), m.group(2).strip()
            assert default == "None", (
                f"a request model defaults environment to {default} — the dashboard's "
                "NL deploy sends none, so this stamps a tier nobody chose"
            )
            assert "None" in annotation, f"environment must be optional, got {annotation}"

    def test_the_dashboard_mapper_does_not_default_the_tier(self):
        src = (DASHBOARD / "lib" / "activity-data.ts").read_text(encoding="utf-8")
        m = re.search(r"environment:\s*typeof item\.environment[^\n]*", src)
        assert m, "could not locate the environment mapping"
        line = m.group(0)
        assert "undefined" in line, (
            f"the mapper still substitutes a tier for a missing one: {line.strip()}"
        )
        assert '"production"' not in line and '"dev"' not in line, line.strip()

    def test_no_render_site_prints_a_bare_environment(self):
        """Derived, not a list of files: any `.environment` interpolated straight
        into JSX would render `undefined` now that the field is optional."""
        offenders = []
        for path in list(DASHBOARD.rglob("*.tsx")):
            if "node_modules" in str(path):
                continue
            for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if re.search(r"\{\s*\w+\.environment\s*\}", line):
                    offenders.append(f"{path.relative_to(REPO)}:{n}")
        assert not offenders, (
            f"{offenders} render `.environment` with no absence branch — with the "
            "field optional these print nothing or 'undefined' instead of saying "
            "no tier was declared"
        )
