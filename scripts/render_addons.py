"""Render the delivery manifests for one tenant/env's declared add-ons.

Read-only. Prints YAML to stdout; applying is a separate, deliberate act — the
same rule `render_tenancy.py` follows, for the same reason (these objects install
software into a shared cluster).

Why this exists: the registry declared add-ons that nothing could install from the
registry alone. Chart and version were expressed, the values seam arrived later,
and the repository URL lived only in `infra/onprem/addons/*.tf` — so every live
install was assembled at a prompt with the missing pieces pasted in by hand, and
what got installed was whatever the operator typed that night. The three things a
Helm-sourced Application needs (repo, chart+version, values) now all come from the
registry, and this script is the one path that puts them together.

Cluster-scoped capabilities are NOT rendered. That is the delivery contract's
refusal, not this script's opinion: a per-tenant `argo-rollouts` is a second
controller reconciling the first one's objects, with nothing in any log to say so.
They are listed on stderr, because a silent omission reads as "this tenant has no
observability" rather than "observability is a shared cluster install".

Usage:
  python scripts/render_addons.py <tenant> -e <env> [--capability NAME] [--check]
  python scripts/render_addons.py acme -e dev | kubectl apply -f -

Exit codes:
  0 = rendered, every namespace-scoped add-on is installable as printed
  1 = rendered, but something declared cannot be installed (missing repo/values),
      or the whole env resolved to cluster-scoped capabilities and nothing was output
  2 = could not render (unknown tenant/env, or an unsupported delivery engine)
"""

from __future__ import annotations

import argparse
import os
import sys

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.platform.adapters import build_delivery_adapter  # noqa: E402
from src.agents.platform.delivery import desired_addons  # noqa: E402
from src.agents.platform.registry import load_registry  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tenant")
    parser.add_argument("-e", "--env", required=True)
    parser.add_argument("--capability", action="append", default=None,
                        help="render only these capabilities (repeatable)")
    parser.add_argument("--check", action="store_true",
                        help="report installability only; print no manifests")
    args = parser.parse_args()

    registry = load_registry()
    try:
        tenant = registry.tenant(args.tenant)
        env = registry.environment(args.tenant, args.env)
    except KeyError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    declared = desired_addons(
        tenant, env, registry.wave_for, registry.scope_of, registry.values_for
    )
    if args.capability:
        wanted = set(args.capability)
        unknown = wanted - {a.capability for a in declared}
        if unknown:
            print(
                f"ERROR: {args.tenant}/{args.env} declares no capability "
                f"{', '.join(sorted(unknown))}",
                file=sys.stderr,
            )
            return 2
        declared = [a for a in declared if a.capability in wanted]

    shared = [a for a in declared if a.is_cluster_singleton]
    renderable = [a for a in declared if not a.is_cluster_singleton]

    problems = {
        a.capability: reason
        for a in renderable
        if (reason := registry.uninstallable_reason(a.capability))
    }
    installable = [a for a in renderable if a.capability not in problems]

    manifests = []
    for addon in installable:
        adapter = build_delivery_adapter(env.delivery, registry.repo_for(addon.capability))
        manifests.extend(adapter.render(tenant, env, [addon]))

    if manifests and not args.check:
        print(yaml.safe_dump_all(manifests, sort_keys=False))

    print(
        f"# {args.tenant}/{args.env} via {env.delivery} on {env.cluster}: "
        f"{len(manifests)} manifest(s) for {', '.join(a.capability for a in installable) or 'nothing'}",
        file=sys.stderr,
    )

    if shared:
        # Named, not dropped. "Not rendered" and "not provided" look identical in
        # an empty diff, and only one of them is correct here.
        names = sorted(a.capability for a in shared)
        print(
            "# SHARED, NOT PER-TENANT: "
            f"{', '.join(names)} {'is' if len(names) == 1 else 'are'} cluster-scoped in the\n"
            "#   catalog. One installation serves every tenant; rendering a copy per tenant\n"
            "#   would start a second controller over the same objects. The tenant's share\n"
            "#   is an instance (a Prometheus CR, a Rollout), not another operator.",
            file=sys.stderr,
        )

    for capability, why in sorted(problems.items()):
        print(f"# NOT INSTALLABLE: {capability} — {why}", file=sys.stderr)

    if problems:
        return 1
    if not manifests:
        # Exit 1 with no output on purpose: a caller piping into `kubectl apply`
        # gets an empty stream either way, and only the exit code can tell it
        # "nothing to do" from "everything here is shared".
        print(
            "# Nothing to apply — every declared capability here is a shared cluster install.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
