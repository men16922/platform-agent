#!/usr/bin/env python3
"""Render the RBAC identity the deploy path runs as.

    python scripts/render_deploy_identity.py | kubectl apply -f -
    scripts/mint_deploy_kubeconfig.sh          # -> a kubeconfig for it

Why this exists: measured 2026-07-30, a deploy ran as the ambient kubeconfig, which
on the live kind cluster was cluster-admin — the identity that rolls out a service
could read every secret and delete every tenant's namespace
(`docs/evidence/deploy-path-authorization.log`).

**What it grants is derived from what the adapters actually run**, not from a wish
list: `ClusterRole` rules below are justified line by line against the kubectl
commands in `src/agents/adapters/deployment/*.py` and the read-only tools in
`src/agents/ai/ops_tools.py`. `tests/test_deploy_identity.py` re-derives the verb
set from those call sites, so a new adapter command fails the guard instead of
quietly needing a permission nobody granted.

**What it deliberately does NOT grant** — the whole point:

    secrets                  the deploy path never reads one; ambient could read all
    namespaces (write)       creating tenant boundaries is `setup_tenancy`'s job (D30)
    rbac.authorization.k8s.io  no identity may widen itself
    nodes / persistentvolumes  cluster infrastructure is Terraform-owned (D30)

**Scope honesty.** This is cluster-wide over a narrow set of verbs, not per-tenant.
One "platform deployer" identity for every deploy: it bounds *what* a deploy can do,
not *whose* namespace it touches. Per-tenant deploy credentials need the request to
name a tenant, which it does not (결정 5 C/D →
`docs/plans/2026-07-30-deploy-request-tenant-scoping.md`). Do not describe this as
tenant isolation anywhere.
"""

from __future__ import annotations

import argparse
import json
import sys

#: Where the deployer's ServiceAccount lives. Its own namespace so a tenant with
#: edit rights in their own namespace cannot mint a token for it.
DEFAULT_NAMESPACE = "platform-agent-system"
DEFAULT_NAME = "platform-agent-deployer"

# Each rule carries the call site that needs it. The guard in
# tests/test_deploy_identity.py checks the other direction — that every verb the
# adapters exercise is covered here — so this comment and the code cannot drift
# apart silently the way the read model did (M13 ⑪).
RULES: list[dict] = [
    {
        # `kubectl apply` (create+patch), `rollout status` (get+watch),
        # `rollout undo` (get+patch), `get deployment -o json` (get).
        "apiGroups": ["apps"],
        "resources": ["deployments"],
        "verbs": ["get", "list", "watch", "create", "update", "patch"],
    },
    {
        # `rollout undo` reads the revision history off the ReplicaSets before it
        # patches the Deployment. Read-only: nothing here creates or deletes one.
        "apiGroups": ["apps"],
        "resources": ["replicasets"],
        "verbs": ["get", "list", "watch"],
    },
    {
        # The manifest is a Deployment + a ClusterIP Service.
        "apiGroups": [""],
        "resources": ["services"],
        "verbs": ["get", "list", "watch", "create", "update", "patch"],
    },
    {
        # ops_tools: list_pods, rollout_status. Read-only.
        "apiGroups": [""],
        "resources": ["pods"],
        "verbs": ["get", "list", "watch"],
    },
    {
        # ops_tools.get_logs — `kubectl logs deployment/<x>`.
        "apiGroups": [""],
        "resources": ["pods/log"],
        "verbs": ["get"],
    },
    {
        # ops_tools.describe_deployment prints recent events.
        "apiGroups": ["", "events.k8s.io"],
        "resources": ["events"],
        "verbs": ["get", "list", "watch"],
    },
    {
        # ops_tools.list_namespaces — reading the list, never creating one.
        "apiGroups": [""],
        "resources": ["namespaces"],
        "verbs": ["get", "list", "watch"],
    },
]

#: Asserted by the guard. Holding any of these would put the deployer back within
#: reach of the things the ambient credential could do.
FORBIDDEN_RESOURCES = {
    "secrets", "serviceaccounts", "roles", "rolebindings", "clusterroles",
    "clusterrolebindings", "nodes", "persistentvolumes",
}
#: Verbs that must never appear — `*` because it silently re-grants everything,
#: `delete` because nothing in the deploy path deletes a Kubernetes object
#: (teardown is `provision_tools`, and rollback is a patch, not a delete).
FORBIDDEN_VERBS = {"*", "delete", "deletecollection", "escalate", "bind", "impersonate"}


def manifests(name: str, namespace: str) -> list[dict]:
    return [
        {
            "apiVersion": "v1",
            "kind": "Namespace",
            "metadata": {"name": namespace},
        },
        {
            "apiVersion": "v1",
            "kind": "ServiceAccount",
            "metadata": {"name": name, "namespace": namespace},
        },
        {
            "apiVersion": "rbac.authorization.k8s.io/v1",
            "kind": "ClusterRole",
            "metadata": {
                "name": name,
                "annotations": {
                    "platform-agent/purpose": (
                        "the identity a deploy runs as; bounds what a deploy can do, "
                        "NOT whose namespace it touches (결정 5)"
                    ),
                },
            },
            "rules": RULES,
        },
        {
            "apiVersion": "rbac.authorization.k8s.io/v1",
            "kind": "ClusterRoleBinding",
            "metadata": {"name": name},
            "roleRef": {
                "apiGroup": "rbac.authorization.k8s.io",
                "kind": "ClusterRole",
                "name": name,
            },
            "subjects": [
                {"kind": "ServiceAccount", "name": name, "namespace": namespace}
            ],
        },
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default=DEFAULT_NAME)
    parser.add_argument("--namespace", default=DEFAULT_NAMESPACE)
    args = parser.parse_args(argv)

    doc = {"apiVersion": "v1", "kind": "List", "items": manifests(args.name, args.namespace)}
    json.dump(doc, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
