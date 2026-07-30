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
        attest_decision,
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

    bar("2. Run the production chain: attest, then resolve")
    # Both steps, because the attestation is minted at the *gate* (AUTO / approval),
    # not at detection — a raw incident straight off the adapter never carries one,
    # and asking only `resolve_incident_scope` therefore answers False even in a
    # correctly configured environment. This probe reported exactly that for one
    # run after `attest_decision` landed, which would have read as "still broken".
    decision = {"analyzer": {"detector": {"normalized_incident": incident}}}
    attested = attest_decision(decision, approval_id="PROBE", log=_Log())
    print(f"      attest_decision       -> {attested}")
    scope = resolve_incident_scope(incident, _Log())
    print(f"      resolve_incident_scope -> {scope.redacted() if scope else None}")

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
    # Call sites, not mentions: the module's own docstrings discuss both symbols at
    # length, and the first version of this counted those as producers.
    producers = [
        line for line in _grep(r"\(sign_approval\|attest_decision\)\s*(", "src")
        if not line.startswith("src/agents/platform/scope.py")
    ]
    print(f"      production call sites: {producers or '(none)'}")
    print(f"      test call sites      : {len(_grep('sign_approval', 'tests'))}")

    bar("VERDICT")
    reachable = scope is not None
    print(f"      scope reachable in THIS environment: {reachable}")
    if reachable:
        print("      Configured. The gate can be opened, so the boundary is enforced")
        print("      rather than merely closed. Isolation itself is the API server's job.")
    elif producers:
        # The distinction that matters operationally: a missing producer is a code
        # gap somebody has to close; missing credentials are one `make` away. Before
        # 2026-07-31 these were the same answer, and collapsing them again would hide
        # a regression behind a config problem.
        print("      A producer EXISTS but this environment is not configured, so every")
        print("      live remediation is still refused. Not a code gap — run:")
        print("          make scope-credentials     # mints credentials, prints the env")
        for var in ("PLATFORM_CREDENTIAL_DIR", "PLATFORM_APPROVAL_SIGNING_KEY"):
            print(f"          {var}: {'set' if os.getenv(var) else 'NOT SET'}")
    else:
        print("      No production code can open the gate at all. A live remediation is")
        print("      refused for want of a credential — not because the namespace was out")
        print("      of scope, but because no scope can exist. NOT an enforced boundary.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
