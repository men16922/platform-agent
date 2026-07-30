"""A deploy lands in a namespace; nothing recorded which one, so rollback guessed.

The row a deploy writes says which cluster, which service, which version and which
tier — but not which *namespace*. It is the one field the executor definitely knew:
`ServiceSpec.namespace` decided the `kubectl apply --namespace` that created the
workload, and the adapter returned it. It just was never persisted.

Every layer downstream then had to invent it, and each one picked the same
plausible literal:

  * `deployments-control.tsx` sent `namespace: "default"` on the rollback payload
  * the Next.js rollback route destructured `namespace = "default"`
  * `RollbackRequest.namespace` defaulted to `"default"`
  * `ServiceSpec.namespace` defaults to `"default"` — the *legitimate* one, because
    that is genuinely where kubectl puts a workload nobody placed

So a service deployed into a tenant namespace rolls back in `default`. That does
not fail loudly: `kubectl rollout undo` either reports the deployment missing, or —
worse — finds a same-named deployment in `default` and reverts *that* one. The
button says it rolled back the row you clicked.

Two rules, and the second is why this is a `namespace` test and not an
`environment` one:

  1. **Record the resolved fact.** Unlike a tier (D36), the namespace is not
     unknown at write time — the deploy already happened somewhere. Absence here
     means the row predates this, not that nobody chose.
  2. **Resolve it exactly once.** `ServiceSpec` is the resolution point. Any other
     layer carrying a `"default"` literal is a second answer to a question that
     already has one, and the two drift the moment tenancy puts a deploy anywhere
     else.

Also guarded here: the D36 tier default that survived at a *third* boundary. That
guard enumerated the two boundaries it knew (the FastAPI request model, the
dashboard mapper) and the Next.js route in between kept `environment =
"production"` — writing, on the rollback path, exactly the tier D36 stopped the
deploy path from inventing. The sweep below is derived over the whole read/route
surface instead of naming files, so a fourth boundary fails too.
"""

import pathlib
import re

from src.agents.ai.deploy_recorder import (
    record_cluster_teardown,
    record_deploy,
    record_rollback,
)

REPO = pathlib.Path(__file__).resolve().parents[1]
DASHBOARD = REPO / "dashboard" / "src"


class _FakeTable:
    def __init__(self, items=None):
        self.items = list(items or [])

    def put_item(self, Item):
        self.items.append(Item)


def _deploy_rows(table):
    return [i for i in table.items if i["PK"] == "DEPLOY"]


def _latest_deploy(table):
    return _deploy_rows(table)[-1]


# What the router hands the recorder: the preferred one-call tool, whose result
# reports the namespace the cluster step actually applied into.
def _steps(namespace="acme-prod-app", *, in_args=False, in_result=True):
    args = {"service_name": "orders-api", "version": "v1.4.2"}
    result = {"ok": True, "endpoint": "http://orders-api"}
    if in_args:
        args["namespace"] = namespace
    if in_result:
        result["namespace"] = namespace
    return [{"tool": "deploy_service", "args": args, "result": result}]


class TestTheRowRecordsWhereItLanded:
    def test_namespace_from_the_tool_result(self):
        """The result is preferred over the args: it is what the adapter *did*."""
        table = _FakeTable()
        record_deploy(
            instruction="deploy orders-api for acme",
            model="local-qwen",
            provider="onprem",
            summary="ok",
            steps=_steps("acme-prod-app"),
            ok=True,
            table=table,
        )
        row = _latest_deploy(table)
        assert row.get("namespace") == "acme-prod-app", (
            "the DEPLOY row does not say which namespace the workload went into, so "
            "every rollback path downstream has to guess — and they all guess 'default'"
        )

    def test_namespace_from_the_args_when_the_result_is_silent(self):
        """`deploy_to_cluster` reports it; a step that only took it still knew it."""
        table = _FakeTable()
        record_deploy(
            instruction="deploy orders-api for acme",
            model="local-qwen",
            provider="onprem",
            summary="ok",
            steps=_steps("acme-prod-app", in_args=True, in_result=False),
            ok=True,
            table=table,
        )
        assert _latest_deploy(table).get("namespace") == "acme-prod-app"

    def test_a_run_that_never_named_one_records_no_namespace(self):
        """Not the same as recording "default".

        A provisioning run has no namespace at all. Stamping the kubectl default on
        it would make the row assert a placement that never happened — the failure
        mode this whole milestone is about.
        """
        table = _FakeTable()
        record_deploy(
            instruction="provision a kind cluster",
            model="local-qwen",
            provider="onprem",
            summary="ok",
            steps=[{"tool": "provision_cluster", "args": {"cluster_name": "platform-agent"}, "result": {"success": True}}],
            ok=True,
            table=table,
        )
        row = _latest_deploy(table)
        assert "namespace" not in row, f"provision row claims namespace={row.get('namespace')!r}"

    def test_the_deploy_half_of_a_composite_run_keeps_it(self):
        """provision+deploy splits into two rows; only the deploy half has a namespace."""
        table = _FakeTable()
        steps = [
            {"tool": "provision_cluster", "args": {"cluster_name": "platform-agent"}, "result": {"success": True}},
            *_steps("acme-prod-app"),
        ]
        record_deploy(
            instruction="stand up a cluster and deploy orders-api",
            model="local-qwen",
            provider="onprem",
            summary="ok",
            steps=steps,
            ok=True,
            table=table,
        )
        rows = {r["type"]: r for r in _deploy_rows(table)}
        assert rows["deploy"].get("namespace") == "acme-prod-app"
        assert "namespace" not in rows["provision"], "the provisioning row borrowed the app's namespace"


