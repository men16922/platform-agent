#!/usr/bin/env python3
"""Can a production incident actually mint a scoped credential?

`guard_scoped_action` refuses without an `IncidentScope`. The only producer is
`resolve_incident_scope`, which reads `source_metadata["attested_approval"]`. This
probe builds an incident the way the real signal adapter does — from an Alertmanager
payload — and asks whether a scope comes out.

Nothing of ours is mocked; the adapter, the resolver and the gate are the real ones.
Run it whenever the answer is supposed to have changed:

    python scripts/probe_scope_reachability.py

Companion to `scripts/probe_netpol_side_effects.sh`: a measurement kept re-runnable
rather than a claim kept in prose. Asserted by
`tests/test_scope_producer_reachability.py`; options → `docs/plans/2026-07-30-deploy-request-tenant-scoping.md`.
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))


class _Log:
    def _emit(self, level: str, event: str, **kw) -> None:
        print(f"      [{level}] {event} {kw or ''}")

    def info(self, event, **kw): self._emit("info", event, **kw)
    def warning(self, event, **kw): self._emit("warn", event, **kw)
    def error(self, event, **kw): self._emit("error", event, **kw)


ALERT = {
    "status": "firing",
    "alerts": [
        {
            "labels": {
                "alertname": "PodCrashLooping", "namespace": "acme-dev-logging",
                "pod": "loki-gateway-0", "severity": "warning",
                "tenant": "acme", "env": "dev",
            },
            "annotations": {"summary": "pod restarting", "description": "CrashLoopBackOff"},
            "startsAt": "2026-07-30T00:00:00Z",
            "generatorURL": "http://prom/graph",
        }
    ],
}


def _grep(pattern: str, *paths: str) -> list[str]:
    out = subprocess.run(
        ["grep", "-rn", pattern, *paths], capture_output=True, text=True, cwd=REPO
    ).stdout.strip().splitlines()
    return [line for line in out if "cdk.out" not in line and "__pycache__" not in line]


def bar(title: str) -> None:
    print("\n" + "=" * 78 + f"\n{title}\n" + "=" * 78)


def main() -> int:
    from src.agents.adapters.signals.onprem import OnPremAlertmanagerSignalAdapter
    from src.agents.platform.scope import (
        ScopeError,
        guard_scoped_action,
        resolve_incident_scope,
    )

    bar("1. A real incident, built by the real on-prem signal adapter")
    incident = OnPremAlertmanagerSignalAdapter().normalise(ALERT)
    metadata = incident.source_metadata or {}
    print(f"      provider            : {incident.provider}")
    print(f"      tenant / env        : {incident.tenant!r} / {incident.env!r}")
    print(f"      source_metadata keys: {sorted(metadata)}")
    print(f"      carries attested_approval? {'attested_approval' in metadata}")

    bar("2. Can a scope be minted from it? (the only producer in the codebase)")
    scope = resolve_incident_scope(incident, _Log())
    print(f"      resolve_incident_scope -> {scope!r}")

    bar("3. So what does the gate do to a LIVE remediation?")
    try:
        guard_scoped_action(action="restart_workload", namespace="acme-dev-logging",
                            scope=scope, log=_Log(), log_prefix="onprem_runner")
        print("      -> PERMITTED")
    except ScopeError as exc:
        print(f"      -> REFUSED: {exc}")

    bar("4. Are the broker's prerequisites provisioned anywhere?")
    for var in ("PLATFORM_CREDENTIAL_DIR", "PLATFORM_APPROVAL_SIGNING_KEY"):
        setters = sorted({
            line.split(":")[0] for line in _grep(var, "src", "scripts", "Makefile")
            if not line.split(":")[0].endswith("platform/scope.py")
        })
        print(f"      {var}")
        print(f"        in env    : {bool(os.getenv(var))}")
        print(f"        set by    : {setters or '(nothing — only its own definition)'}")

    bar("5. Who produces an attested record?")
    prod = [l for l in _grep("sign_approval", "src") if "def sign_approval" not in l]
    tests = _grep("sign_approval", "tests", "scripts")
    writes = _grep('"attested_approval"', "src")
    print(f"      sign_approval callers in src/  : {prod or '(none)'}")
    print(f"      sign_approval callers in tests/: {len(tests)}")
    print(f"      writers of attested_approval   : "
          f"{[l for l in writes if 'scope.py' not in l] or '(none — only the reader)'}")

    bar("VERDICT")
    reachable = scope is not None
    print(f"      scope reachable from a production incident: {reachable}")
    if not reachable:
        print("      The gate is correct and its isolation is live-proven, but nothing")
        print("      in production opens it. A live remediation is refused for want of a")
        print("      credential — not because the namespace was out of scope, but because")
        print("      no scope can exist. Fail-closed, and NOT an enforced boundary.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
