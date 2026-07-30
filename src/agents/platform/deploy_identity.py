"""The credential the deploy path runs as — one seam, one place to pin it.

Measured 2026-07-30 (``docs/evidence/deploy-path-authorization.log``): every
deployment adapter shelled out to a bare ``kubectl`` — no ``--kubeconfig``, no
``--context`` — so a deploy ran as whatever the ambient context was. On the live
kind cluster that ambient was ``kubernetes-admin`` in ``kubeadm:cluster-admins``::

    can-i get secrets -A                    : yes
    can-i delete namespaces -A              : yes
    can-i create clusterrolebindings        : yes

Which is to say: the identity that rolls out ``orders-api`` could also read every
secret in the cluster and delete the namespaces of every tenant. The incident path
had exactly this and Phase 1a removed it (``onprem_runner._run_kubectl``); the
deploy path kept it. **The front door was bolted and the loading dock was not.**

This module is the seam, deliberately *one* implementation rather than four. The
repo has already paid for the alternative: when the same idea was rendered
per-runner, the third runner simply did not have it (see ``platform/scope.py`` on
why ``guard_scoped_action`` is shared). Four deployment adapters build kubectl argv;
if each grew its own pinning, the fourth would be the one still running ambient.

**What this is not.** It does not separate tenants. Every deploy uses the same
"platform deployer" identity, so it bounds *what* a deploy can do, not *whose*
cluster it touches — that is 결정 5 C/D and needs router authentication first
(`docs/plans/2026-07-30-deploy-request-tenant-scoping.md`). Saying more than that
on a card or a dashboard would be advertising what we do not enforce.

**Absence is loud, not silent.** With ``PLATFORM_DEPLOY_KUBECONFIG`` unset the argv
is unchanged (ambient) — the demo, `make dev-up` and every local run keep working —
but ``warn_if_ambient`` says so once per process. A fail-closed default here would
be the safer *shape* and the wrong *change*: it would break the two-line demo the
repo is built around, and a boundary nobody can run is the failure mode this whole
investigation just documented.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

#: Path to the kubeconfig the deploy path should use. Unset -> ambient (loud).
DEPLOY_KUBECONFIG_ENV = "PLATFORM_DEPLOY_KUBECONFIG"

#: Emitted once per process so the warning is a signal rather than log noise.
_warned = False


def deploy_kubeconfig() -> str | None:
    """The configured deploy credential, or None when running ambient.

    An empty value is treated as unset: a shell that exports the variable without a
    value has not configured a credential, and pinning kubectl to ``""`` would fail
    in a way that reads like a broken cluster rather than a broken config.
    """
    return os.getenv(DEPLOY_KUBECONFIG_ENV) or None


def deploy_kubectl(*args: str) -> list[str]:
    """kubectl argv for the deploy path, pinned to the deploy credential if there is one.

    Every deployment adapter builds its commands through here, so the answer to
    "what identity did this deploy run as" has exactly one implementation.
    """
    kubeconfig = deploy_kubeconfig()
    if kubeconfig:
        return ["kubectl", "--kubeconfig", kubeconfig, *args]
    return ["kubectl", *args]


def warn_if_ambient() -> None:
    """Say once, at the point of use, that this deploy is running on ambient credentials.

    At the point of use rather than at import: what matters is that a *deploy*
    happened unpinned, and importing the module proves nothing about that.
    """
    global _warned
    if _warned or deploy_kubeconfig():
        return
    _warned = True
    logger.warning(
        "deploy.ambient_credentials: %s is not set, so this deploy runs as whatever "
        "identity the current kubeconfig context holds — on a kubeadm cluster that is "
        "typically cluster-admin (every secret, every namespace). Render one with "
        "`python scripts/render_deploy_identity.py` and mint it with "
        "`scripts/mint_deploy_kubeconfig.sh`.",
        DEPLOY_KUBECONFIG_ENV,
    )
