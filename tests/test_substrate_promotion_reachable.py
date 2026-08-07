"""A verifier that cannot reach its subject is a guard nobody can ever open.

This is the fourth face of one shape, and the first three each cost a live run:

  M13   a field is declared, written, and read by nobody
  D38   a mechanism is correct and no production code can reach it
  D39   a security exception is held open for a caller that does not exist
  D40   a probe exists to promote a substrate, and structurally cannot run on any
        substrate that is not already promoted

`verify_tenant_isolation.py` is the experiment that licenses membership in
``PROVEN_ENFORCING_SUBSTRATES``: same-tenant reachable, cross-tenant blocked,
kubelet probes and DNS unharmed. It is careful, it renders nothing of its own, and
each of its four claims can fail. It also refuses to start unless
``network_policies_apply_to`` is true — which reads the very set it is supposed to
justify. So the promotion procedure is: add the substrate first, then run the thing
that decides whether to add it. kind passed because kind was already inside.

Nothing was red. The set said "kind", the docstrings said "measured, not assumed",
and the recorded reason k3s stayed out — "acme/prod is the only env on k3s-lab" —
was true, was repeated in four files, and was not the binding blocker. The binding
ones (acme/prod renders ONE namespace where the same-tenant leg needs two; and the
circular gate above) were written down nowhere.

Investigation: docs/plans/2026-08-01-k3s-proven-substrate.md.

What this file asserts is narrow and true today: every membership claim in the set
must be FALSIFIABLE with the registry as it stands. Not that it was falsified — the
evidence logs carry that — but that the experiment could be run at all. A claim
whose disproof requires a registry that does not exist is not a measured claim; it
is a default wearing a measurement's name.

Not asserted: that k3s should or should not be added. That is an operator decision
(NEXT_PLAN 결정 4, closed as "not now" for reasons this file pins).
"""

from __future__ import annotations

import pathlib

import pytest

from src.agents.platform.registry import load_registry
from src.agents.platform.tenancy import (
    PROVEN_ENFORCING_SUBSTRATES,
    namespaces_for,
    network_policies_apply_to,
)

REPO = pathlib.Path(__file__).resolve().parents[1]
PROBE = REPO / "scripts" / "verify_tenant_isolation.py"

#: The probe's own preconditions, restated here rather than imported, because the
#: point is to fail when the probe and the registry drift apart — importing them
#: would make the two agree by construction and this guard would assert nothing.
_SAME_TENANT_LEG_NEEDS = 2


@pytest.fixture
def registry():
    return load_registry()


def _envs_on(registry, substrate: str):
    for tenant in registry.tenants.values():
        for env in tenant.environments.values():
            if env.substrate == substrate:
                yield tenant, env


def test_every_proven_substrate_is_falsifiable_from_the_registry(registry):
    """Membership requires a registry on which the disproving probe can actually run.

    Three things must line up on ONE cluster, or `verify_tenant_isolation.py` exits
    2 before it applies a single object:

      * a tenant/env with >= 2 namespaces  -> the same-tenant leg has a source and
        a destination (this is the check acme/prod fails, with 1 addon = 1 ns)
      * a DIFFERENT tenant with >= 1 namespace on the SAME cluster -> "cross-tenant"
        means something
      * NetworkPolicies rendered for that env -> there is a policy under test

    Promote a substrate without arranging these and the set gains a claim that
    cannot be disproven. That is the failure this test exists to make loud, and it
    is the one that would have caught D40 at the moment the sentence was written.
    """
    for substrate in sorted(PROVEN_ENFORCING_SUBSTRATES):
        candidates = list(_envs_on(registry, substrate))
        assert candidates, (
            f"'{substrate}' is in PROVEN_ENFORCING_SUBSTRATES but no registry env "
            "runs on it — the claim is about a substrate the platform does not use"
        )

        runnable = []
        for tenant, env in candidates:
            targets = namespaces_for(tenant, env.name)
            if len(targets) < _SAME_TENANT_LEG_NEEDS:
                continue
            if not network_policies_apply_to(tenant, env.name):
                continue
            peers = [
                (peer, peer_env)
                for peer, peer_env in _envs_on(registry, substrate)
                if peer.name != tenant.name
                and peer_env.cluster == env.cluster
                and namespaces_for(peer, peer_env.name)
            ]
            if peers:
                runnable.append((tenant.name, env.name, peers[0][0].name))

        assert runnable, (
            f"'{substrate}' is claimed PROVEN, but no tenant/env on it can be run "
            f"through scripts/verify_tenant_isolation.py:\n"
            + "\n".join(
                f"  - {t.name}/{e.name} on {e.cluster}: "
                f"{len(namespaces_for(t, e.name))} namespace(s), "
                f"netpol_rendered={network_policies_apply_to(t, e.name)}"
                for t, e in candidates
            )
            + "\n  The probe needs >=2 namespaces for one tenant AND a second tenant "
            "on the same cluster. Until that exists the membership claim is not "
            "falsifiable — see docs/plans/2026-08-01-k3s-proven-substrate.md"
        )


def test_the_promotion_gate_is_circular_and_that_is_written_down(registry):
    """Pin the circularity so the next person meets it here, not in a live run.

    `verify_tenant_isolation.py` gates on `network_policies_apply_to`, which gates on
    `PROVEN_ENFORCING_SUBSTRATES`. A candidate substrate therefore fails the probe's
    precondition no matter how the registry is arranged, and promoting it means
    flipping the set FIRST and reverting if the probe then disagrees.

    That procedure is defensible; being undocumented is not. If someone opens an
    explicit candidate path in the probe, this test goes red and is the right place
    to learn the full blocker list.
    """
    unproven = [
        (tenant, env)
        for tenant in registry.tenants.values()
        for env in tenant.environments.values()
        if env.substrate not in PROVEN_ENFORCING_SUBSTRATES
    ]
    assert unproven, (
        "no unproven substrate left in the registry — if every substrate is proven, "
        "this guard has nothing to say and should be retired rather than weakened"
    )
    for tenant, env in unproven:
        assert network_policies_apply_to(tenant, env.name) is False, (
            f"{tenant.name}/{env.name} renders NetworkPolicies on unproven substrate "
            f"'{env.substrate}' — the skip in render_tenancy is what keeps an "
            "unenforced policy from reading as isolation"
        )

    source = PROBE.read_text(encoding="utf-8")
    assert "network_policies_apply_to" in source, (
        "the semantic probe no longer gates on the proven set. If that is because a "
        "candidate path was opened, good — update this test and "
        "docs/plans/2026-08-01-k3s-proven-substrate.md, and note that the probe ALSO "
        "needs >=2 namespaces for the target tenant (blocker 1) and a peer tenant on "
        "the same cluster (blocker 2)"
    )