class TestSupersedeDoesNotEraseIt:
    """The single-row lifecycle rewrites the row in place, so a rollback that omits
    a field deletes it — `cost_metrics` already cost us this exact lesson. Here the
    stake is higher: the field that goes missing is the one the *next* rollback
    needs to target the right namespace, so one rollback silently re-arms the bug.
    """

    def test_rollback_carries_the_namespace_forward(self):
        table = _FakeTable()
        record_rollback(
            deployment_id="DEP-ABC12345",
            kind="deploy",
            cluster="platform-agent",
            service="orders-api",
            version="previous",
            provider="onprem",
            environment=None,
            namespace="acme-prod-app",
            model="local-qwen",
            action="rollback orders-api",
            summary="reverted",
            steps=[{"tool": "rollback_deployment", "args": {"namespace": "acme-prod-app"}, "result": {"success": True}}],
            ok=True,
            table=table,
        )
        row = _latest_deploy(table)
        assert row.get("namespace") == "acme-prod-app", (
            "the superseding row dropped the namespace — the row it replaced had it, "
            "so the deployment just forgot where it lives"
        )

    def test_a_natural_language_rollback_recovers_it_from_the_row(self):
        """The NL path is given no namespace; the row being superseded has one."""
        table = _FakeTable(
            [
                {
                    "PK": "DEPLOY",
                    "deployment_id": "DEP-ABC12345",
                    "type": "deploy",
                    "service": "orders-api",
                    "version": "v1.4.2",
                    "cluster": "platform-agent",
                    "namespace": "acme-prod-app",
                    "status": "success",
                    "created_at": "2026-07-30T00:00:00Z",
                }
            ]
        )
        record_deploy(
            instruction="roll back orders-api",
            model="local-qwen",
            provider="onprem",
            summary="reverted",
            steps=[{"tool": "rollback_deployment", "args": {"service_name": "orders-api"}, "result": {"success": True}}],
            ok=True,
            table=table,
        )
        row = _latest_deploy(table)
        assert row["deployment_id"] == "DEP-ABC12345", "did not supersede the original row"
        assert row.get("namespace") == "acme-prod-app", (
            "an NL rollback wrote the row without the namespace the original carried"
        )

    def test_teardown_cascade_keeps_each_app_in_its_own_namespace(self):
        """Apps on one cluster can live in different namespaces; the cascade must not
        flatten them onto one (or onto none)."""
        table = _FakeTable(
            [
                {
                    "PK": "DEPLOY", "deployment_id": "DEP-1", "type": "provision", "service": "platform-agent",
                    "version": "kind", "cluster": "platform-agent", "status": "success", "created_at": "2026-07-30T00:00:00Z",
                },
                {
                    "PK": "DEPLOY", "deployment_id": "DEP-2", "type": "deploy", "service": "orders-api",
                    "version": "v1", "cluster": "platform-agent", "namespace": "acme-prod-app",
                    "status": "success", "created_at": "2026-07-30T00:01:00Z",
                },
                {
                    "PK": "DEPLOY", "deployment_id": "DEP-3", "type": "deploy", "service": "billing-api",
                    "version": "v2", "cluster": "platform-agent", "namespace": "globex-prod-app",
                    "status": "success", "created_at": "2026-07-30T00:02:00Z",
                },
            ]
        )
        record_cluster_teardown(
            cluster="platform-agent",
            provider="onprem",
            environment=None,
            model="local-qwen",
            summary="cluster gone",
            steps=[{"tool": "teardown_cluster", "args": {"cluster_name": "platform-agent"}, "result": {"success": True}}],
            ok=True,
            table=table,
        )
        by_id = {}
        for row in _deploy_rows(table):
            by_id[row["deployment_id"]] = row  # later writes win, as the read layer does
        assert by_id["DEP-2"].get("namespace") == "acme-prod-app"
        assert by_id["DEP-3"].get("namespace") == "globex-prod-app"
        assert "namespace" not in by_id["DEP-1"], "the provisioning row picked up an app's namespace"


