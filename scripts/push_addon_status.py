"""Spoke-side agent: read THIS cluster's add-on status and push it to the hub.

Runs inside the cluster it reports on (a CronJob or a loop next to the on-prem
stack), using that cluster's own credentials and nothing else. The hub never calls
back, which is why it can hold zero spoke credentials — see
src/agents/platform/collector.py for the trust argument.

    PLATFORM_PUSH_KEY=<the key for this tenant/env> \
    python scripts/push_addon_status.py --tenant acme --env dev \
        --hub http://127.0.0.1:8077 [--once|--interval 60]

Exit codes: 0 = pushed, 1 = hub rejected or unreachable, 2 = cannot render a report.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.platform.collector import (  # noqa: E402
    build_report,
    read_applications,
    sign,
)
from src.agents.platform.registry import load_registry  # noqa: E402

PUSH_KEY_ENV = "PLATFORM_PUSH_KEY"


def push_once(
    hub: str, tenant, env_name: str, key: str, *, scope_of=None, timeout: int = 15
) -> tuple[int, str]:
    """One read + one push. Returns (exit code, human-readable line)."""
    applications = read_applications()
    # An empty read is ambiguous — no ArgoCD, no permission, or genuinely nothing
    # deployed — so it is reported as "not observed" (UNKNOWN) rather than as an
    # empty cluster (MISSING for every add-on). Claiming a false outage is as bad
    # as hiding a real one, and the hub cannot tell the difference after the fact.
    report = build_report(
        tenant, env_name, applications, now=time.time(),
        observed=bool(applications), scope_of=scope_of,
    )
    payload = report.to_dict()
    request = urllib.request.Request(
        f"{hub.rstrip('/')}/api/platform/status",
        data=json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-Platform-Signature": sign(payload, key),
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return 1, f"hub rejected the report: {exc.code} {exc.read().decode('utf-8')[:200]}"
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        return 1, f"hub unreachable: {exc}"

    observed = sum(1 for row in report.statuses if row.health_state.value != "unknown")
    return 0, (
        f"pushed {body.get('rows', 0)} row(s) for {report.identity} "
        f"({observed} observed, {len(report.statuses) - observed} unknown)"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--env", required=True)
    parser.add_argument("--hub", default=os.getenv("PLATFORM_HUB_URL", "http://127.0.0.1:8077"))
    parser.add_argument("--interval", type=int, default=0,
                        help="seconds between pushes; 0 = push once and exit")
    args = parser.parse_args()

    key = os.getenv(PUSH_KEY_ENV, "").strip()
    if not key:
        print(f"ERROR: {PUSH_KEY_ENV} is unset — the hub authenticates by key, and an "
              "unsigned report is not a report", file=sys.stderr)
        return 2

    registry = load_registry()
    try:
        tenant = registry.tenant(args.tenant)
    except KeyError:
        print(f"ERROR: no tenant {args.tenant!r} in the registry", file=sys.stderr)
        return 2
    if args.env not in tenant.environments:
        print(f"ERROR: tenant {args.tenant!r} has no env {args.env!r}", file=sys.stderr)
        return 2

    while True:
        code, line = push_once(args.hub, tenant, args.env, key, scope_of=registry.scope_of)
        print(f"[{time.strftime('%H:%M:%S')}] {line}", file=sys.stderr if code else sys.stdout)
        if args.interval <= 0:
            return code
        # A failed push is not fatal to the loop: the hub going away must not stop
        # the agent, or recovery would need a human on every spoke.
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
