"""Attach an add-on to one tenant/env by editing exactly one registry file.

The driver for Phase 5's write path. Prints the diff by default and changes
nothing; `--write` applies it to the working tree. Opening the PR is left to the
operator (`gh pr create`), because pushing a branch is outward-facing and this
script's job ends at "here is the one-file change and here is what it says".

    python scripts/attach_addon.py acme prod logging 7.1.0
    python scripts/attach_addon.py acme prod logging 7.1.0 --write

Exit codes:
  0 = a plan was produced (and applied, with --write)
  1 = refused — the registry, the catalog, or the blast-radius rule said no
"""

from __future__ import annotations

import argparse
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.agents.platform.registry_write import (  # noqa: E402
    RegistryWriteError,
    plan_addon_attachment,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tenant")
    parser.add_argument("env")
    parser.add_argument("capability")
    parser.add_argument("version")
    parser.add_argument(
        "--write", action="store_true",
        help="apply the edit to the working tree (still does not commit or push)",
    )
    args = parser.parse_args()

    try:
        plan = plan_addon_attachment(args.tenant, args.env, args.capability, args.version)
    except RegistryWriteError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # registry/catalog rejections carry their own wording
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 1

    print(f"file   : {plan.path.relative_to(REPO)}")
    print(f"branch : {plan.branch}")
    print(f"title  : {plan.title}")
    print()
    print(plan.diff(), end="")

    if not args.write:
        print("\n(dry run — pass --write to apply)")
        return 0

    plan.path.write_text(plan.updated, encoding="utf-8")
    print(f"\napplied to {plan.path.relative_to(REPO)}. Open the PR yourself:")
    print(f"  git switch -c {plan.branch}")
    print(f"  git commit -am {plan.title!r}")
    print(f"  gh pr create --title {plan.title!r} --body 'Attach {plan.capability}.'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