class TestOnlyOneLayerResolvesIt:
    """Derived over the surface, not a list of the layers we happen to remember.

    The D36 guard named two boundaries and the third one kept its default. So this
    reads every dashboard route/component and every request model, and fails on any
    literal default for a field whose absence is meaningful.
    """

    #: `ServiceSpec`/`DeployResult` — the one place the kubectl default belongs.
    ALLOWED = {DASHBOARD.parent.parent / "src" / "agents" / "adapters" / "deployment" / "base.py"}

    def _code_lines(self):
        """Every dashboard source line, minus comments.

        Comments are stripped because these guards must be describable in prose
        next to the code they protect — a sweep that trips on its own explanation
        forces the fix to be undocumented.
        """
        for pattern in ("*.ts", "*.tsx"):
            for path in DASHBOARD.rglob(pattern):
                if "node_modules" in str(path):
                    continue
                for n, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                    line = re.sub(r"(//|/\*|\*).*$", "", raw)
                    if line.strip():
                        yield path, n, line

    def test_no_dashboard_layer_defaults_the_namespace(self):
        offenders = [
            f"{p.relative_to(REPO)}:{n}: {line.strip()}"
            for p, n, line in self._code_lines()
            if re.search(r"""namespace\s*[:=]\s*["']default["']""", line)
        ]
        assert not offenders, (
            "these substitute the kubectl default for the namespace the deployment "
            f"actually landed in, so a rollback targets the wrong one: {offenders}"
        )

    def test_no_dashboard_layer_defaults_the_tier(self):
        """D36 at the boundaries its own guard did not cover.

        That guard enumerated two (the FastAPI request model, the dashboard mapper).
        This one is derived over the surface, and it found two more the moment it
        ran: the rollback route and the trigger route.
        """
        offenders = [
            f"{p.relative_to(REPO)}:{n}: {line.strip()}"
            for p, n, line in self._code_lines()
            if re.search(r"""environment\s*=\s*["'](production|staging|dev|prod)["']""", line)
        ]
        assert not offenders, (
            "a tier is being invented for a request that declared none — and this one "
            f"is on a write path, so it lands in the durable row (D36): {offenders}"
        )

    def test_the_rollback_request_model_does_not_default_the_namespace(self):
        src = (REPO / "src" / "agents" / "ai" / "local_deploy_api.py").read_text(encoding="utf-8")
        for m in re.finditer(r"namespace:\s*([^\n=]+)=\s*Field\(([^,)]+)", src):
            annotation, default = m.group(1).strip(), m.group(2).strip()
            assert default == "None", (
                f"a request model defaults namespace to {default} — the caller that "
                "knows the answer is the row, and it is now recorded"
            )
            assert "None" in annotation, f"namespace must be optional, got {annotation}"

    def test_the_preferred_deploy_tool_reports_where_it_landed(self):
        """`deploy_service` is the tool the prompt tells the model to prefer. If its
        result omits the namespace, the recorder can only fall back to whatever the
        model happened to pass in — and the model usually passes nothing."""
        from src.agents.ai import local_deployer

        calls = {}

        def fake_deploy_to_cluster(*args, **kwargs):
            calls["namespace"] = kwargs.get("namespace")
            return {"status": "success", "deployment_id": "acme-prod-app/orders-api",
                    "namespace": kwargs.get("namespace"), "endpoint": "http://x", "error": None}

        originals = (local_deployer.build_image, local_deployer.push_image,
                     local_deployer.deploy_to_cluster, local_deployer.validate_deployment)
        try:
            local_deployer.build_image = lambda *a, **k: {"success": True, "image_tag": "t"}
            local_deployer.push_image = lambda *a, **k: {"success": True, "image_uri": "u"}
            local_deployer.deploy_to_cluster = fake_deploy_to_cluster
            local_deployer.validate_deployment = lambda *a, **k: {"healthy": True, "checks_passed": 3, "checks_total": 3}
            out = local_deployer.deploy_service("orders-api", "v1.4.2", namespace="acme-prod-app")
        finally:
            (local_deployer.build_image, local_deployer.push_image,
             local_deployer.deploy_to_cluster, local_deployer.validate_deployment) = originals

        assert calls["namespace"] == "acme-prod-app"
        assert out.get("namespace") == "acme-prod-app", (
            "deploy_service does not report the namespace it deployed into, so the "
            "recorded row cannot state it either"
        )

    def test_the_read_model_documents_the_field(self):
        """The doc nobody imports (M13 ⑪) — kept honest because it is derived-checked
        in tests/test_activity_read_model_matches_writers.py."""
        src = (DASHBOARD / "lib" / "activity-model.ts").read_text(encoding="utf-8")
        assert re.search(r"\bnamespace\?:\s*string", src), (
            "the read model does not declare `namespace`, so the next person reading "
            "it will conclude the row cannot answer 'where did this land'"
        )

    def test_the_mapper_surfaces_it(self):
        src = (DASHBOARD / "lib" / "activity-data.ts").read_text(encoding="utf-8")
        m = re.search(r"namespace:\s*typeof item\.namespace[^\n]*", src)
        assert m, "the deployment mapper drops `namespace`, so no view or action can use it"
        assert "undefined" in m.group(0), (
            f"the mapper substitutes a namespace for a missing one: {m.group(0).strip()}"
        )
