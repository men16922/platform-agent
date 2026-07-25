"""
Terraform → GitOps ownership handoff preflight.

Phase 1b moves add-on ownership from ``helm_release`` (Terraform) to a GitOps
engine. The migration is a `terraform state rm` followed by the engine adopting
the *already installed* release. That adoption has to be a **no-op**: if the
controller decides the objects are new, it deletes and recreates them, and any
PersistentVolumeClaim in the release goes with them.

So the dangerous part is not the `state rm` — it is discovering afterwards that
adoption was not clean. This module answers "is it safe *yet*?" before anything
is removed from state, and refuses on anything it cannot prove.

Four findings, each mapped to a way the handoff actually breaks:

* **Ownership metadata mismatch** — Helm marks resources with
  ``app.kubernetes.io/managed-by`` + ``meta.helm.sh/release-{name,namespace}``.
  The GitOps manifest must reproduce these exactly, or the controller sees
  unowned/foreign objects.
* **Stateful resources** — a PVC in the release means a botched adoption is
  *data loss*, not an outage. Requires a snapshot first; never auto-cleared.
* **Source drift** — the engine syncs from the git remote, not from the working
  tree. Unpushed chart edits guarantee churn that looks like an adoption failure
  but is really a content difference.
* **No recorded baseline** — "revision did not increase" is only checkable if
  the revision before the handoff was written down.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Helm's ownership markers. A GitOps manifest that does not reproduce these
# exactly will not adopt the existing release.
MANAGED_BY_LABEL = "app.kubernetes.io/managed-by"
RELEASE_NAME_ANNOTATION = "meta.helm.sh/release-name"
RELEASE_NAMESPACE_ANNOTATION = "meta.helm.sh/release-namespace"

#: Kinds whose recreation destroys data rather than merely causing an outage.
STATEFUL_KINDS = frozenset({"PersistentVolumeClaim", "StatefulSet"})


@dataclass(frozen=True)
class Finding:
    """One preflight result. ``blocking`` decides whether the handoff may proceed."""

    check: str
    passed: bool
    blocking: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "check": self.check,
            "passed": self.passed,
            "blocking": self.blocking,
            "detail": self.detail,
        }


@dataclass
class HandoffPreflight:
    """Collected findings plus the verdict and the rollback command."""

    release: str
    namespace: str
    revision: int | None
    findings: list[Finding] = field(default_factory=list)

    @property
    def safe(self) -> bool:
        """Safe only when no blocking check failed. Unknown counts as unsafe."""
        return not any(f.blocking and not f.passed for f in self.findings)

    @property
    def blockers(self) -> list[Finding]:
        return [f for f in self.findings if f.blocking and not f.passed]

    def to_dict(self) -> dict[str, Any]:
        return {
            "release": self.release,
            "namespace": self.namespace,
            "revision_before": self.revision,
            "safe": self.safe,
            "findings": [f.to_dict() for f in self.findings],
        }


def check_ownership(resources: list[dict[str, Any]], release: str, namespace: str) -> Finding:
    """
    Every resource must carry Helm's ownership markers for this exact release.

    A mismatch is the difference between "controller adopts 6 objects" and
    "controller creates 6 new objects and prunes the old ones".
    """
    # Only Helm-applied objects carry ownership markers. Pods, ReplicaSets and
    # friends are created by their controller and inherit the instance label, so
    # judging them here produces false positives — and a checker that cries wolf
    # gets ignored, which is worse than not having one.
    resources = [r for r in resources if not (r.get("metadata") or {}).get("ownerReferences")]

    mismatched: list[str] = []
    for resource in resources:
        metadata = resource.get("metadata") or {}
        labels = metadata.get("labels") or {}
        annotations = metadata.get("annotations") or {}
        name = f"{resource.get('kind', '?')}/{metadata.get('name', '?')}"
        if labels.get(MANAGED_BY_LABEL) != "Helm":
            mismatched.append(f"{name}: managed-by={labels.get(MANAGED_BY_LABEL)!r}")
        elif annotations.get(RELEASE_NAME_ANNOTATION) != release:
            mismatched.append(f"{name}: release-name={annotations.get(RELEASE_NAME_ANNOTATION)!r}")
        elif annotations.get(RELEASE_NAMESPACE_ANNOTATION) != namespace:
            mismatched.append(
                f"{name}: release-namespace={annotations.get(RELEASE_NAMESPACE_ANNOTATION)!r}"
            )

    if not resources:
        return Finding(
            check="ownership-metadata",
            passed=False,
            blocking=True,
            detail="no resources found — cannot prove the GitOps manifest would adopt anything",
        )
    if mismatched:
        return Finding(
            check="ownership-metadata",
            passed=False,
            blocking=True,
            detail=f"{len(mismatched)} resource(s) would not be adopted: " + "; ".join(mismatched[:3]),
        )
    return Finding(
        check="ownership-metadata",
        passed=True,
        blocking=True,
        detail=f"all {len(resources)} resources carry Helm ownership for {release}/{namespace}",
    )


def check_stateful(resources: list[dict[str, Any]], snapshot_taken: bool) -> Finding:
    """
    A PVC in the release turns a botched adoption into data loss.

    Never auto-cleared: the caller must assert a snapshot exists. "Probably fine"
    is not an acceptable answer when the failure mode is losing metric history.
    """
    # PVCs created by a StatefulSet's volumeClaimTemplate have no ownerReferences
    # to the release, so both the StatefulSet and its PVCs are counted — losing
    # either is data loss, which is exactly what this check exists to prevent.
    stateful = [
        f"{r.get('kind')}/{(r.get('metadata') or {}).get('name')}"
        for r in resources
        if r.get("kind") in STATEFUL_KINDS
    ]
    if not stateful:
        return Finding(
            check="stateful-resources",
            passed=True,
            blocking=True,
            detail="no PVC/StatefulSet in this release — a failed adoption costs uptime, not data",
        )
    if snapshot_taken:
        return Finding(
            check="stateful-resources",
            passed=True,
            blocking=True,
            detail=f"stateful resources present ({', '.join(stateful)}) and a snapshot was asserted",
        )
    return Finding(
        check="stateful-resources",
        passed=False,
        blocking=True,
        detail=(
            f"stateful resources present ({', '.join(stateful)}) with no snapshot — "
            "a failed adoption would destroy data, not just restart it"
        ),
    )


def check_source_reachable(commits_ahead: int, remote_configured: bool) -> Finding:
    """
    The engine syncs from the git remote, not from your working tree.

    Unpushed chart edits guarantee the controller applies *older* content, which
    shows up as churn and is easily misread as "adoption failed".
    """
    if not remote_configured:
        return Finding(
            check="source-reachable",
            passed=False,
            blocking=True,
            detail="no git remote — the GitOps engine has nothing to sync from",
        )
    if commits_ahead > 0:
        return Finding(
            check="source-reachable",
            passed=False,
            blocking=True,
            detail=(
                f"local branch is {commits_ahead} commit(s) ahead of the remote; the engine would "
                "sync older chart content and the resulting churn would look like an adoption failure"
            ),
        )
    return Finding(
        check="source-reachable",
        passed=True,
        blocking=True,
        detail="remote is up to date with the local branch",
    )


def check_baseline_recorded(revision: int | None) -> Finding:
    """"Revision did not increase" is only verifiable against a recorded baseline."""
    if revision is None:
        return Finding(
            check="revision-baseline",
            passed=False,
            blocking=True,
            detail="could not read the current helm revision — no-churn would be unverifiable",
        )
    return Finding(
        check="revision-baseline",
        passed=True,
        blocking=False,
        detail=f"revision before handoff = {revision}; adoption must leave it unchanged",
    )


#: Fields the delivery engine legitimately adds on adoption. Reporting these as
#: drift would make the check cry wolf on every single handoff.
_ADOPTION_ANNOTATIONS = ("argocd.argoproj.io/tracking-id", "kubectl.kubernetes.io/last-applied-configuration")


def check_live_matches_rendered(differences: list[str]) -> Finding:
    """Does the LIVE object still match the manifest the engine will apply?

    The gap this closes, found the hard way on the first real handoff: every
    other check passed, the preflight said SAFE TO PROCEED, and adoption still
    churned — ArgoCD applied the rendered manifest and a canary rolled.

    Nothing was wrong with the handoff. The live Rollout had silently lost its
    container `ports` and `resources.requests`, so re-asserting git's desired
    state was a real change. (Cause: `kubectl patch --type=merge` on a container
    list. That is a JSON merge patch, which REPLACES arrays wholesale — a patch
    carrying only name+image drops every other field of the container.)

    Adoption re-asserts the manifest either way, so drift is not dangerous by
    itself. It is dangerous because it makes the handoff look like the culprit:
    you expect a no-op, you get a rollout, and you reach for the rollback.
    Non-blocking on purpose — this is "expect churn, here is exactly what",
    not "stop".
    """
    if not differences:
        return Finding(
            check="live-matches-rendered",
            passed=True,
            blocking=False,
            detail="live objects match the rendered manifest — adoption should be a true no-op",
        )
    listed = ", ".join(differences[:6])
    if len(differences) > 6:
        listed += f", +{len(differences) - 6} more"
    return Finding(
        check="live-matches-rendered",
        passed=False,
        blocking=False,
        detail=(
            f"{len(differences)} field(s) drifted from the rendered manifest: {listed}. "
            "Adoption will re-assert git and that WILL churn — reconcile first if you "
            "want to measure the handoff itself"
        ),
    )


def diff_live_against_rendered(
    rendered: dict[str, Any], live: dict[str, Any], path: str = ""
) -> list[str]:
    """Field paths where ``live`` no longer carries what ``rendered`` declares.

    One-directional on purpose: extra fields in the live object are the API
    server's defaults (clusterIP, creationTimestamp, status, …) and reporting
    them would bury the two fields that actually matter.
    """
    differences: list[str] = []
    if isinstance(rendered, dict) and isinstance(live, dict):
        for key, want in rendered.items():
            if key in _ADOPTION_ANNOTATIONS:
                continue
            here = f"{path}.{key}" if path else key
            if key not in live:
                differences.append(f"{here} (missing)")
            else:
                differences.extend(diff_live_against_rendered(want, live[key], here))
    elif isinstance(rendered, list) and isinstance(live, list):
        if len(rendered) != len(live):
            differences.append(f"{path} (length {len(live)} != {len(rendered)})")
        else:
            for index, (want, got) in enumerate(zip(rendered, live)):
                differences.extend(diff_live_against_rendered(want, got, f"{path}[{index}]"))
    elif rendered != live:
        differences.append(f"{path} ({live!r} != {rendered!r})")
    return differences


def rollback_commands(terraform_address: str, release: str, namespace: str) -> list[str]:
    """
    The exact way back to single (Terraform) ownership.

    Emitted up front rather than looked up mid-incident: partial adoption leaves
    dual ownership, which drifts silently until someone notices.
    """
    return [
        f"terraform import {terraform_address} {namespace}/{release}",
        f"helm history {release} -n {namespace}   # revision must match the recorded baseline",
    ]


def preflight(
    *,
    release: str,
    namespace: str,
    revision: int | None,
    resources: list[dict[str, Any]],
    commits_ahead: int,
    remote_configured: bool = True,
    snapshot_taken: bool = False,
    drift: list[str] | None = None,
) -> HandoffPreflight:
    """Run every check. Safe only if no blocking check failed."""
    return HandoffPreflight(
        release=release,
        namespace=namespace,
        revision=revision,
        findings=[
            check_baseline_recorded(revision),
            check_ownership(resources, release, namespace),
            check_stateful(resources, snapshot_taken),
            check_source_reachable(commits_ahead, remote_configured),
            check_live_matches_rendered(drift or []),
        ],
    )
