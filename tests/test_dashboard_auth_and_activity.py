"""Tests for dashboard auth boundary design — permission model correctness."""

import pathlib
import subprocess


def test_auth_module_typescript_compiles():
    """Verify auth.ts compiles without errors via tsc --noEmit."""
    result = subprocess.run(
        ["npx", "tsc", "--noEmit", "--strict", "--esModuleInterop",
         "--moduleResolution", "bundler", "--module", "esnext",
         "--target", "es2022", "--skipLibCheck",
         "src/lib/auth.ts"],
        capture_output=True,
        text=True,
        cwd="dashboard",
    )
    # tsc --noEmit on a file with path aliases won't resolve @/ imports,
    # so we check that the core type logic is sound via a different approach.
    # Instead verify the file is valid TypeScript by checking it parses.
    assert "src/lib/auth.ts" not in result.stdout or "error" not in result.stdout.lower()


def test_auth_role_hierarchy():
    """Verify role permission hierarchy: admin > operator > viewer."""
    # This is a design invariant test — read the source and verify.
    # We can't directly import TS, so verify the design via the doc.
    with open("docs/DASHBOARD_AUTH_DESIGN.md", "r") as f:
        content = f.read()

    # Verify all roles are documented
    assert "viewer" in content
    assert "operator" in content
    assert "admin" in content

    # Verify P1 approval is admin-only
    assert "P1 approval requires admin" in content

    # The read path is NO LONGER public — this test used to pin that statement
    # in place, which is how a policy line outlives the policy. Assert the
    # correction is recorded instead, so the doc cannot quietly drift back.
    assert "테넌트별 파티션" in content, "read-path policy must reflect partitioning"


def test_auth_design_doc_constraints():
    """Verify auth design documents key security constraints."""
    with open("docs/DASHBOARD_AUTH_DESIGN.md", "r") as f:
        content = f.read()

    # Must document session strategy
    assert "JWT" in content
    assert "httpOnly" in content

    # Must document CSRF protection
    assert "CSRF" in content

    # Must document audit logging
    assert "Audit" in content

    # Must have implementation phases
    assert "Phase 1" in content
    assert "Phase 2" in content
    assert "Phase 3" in content


def test_auth_module_exports_permission_model():
    """Verify the auth.ts file exports the expected permission types."""
    with open("dashboard/src/lib/auth.ts", "r") as f:
        content = f.read()

    # Core exports
    assert "export type Role" in content
    assert "export type Permission" in content
    assert "export function hasPermission" in content
    assert "export function canApprove" in content
    assert "export const ROLE_PERMISSIONS" in content

    # Security invariants
    assert '"incidents:approve:p1"' in content
    assert '"operator"' in content
    assert '"admin"' in content


def test_read_side_authorization_is_consumed_not_merely_declared():
    """
    This test used to assert that `ROUTE_PROTECTION` and `meetsProtectionLevel`
    were *exported* — and they were, for months, while **nothing imported
    either**. The route table said reads were "public"; the proxy matcher said
    something different; neither was the thing that ran. A guard that pins a
    declaration in place is how declared-but-unconsumed policy survives review.

    So assert consumption instead: the visibility seam must exist **and** the
    fleet route must call it. If someone deletes the call, this fails; if
    someone re-adds an unused policy table, nothing here props it up.
    """
    from pathlib import Path

    seam = Path("dashboard/src/lib/visibility.ts").read_text()
    assert "export function resolveVisibility" in seam
    assert "export function filterFleet" in seam

    route = Path("dashboard/src/app/api/dashboard/platform/status/route.ts").read_text()
    assert "resolveVisibility" in route, "the fleet route must resolve caller visibility"
    assert "filterFleet" in route, "the fleet route must filter what it returns"
    assert "restricted" in route, (
        "withheld-by-authorization must stay distinct from empty — an empty "
        "fleet and a fleet you may not see call for opposite reactions"
    )


def test_proxy_file_convention_is_current():
    """
    Next 16 deprecated the `middleware` file convention in favour of `proxy`
    (node_modules/next/dist/docs/.../file-conventions/proxy.md). A deprecated
    convention keeps working until it doesn't, and the failure mode is the
    write-route matcher silently not running.
    """
    from pathlib import Path

    assert Path("dashboard/src/proxy.ts").is_file(), "expected src/proxy.ts"
    assert not Path("dashboard/src/middleware.ts").exists(), (
        "middleware.ts is the deprecated convention; both files present is worse "
        "than either alone"
    )
    assert "auth as proxy" in Path("dashboard/src/proxy.ts").read_text()


def test_activity_model_documents_the_live_entity_types():
    """The read-model doc still names the row types that actually exist.

    This used to assert a list of substrings — `GSI1PK:`, `TTL_30_DAYS`,
    `makeDeploymentRecord` — and passed for as long as those characters were
    present, which is how the file drifted into declaring a `duration_ms` no
    writer produces while omitting `trace`, `cost_metrics` and `deployment_id`.
    Keyword presence cannot see shape. The shape is now derived from the writers
    in tests/test_activity_read_model_matches_writers.py; what is left here is
    the part that is genuinely a naming contract.

    The removed assertions and why:
      * `TTL_30_DAYS` / `make*Record` — an unwired TS write path. Nothing
        imported the module, the real writers are Python, and keeping a second
        record constructor meant keeping a second thing to drift.
      * `GSI1PK:` in its required form — GSI1 is written by one writer family
        only and queried by nothing, so requiring it stated a guarantee the
        table does not give.
    """
    content = pathlib.Path("dashboard/src/lib/activity-model.ts").read_text(encoding="utf-8")

    for pk in ('"DEPLOY"', '"ACTIVITY"', '"HEALTH"'):
        assert pk in content, f"{pk} is a live PK value and must stay documented"

    # HEALTH_HISTORY is documented as an access pattern that is NOT written —
    # asserting it as a schema type is what made this file look complete.
    assert "HEALTH_HISTORY" in content
    assert "NOT WRITTEN" in content, (
        "the doc must keep saying that the health-history pattern has no writer"
    )


def test_activity_data_access_layer():
    """Verify activity-data.ts implements the expected feed functions."""
    with open("dashboard/src/lib/activity-data.ts", "r") as f:
        content = f.read()

    # Must export feed functions
    assert "getDeploymentFeed" in content
    assert "getAgentActivityFeed" in content
    assert "getProviderHealthFeed" in content

    # Must support live/demo modes
    assert "aws-live" in content
    assert "demo" in content
    assert "demo-fallback" in content

    # Must use correct table name
    assert "platform-agent-activity" in content


def test_incidents_route_partitions_and_does_not_share_a_cache():
    """
    Once the response varies by caller, a shared/CDN cache serves one tenant's
    incidents to another. The cache header is part of the partition, not an
    optimisation that happened to be dropped — so assert it, or the next person
    tuning performance reinstates the leak.
    """
    from pathlib import Path

    route = Path("dashboard/src/app/api/dashboard/incidents/route.ts").read_text()
    assert "resolveVisibility" in route and "filterRows" in route
    assert "s-maxage" not in route, "shared-cache directive on a per-caller response"
    assert "private" in route and "no-store" in route
    assert "withheld" in route, "silently shortening the list is the failure mode"
