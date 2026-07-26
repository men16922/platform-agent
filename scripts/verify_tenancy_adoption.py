"""Has the cluster actually ADOPTED the tenancy the registry declares?

Exists because of a disaster-recovery drill. Rebuilding a tenant from the registry
recreated every object correctly — Tenant, Namespace with identical labels, RBAC,
NetworkPolicy — and for the first ~10 seconds the Capsule Tenant still reported
``NAMESPACE COUNT = 0``. During that window the namespace exists, carries the
tenant label, looks finished in every view, and **its quota binds nothing**: a
workload admitted then is unbounded on a shared cluster.

That window closes on its own. The problem is that nothing distinguishes "closing"
from "never going to close" — which is the state the very first Phase 2 apply was
stuck in, when Capsule refused to adopt an admin-created namespace at all. Both
look identical at a glance, and the glance is what people take before declaring a
recovery complete.

So this asks the question directly, per tenant/env:

    declared namespaces (registry)  ==  namespaces the tenant actually owns?
    is a ResourceQuota present, and does it match the declared bound?

Usage:
  python scripts/verify_tenancy_adoption.py [--tenant NAME] [--wait 60]

Exit codes: 0 = adopted and bounded, 1 = a gap remains, 2 = cannot check.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.platform.registry import IsolationTier, load_registry  # noqa: E402
from src.agents.platform.tenancy import (  # noqa: E402
    CAPSULE_TENANT_LABEL,
    namespaces_for,
)


def _kubectl_json(*args: str) -> dict | None:
    try:
        proc = subprocess.run(
            ["kubectl", *args, "-o", "json"], capture_output=True, text=True, timeout=30
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    try:
        return json.loads(proc.stdout)
    except ValueError:
        return None


def _check(tenant, env_name: str) -> tuple[bool, list[str]]:
    """(adopted, findings) for one tenant/env."""
    declared = [ns for _cap, ns in namespaces_for(tenant, env_name)]
    tenant_name = f"{tenant.naming_prefix}-{env_name}"
    findings: list[str] = []

    capsule = _kubectl_json("get", "tenant.capsule.clastix.io", tenant_name)
    if capsule is None:
        # No Capsule object at all is a different failure from a slow one: the
        # namespaces exist and NOTHING bounds them, permanently.
        return False, [f"Capsule Tenant {tenant_name!r} not found — quota is unenforced"]

    owned = int((capsule.get("status") or {}).get("size", 0) or 0)
    if owned != len(declared):
        findings.append(
            f"tenant owns {owned} namespace(s), registry declares {len(declared)}"
        )

    for namespace in declared:
        obj = _kubectl_json("get", "namespace", namespace)
        if obj is None:
            findings.append(f"namespace {namespace} missing")
            continue
        labels = (obj.get("metadata") or {}).get("labels") or {}
        if labels.get(CAPSULE_TENANT_LABEL) != tenant_name:
            # The label is what puts a namespace INSIDE the tenant. Without it the
            # namespace is real, our own tenant labels are on it, and it is not in
            # the tenant — every view reads correct while the bound applies to
            # nothing.
            findings.append(
                f"namespace {namespace} is not labelled into tenant {tenant_name}"
            )

        quotas = _kubectl_json("get", "resourcequota", "-n", namespace)
        items = (quotas or {}).get("items") or []
        if not items:
            findings.append(f"namespace {namespace} has no ResourceQuota")
            continue
        hard = (items[0].get("spec") or {}).get("hard") or {}
        declared_quota = tenant.quota.to_dict()
        if declared_quota.get("cpu") and "limits.cpu" not in hard:
            findings.append(f"{namespace}: quota does not bound cpu")

    return not findings, findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant", help="check one tenant (default: all soft-tier)")
    parser.add_argument("--wait", type=int, default=0,
                        help="seconds to allow for adoption before failing")
    args = parser.parse_args()

    context = subprocess.run(
        ["kubectl", "config", "current-context"], capture_output=True, text=True
    )
    if context.returncode != 0:
        print("ERROR: no kubectl context", file=sys.stderr)
        return 2
    current_cluster = context.stdout.strip()
    print(f"context: {current_cluster}")

    registry = load_registry()
    selected = [
        (tenant, env)
        for name, tenant in sorted(registry.tenants.items())
        for env in sorted(tenant.environments)
        if tenant.isolation is IsolationTier.SOFT
        and (args.tenant is None or name == args.tenant)
    ]
    if not selected:
        print("ERROR: no soft-tier tenant/env matched", file=sys.stderr)
        return 2

    # Only envs whose cluster is the one we are pointed at can be checked. The first
    # version of this skipped that comparison and reported acme/prod (a k3s cluster
    # this laptop is not talking to) as "Capsule Tenant not found — quota is
    # unenforced". That is the same false alarm this whole script exists to prevent,
    # produced by the tool meant to catch it: **not looking is not a finding.**
    targets, elsewhere = [], []
    for tenant, env_name in selected:
        env = tenant.environments[env_name]
        (targets if env.cluster == current_cluster else elsewhere).append(
            (tenant, env_name, env.cluster)
        )
    targets = [(t, e) for t, e, _ in targets]
    if not targets:
        print(f"nothing to check: no selected env runs on {current_cluster!r}", file=sys.stderr)
        for name, env_name, cluster in [(t.name, e, c) for t, e, c in elsewhere]:
            print(f"  {name}/{env_name} lives on {cluster}", file=sys.stderr)
        return 2

    deadline = time.time() + max(args.wait, 0)
    while True:
        results = []
        for tenant, env_name in targets:
            # Only clusters we are actually pointed at can be checked; a tenant/env
            # on another cluster reports "cannot check" rather than "broken".
            adopted, findings = _check(tenant, env_name)
            results.append((tenant.name, env_name, adopted, findings))
        if all(adopted for _, _, adopted, _ in results) or time.time() >= deadline:
            break
        time.sleep(5)

    failed = 0
    for name, env_name, adopted, findings in results:
        if adopted:
            print(f"{name}/{env_name}: adopted and bounded ✓")
        else:
            failed += 1
            print(f"{name}/{env_name}: NOT fully adopted ✗")
            for finding in findings:
                print(f"    - {finding}")

    for tenant, env_name, cluster in elsewhere:
        print(f"{tenant.name}/{env_name}: not checked — lives on {cluster}")

    if failed:
        print(
            "\nA namespace outside its tenant is not a slow rebuild — it is an "
            "unbounded namespace on a shared cluster that reads as finished.\n"
            "Re-run with --wait 60 to allow for reconcile lag; if it persists, the "
            "applying identity is probably not in Capsule's `administrators` list.",
            file=sys.stderr,
        )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
