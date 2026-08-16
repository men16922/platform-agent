"""
Rollback vs GitOps self-heal — Phase 3② (the refusal half).

The platform offers ``rollback_release`` / ``ONPREM-ArgoRolloutRollback`` as
automated remediation at the same time as ArgoCD/Flux reconcile the declared
desired version. With no policy between them the agent's rollback is reverted by
the reconciler within seconds: **the remediation loop fights the delivery loop.**

What makes that worse than a plain failure is the shape of it. The rollback
*succeeds* — ``kubectl rollout undo`` returns 0, the verifier can even observe a
healthy workload in the window before reconciliation — and then the fix quietly
disappears. Every record we keep says the incident was remediated. This is the
same "no error, just not read" family as the values files and the dangling
RoleBinding subject, and it is the one where our own logs actively lie.

So: **do not act on a reconciler-managed target unless desired has been aligned
first.** This module answers only "who owns this object, and has desired been
aligned?" and refuses when the answer means the action would be undone. The
alignment itself (selfHeal pause, or registry write-back once Phase 5 can write
the registry) is the caller's business.

Ownership is read off the markers the reconcilers themselves stamp, not off our
registry — the registry says what *should* be managed, and the question here is
what *is*. Those differ exactly when something has gone wrong, which is when a
rollback gets attempted.
"""

from __future__ import annotations

from typing import Any

#: (reconciler, metadata section, key). ArgoCD is configured with
#: ``resourceTrackingMethod=annotation`` (see the addons chart), so the
#: tracking-id annotation is authoritative rather than the app.kubernetes.io
#: instance label, which is shared with plain Helm installs and would produce
#: false positives.
RECONCILER_MARKERS: tuple[tuple[str, str, str], ...] = (
    ("argocd", "annotations", "argocd.argoproj.io/tracking-id"),
    ("flux", "labels", "kustomize.toolkit.fluxcd.io/name"),
    ("flux", "labels", "helm.toolkit.fluxcd.io/name"),
)

#: Actions that put the live state back to a previous revision. These are the
#: only ones that conflict: a restart or a scale converges to the same desired
#: spec the reconciler already holds, so self-heal has nothing to undo.
#:
#: ⚠️ The two AWS entries were missing until 2026-08-16, and the test that exists
#: to catch exactly that could not: it iterated
#: ``("ONPREM-", "GCP-", "AZURE-")`` — **AWS was absent from the list of clouds**,
#: so the one unregistered cloud was the one never asked about. It also asked
#: `any(...)`, which one action per prefix satisfies while a second goes missing.
#: The completeness check is now derived from the execution adapters
#: (`test_reconciler_conflict.py`), because a hand-written sibling list is what
#: failed here — for the sixth time in this repository.
ROLLBACK_ACTIONS: frozenset[str] = frozenset({
    "ONPREM-ArgoRolloutRollback",
    "GCP-RollbackGKEWorkload",
    "GCP-RollbackCloudRunRevision",
    "AZURE-RollbackAKSWorkload",
    "AZURE-RollbackFunctionApp",
    "AWS-RollbackEKSDeployment",
    "AWS-RollbackLambdaAlias",
})


class ReconcilerConflict(RuntimeError):
    """Raised when a rollback would be reverted by a reconciler. Fail-closed."""


def is_rollback(action: str) -> bool:
    """Whether ``action`` moves live state backwards to a previous revision."""
    return action in ROLLBACK_ACTIONS


def detect_reconciler(manifest: dict[str, Any] | None) -> str | None:
    """
    Name the reconciler that owns ``manifest``, or None if nothing claims it.

    None means "no marker found", which is **not** the same as "nothing manages
    this" — a reconciler we do not know about leaves no marker we recognise.
    Callers must treat None as "no known conflict", never as proof of safety.
    """
    if not manifest:
        return None
    metadata = manifest.get("metadata") or {}
    for reconciler, section, key in RECONCILER_MARKERS:
        if key in (metadata.get(section) or {}):
            return reconciler
    return None


def guard_rollback(
    *,
    action: str,
    manifest: dict[str, Any] | None,
    log: Any,
    log_prefix: str,
    desired_aligned: bool = False,
) -> None:
    """
    Refuse a rollback that a reconciler would undo.

    ``desired_aligned`` is the caller's assertion that it has already made
    desired match the rollback target — by pausing self-heal for the duration,
    or by writing the target version back to the registry. It defaults to False
    so that a caller which has not thought about this gets the refusal rather
    than the silent revert.
    """
    if not is_rollback(action):
        return

    reconciler = detect_reconciler(manifest)
    if reconciler is None:
        return

    if desired_aligned:
        log.info(
            f"{log_prefix}.rollback_with_aligned_desired",
            action=action,
            reconciler=reconciler,
        )
        return

    name = ((manifest or {}).get("metadata") or {}).get("name", "<unknown>")
    namespace = ((manifest or {}).get("metadata") or {}).get("namespace", "<unknown>")
    log.error(
        f"{log_prefix}.reconciler_conflict",
        action=action,
        reconciler=reconciler,
        workload=f"{namespace}/{name}",
    )
    raise ReconcilerConflict(
        f"refusing {action!r} on {namespace}/{name}: it is managed by {reconciler}, "
        "which would revert the rollback to the declared desired version. Align "
        "desired first (pause self-heal for the duration, or write the target "
        "version back to the registry) — otherwise the rollback is recorded as a "
        "success and then silently undone."
    )
