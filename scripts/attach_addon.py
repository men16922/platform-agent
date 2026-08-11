"""Attach an add-on to one tenant/env by editing exactly one registry file.

The driver for Phase 5's write path. Prints the diff by default and changes
nothing; `--write` applies it to the working tree; `--commit` also puts it on its
own branch as a path-limited commit. Opening the PR is left to the operator
(`gh pr create`), because pushing a branch is outward-facing and this script's job
ends at "here is the one-file change and here is what it says".

    python scripts/attach_addon.py acme prod logging 7.1.0
    python scripts/attach_addon.py acme prod logging 7.1.0 --write
    python scripts/attach_addon.py acme prod logging 7.1.0 --commit

`--commit` exists because the instruction it replaces was wrong. This script used
to print `git commit -am <title>`, and `-a` stages every modified tracked file —
so an operator with anything else dirty would open a PR touching files the plan
never named, from the tool whose one job is that the PR touches exactly one file.

Exit codes:
  0 = a plan was produced (and applied, with --write/--commit)
  1 = refused — the registry, the catalog, the blast-radius rule, or git said no

REFUSED GOES TO STDOUT, next to the plan it refused. The `--commit` refusal comes
*after* the file/branch/title/diff have already been printed, so with REFUSED on
stderr a piped copy showed a complete-looking plan and no sign that nothing was
committed. The reader's evidence of failure was the absence of the "committed
<sha>" line — and an absent line is not a verdict.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.agents.platform.registry_write import (  # noqa: E402
    RegistryWriteError,
    commit_attachment,
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
    parser.add_argument(
        "--commit", action="store_true",
        help="apply, branch, and commit that one path (local only — never pushes)",
    )
    args = parser.parse_args()

    try:
        plan = plan_addon_attachment(args.tenant, args.env, args.capability, args.version)
    except RegistryWriteError as exc:
        print(f"REFUSED: {exc}")
        return 1
    except Exception as exc:  # registry/catalog rejections carry their own wording
        print(f"REFUSED: {exc}")
        return 1

    print(f"file   : {plan.path.relative_to(REPO)}")
    print(f"branch : {plan.branch}")
    print(f"title  : {plan.title}")
    print()
    print(plan.diff(), end="")

    if not (args.write or args.commit):
        print("\n(dry run — pass --write to apply, --commit to also branch and commit)")
        return 0

    if args.commit:
        try:
            sha = commit_attachment(plan)
        except RegistryWriteError as exc:
            print(f"REFUSED: {exc}")
            return 1
        print(f"\ncommitted {sha[:12]} on {plan.branch} — one file, {plan.path.relative_to(REPO)}.")
        print("Nothing was pushed. Open the PR yourself:")
        print(f"  git push -u origin {plan.branch}")
        print(f"  gh pr create --title {plan.title!r} --body 'Attach {plan.capability}.'")
        return 0

    plan.path.write_text(plan.updated, encoding="utf-8")
    print(f"\napplied to {plan.path.relative_to(REPO)}. Open the PR yourself:")
    print(f"  git switch -c {plan.branch}")
    # `-- <path>`, never `-am`: `-a` would stage every other modified tracked file.
    print(f"  git commit -m {plan.title!r} -- {plan.path.relative_to(REPO)}")
    print(f"  git push -u origin {plan.branch}")
    print(f"  gh pr create --title {plan.title!r} --body 'Attach {plan.capability}.'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
