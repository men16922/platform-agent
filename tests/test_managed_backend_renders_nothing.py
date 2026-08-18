"""
A managed backend renders no manifest, and the read model says why. Both halves.

Phase 4a's DoD is four steps: declare a managed backend in the registry → the
adapter renders → remote_write succeeds locally → the read model marks the sync
axis honestly as n/a. ③ landed 2026-08-17 (D50) and ④ has stood since
`from_managed` existed. ①② were open because `delivery.expand_desired` **refused**
a managed declaration outright: passing the backend through as a chart name would
make the engine chase a chart the self-hosted repo does not publish, and *"what a
managed backend should render is deliberately not invented here"*.

The decision, made 2026-08-17: **nothing is rendered, and the absence is
explained.** No new manifest kind. The two halves are a pair —

    delivery   `managed=True` on the DesiredAddon; adapters emit no manifest
    read model `from_managed` → `applicable=False`, `sync_state=NOT_APPLICABLE`

— and that pairing is the whole design. Render-nothing *alone* is the silent drop
the old error existed to prevent: a declared add-on vanishes with no signal, which
looks exactly like delivery lag. Read-model-alone would report a backend the
engine is simultaneously trying to install as a chart. This file fails if either
half disappears, which is the only reason it is safe to have deleted the refusal.

⚠️ It also asks the question with the **shipped registry**, not a built fixture.
`globex/dev` declares `observability: amazon-managed-prometheus` as of 2026-08-17;
before that, `expand_desired`'s managed branch had no caller and the
`applicable=false` axis had only ever been exercised with a faked descriptor —
which is precisely what the design doc said Phase 2 could do and Phase 4 could not.
"""

from __future__ import annotations

import pathlib

import pytest

from src.agents.platform.addon_status import SyncState, from_managed
from src.agents.platform.delivery import desired_addons
from src.agents.platform.registry import Registry, load_registry

REGISTRY_ROOT = pathlib.Path(__file__).resolve().parents[1] / "platform"
CAPABILITY = "observability"
MANAGED_TENANT = "globex"
MANAGED_ENV = "dev"


@pytest.fixture(scope="module")
def registry() -> Registry:
    return load_registry(REGISTRY_ROOT)


def _addons(registry: Registry, tenant_name: str, env_name: str):
    tenant = registry.tenant(tenant_name)
    env = registry.environment(tenant_name, env_name)
    return tenant, env, desired_addons(
        tenant,
        env,
        registry.wave_for,
        registry.scope_of,
        is_managed=registry.is_managed_backend,
    )


def test_the_shipped_registry_declares_a_managed_backend(registry):
    """The premise, and the thing that gives the managed branch any load at all.

    Without a declaration in the registry, everything below is a test of a code path
    no tenant can reach — which is what "prove it with a faked descriptor" meant and
    what DoD ① exists to end.
    """
    env = registry.environment(MANAGED_TENANT, MANAGED_ENV)
    declared = env.addons[CAPABILITY].split()[0]
    assert registry.is_managed_backend(CAPABILITY, declared), (
        f"{MANAGED_TENANT}/{MANAGED_ENV} declares {CAPABILITY}={declared!r}, which the "
        "catalog does not list as managed — this file then proves nothing"
    )


def test_the_declaration_survives_expansion_and_is_marked(registry):
    _tenant, _env, addons = _addons(registry, MANAGED_TENANT, MANAGED_ENV)
    by_capability = {a.capability: a for a in addons}
    assert CAPABILITY in by_capability, (
        "the managed add-on vanished during expansion — a silent drop is "
        "indistinguishable from delivery lag, which is why the old code raised"
    )
    assert by_capability[CAPABILITY].managed is True


@pytest.mark.parametrize("engine", ["argocd", "flux"])
def test_neither_engine_renders_a_manifest_for_it(registry, engine):
    """Asked of both engines, because the rule is engine-independent.

    A third engine that forgets this inherits the bug the old error prevented — the
    same reason `reject_cluster_singletons` lives on the contract rather than in each
    adapter.
    """
    from src.agents.platform.adapters.argocd import ArgoCDDeliveryAdapter
    from src.agents.platform.adapters.flux import FluxDeliveryAdapter

    adapter = (
        ArgoCDDeliveryAdapter(repo_url="https://example.invalid")
        if engine == "argocd"
        else FluxDeliveryAdapter(repo_url="https://example.invalid")
    )
    tenant, env, addons = _addons(registry, MANAGED_TENANT, MANAGED_ENV)
    manifests = adapter.render(tenant, env, addons)

    rendered = " ".join(str(m) for m in manifests)
    declared = env.addons[CAPABILITY].split()[0]
    assert declared not in rendered, (
        f"{engine} rendered something naming {declared!r}; a managed backend has no "
        "chart in the self-hosted repo, so the engine would chase one that does not "
        "exist — the failure the removed error was written to prevent"
    )


def test_the_read_model_is_the_other_half_and_says_n_a(registry):
    """The half that makes the empty render legible instead of silent.

    `from_managed` is what the collector calls for these, and the two values below
    are the DoD's fourth step in code: the sync axis is **not applicable**, not
    "synced" and not "unknown".
    """
    declared = registry.environment(MANAGED_TENANT, MANAGED_ENV).addons[CAPABILITY].split()[0]
    status = from_managed(
        tenant=MANAGED_TENANT,
        env=MANAGED_ENV,
        capability=CAPABILITY,
        backend=declared,
    )
    assert status.sync_state is SyncState.NOT_APPLICABLE, (
        "a managed backend reported with any other sync state is the render's "
        "silence dressed up as agreement"
    )
    assert status.applicable is False


def test_a_self_hosted_declaration_still_renders(registry):
    """The control. Rendering nothing for everything would satisfy the tests above.

    `acme/dev` declares the self-hosted chart for the same capability, so the two
    tenants on this one cluster exercise both branches.
    """
    _tenant, env, addons = _addons(registry, "acme", "dev")
    declared = env.addons[CAPABILITY].split()[0]
    assert not registry.is_managed_backend(CAPABILITY, declared), "premise"
    by_capability = {a.capability: a for a in addons}
    assert by_capability[CAPABILITY].managed is False
    assert by_capability[CAPABILITY].backend == declared
