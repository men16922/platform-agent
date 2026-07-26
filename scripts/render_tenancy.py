"""Render soft-tier tenancy objects for one tenant/env from the registry.

Read-only. Prints YAML to stdout; applying is a separate, deliberate act.

The one thing this refuses to do quietly: report success when the quota will not
be enforced. The Capsule ``Tenant`` is the only object here that bounds anything
(scope: Tenant, aggregated across the tenant's namespaces). Without the Capsule
CRD installed, `kubectl apply` creates the namespaces and RBAC, silently drops
nothing — and leaves the tenant unbounded on a shared cluster while every view
still shows the declared quota. So the CRD is checked, and its absence is a
non-zero exit with the namespaces still printed.

Usage:
  python scripts/render_tenancy.py <tenant> -e <env> [--service-account NAME] [--check]

The same rule applies to data-plane isolation: NetworkPolicies are rendered only for
substrates where enforcement was *proven* by experiment, and their absence is
reported rather than left for someone to infer from a manifest they did not read.

Exit codes:
  0 = rendered, and the cluster can enforce everything rendered
  1 = rendered, but something declared will NOT be enforced here — the quota
      (Capsule CRD absent) or data-plane isolation (unproven substrate)
  2 = could not render (unknown tenant/env, or a tier without namespace tenancy)
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.platform.registry import load_registry  # noqa: E402
from src.agents.platform.tenancy import (  # noqa: E402
    UnsupportedTier,
    namespaces_for,
    network_policies_apply_to,
    render_tenancy,
    unbounded_soft_tenants,
)

CAPSULE_CRD = "tenants.capsule.clastix.io"


def _capsule_installed() -> bool | None:
    """True/False, or None when we could not ask the cluster at all."""
    try:
        proc = subprocess.run(
            ["kubectl", "get", "crd", CAPSULE_CRD],
            capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return proc.returncode == 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tenant")
    parser.add_argument("-e", "--env", required=True)
    parser.add_argument("--service-account", default="platform-agent")
    parser.add_argument("--check", action="store_true",
                        help="report enforceability only; print no manifests")
    args = parser.parse_args()

    registry = load_registry()
    try:
        tenant = registry.tenant(args.tenant)
    except KeyError:
        print(f"ERROR: no tenant {args.tenant!r} in the registry", file=sys.stderr)
        return 2

    if not namespaces_for(tenant, args.env):
        print(
            f"ERROR: tenant {args.tenant!r} has no env {args.env!r} "
            f"(known: {', '.join(sorted(tenant.environments)) or 'none'})",
            file=sys.stderr,
        )
        return 2

    try:
        objects = render_tenancy(
            registry, args.tenant, args.env, service_account=args.service_account
        )
    except UnsupportedTier as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if not args.check:
        print(yaml.safe_dump_all(objects, sort_keys=False))

    kinds = [o["kind"] for o in objects]
    print(
        f"# {args.tenant}/{args.env}: "
        f"{kinds.count('Namespace')} namespace(s), "
        f"{kinds.count('Role')} role(s), "
        f"{kinds.count('NetworkPolicy')} network policy(ies), "
        f"{'1 Capsule Tenant' if 'Tenant' in kinds else 'NO quota object'}",
        file=sys.stderr,
    )

    unbounded = unbounded_soft_tenants(registry)
    if unbounded:
        print(
            f"# WARNING: soft-tier tenants with no declared quota: {', '.join(unbounded)}",
            file=sys.stderr,
        )

    # A missing NetworkPolicy is not a rendering bug — it is a property of the
    # substrate, and the only failure mode worth shouting about is someone reading
    # "tenancy applied" as "tenants cannot reach each other".
    substrate = tenant.environments[args.env].substrate
    if not network_policies_apply_to(tenant, args.env):
        print(
            f"# NO DATA-PLANE ISOLATION: substrate {substrate!r} is not in the proven-"
            "enforcing set,\n"
            "#   so no NetworkPolicy is rendered. Any pod on that cluster can reach these\n"
            "#   namespaces. Prove enforcement first, then add the substrate:\n"
            "#     python scripts/verify_netpol_enforcement.py   # must print ENFORCED",
            file=sys.stderr,
        )
        enforcement_gap = True
    else:
        enforcement_gap = False

    if "Tenant" not in kinds:
        print(
            "# The registry declares no quota for this tenant, so nothing here bounds it.",
            file=sys.stderr,
        )
        return 1

    installed = _capsule_installed()
    if installed is None:
        print("# CANNOT VERIFY: no reachable cluster to check the Capsule CRD against.",
              file=sys.stderr)
        return 1
    if not installed:
        print(
            f"# QUOTA WILL NOT BE ENFORCED: CRD {CAPSULE_CRD} is not installed.\n"
            "#   `kubectl apply` would create the namespaces and RBAC and leave the\n"
            "#   tenant unbounded on a shared cluster, while the registry and every\n"
            "#   view still show the declared quota. Install Capsule first.",
            file=sys.stderr,
        )
        return 1
    return 1 if enforcement_gap else 0


if __name__ == "__main__":
    raise SystemExit(main())
