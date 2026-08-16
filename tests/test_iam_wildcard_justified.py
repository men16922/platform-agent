"""
Every `Resource: "*"` in the CDK stacks must say why.

`AGENT_BRIEF` used to state the guardrail as "`Resource:\"*\"` 금지". Measured
2026-08-15: `incident_agent_stack.ts` has seven of them and **all seven are
actions AWS gives no resource types to** — the ban was unconditionally false, and
five of the seven carried no explanation. A rule nobody can satisfy is the shape
this repo already named: *만족 불가능한 규칙은 우회를 습관으로 만든다* (the ₩20
budget, `2026-08-08-phase4-scope-and-cost.md` §2).

So the rule was rewritten to the one that can hold — **no *unexplained* wildcard**
— and this enforces it. Verified against the AWS Service Authorization Reference
on 2026-08-16 (via `iann0036/iam-dataset`, which mirrors it as JSON; the AWS page
itself is JS-rendered and cannot be read):

    cloudwatch:GetMetricStatistics   resource types: none
    xray:GetTraceSummaries           resource types: none
    xray:BatchGetTraces              resource types: none
    states:SendTaskSuccess           resource types: none
    states:SendTaskFailure           resource types: none
    states:ListStateMachines         resource types: none
    cloudwatch:ListMetrics           resource types: ['dataset']  ← the exception

⚠️ `ListMetrics` is the one that *does* have a resource type — `dataset`, for
Metrics Insights, which is not what listing metrics uses. Reporting all seven as
"no resource types" would have been a tidier sentence and a false one.

The check is adjacency, not prose quality: a comment must sit directly above the
`PolicyStatement`. That is deliberately mechanical — it cannot judge whether the
reason is *true*, only that someone had to write one.
"""

from __future__ import annotations

import pathlib
import re
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _tracked_stacks() -> list[pathlib.Path]:
    out = subprocess.run(
        ["git", "ls-files", "src/stacks/*.ts"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout.split()
    # `src/stacks/cdk.out/` is an untracked build artefact holding copies of this
    # tree — `git ls-files` keeps it out. Walking the filesystem would not.
    return [ROOT / rel for rel in out]


def _wildcard_statements() -> list[tuple[str, int, list[str], bool]]:
    """(file, line, actions, has_adjacent_comment) for each `resources: ['*']`."""
    found = []
    for path in _tracked_stacks():
        lines = path.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            if "resources: ['*']" not in line and 'resources: ["*"]' not in line:
                continue
            j = i
            while j > 0 and "PolicyStatement({" not in lines[j]:
                j -= 1
            actions = re.findall(r"'([a-z0-9-]+:[A-Za-z*]+)'", "\n".join(lines[j:i]))
            documented = j > 0 and lines[j - 1].strip().startswith("//")
            found.append((path.relative_to(ROOT).as_posix(), i + 1, actions, documented))
    return found


STATEMENTS = _wildcard_statements()
IDS = [f"{f}:{n}" for f, n, _, _ in STATEMENTS]


def test_the_sweep_finds_the_known_statements():
    """Vacuity check — an anchor change must not silently empty this file."""
    assert len(STATEMENTS) >= 7, STATEMENTS


@pytest.mark.parametrize("path,line,actions,documented", STATEMENTS, ids=IDS)
def test_wildcard_resource_is_explained(path, line, actions, documented):
    assert documented, (
        f"{path}:{line} grants {actions} on `Resource: \"*\"` with no comment above the "
        "statement. AGENT_BRIEF's guardrail is 'no *unexplained* wildcard' — most AWS "
        "read actions genuinely have no resource types, but the next reader cannot tell "
        "that from a bare `*`."
    )


def test_the_site_that_taught_us_adjacency_is_covered():
    """Pins the checking rule itself, through the same sweep the guard uses.

    The `states:ListStateMachines` grant had its reason four lines up, above the
    enclosing `if` — true, and invisible to a reader looking at the statement.
    Two hand-written scans of this file disagreed about that site before the
    comment was moved down, which is why the rule is *adjacency*.

    Asked through `_wildcard_statements()` rather than a second hand-rolled scan:
    a checker that disagrees with the checker is how this went wrong the first
    time.
    """
    listing = [s for s in STATEMENTS if "states:ListStateMachines" in s[2]]
    assert len(listing) == 1, listing
    assert listing[0][3], "the grant whose comment sat above the enclosing `if` is unexplained again"
