"""The read-model doc drifted from the writers because nothing imports it.

`dashboard/src/lib/activity-model.ts` documents the single-table design. No
module imports it, so nothing broke as it went stale — and it went far:

  * it declared `duration_ms` and `error_message`, which no writer produces
  * it omitted `trace`, `cost_metrics` and `deployment_id` — the three fields
    the deployment detail page is built on
  * it declared `ttl` and the GSI1 keys as *required*, when the writer that
    produces almost every row in practice (`ai/deploy_recorder.py`) writes
    neither, so those rows never expire and never appear in GSI1

Reading it would have misled someone into adding a provider-scoped GSI1 query
that silently returned a subset. That is the same defect class as the fields
this milestone chased, one level up: the declaration is the thing nobody reads.

So the doc is derived-checked here rather than trusted. This asserts the two
directions that matter and would have caught every drift above:

  1. no field is declared for a row type that no writer produces
  2. no field is written by *every* writer of a row type while being absent
     from the documented core

Deliberately NOT asserted: that the doc lists every optional field. Partial
fields are real (two writer families, neither a superset), and requiring the
union would just make the doc restate the writers instead of explaining them.
"""

import ast
import pathlib
import re

REPO = pathlib.Path(__file__).resolve().parents[1]
MODEL_TS = REPO / "dashboard" / "src" / "lib" / "activity-model.ts"
WRITERS = [
    REPO / "src" / "agents" / "ai" / "deploy_recorder.py",
    REPO / "src" / "agents" / "operations" / "activity_writer.py",
]

# Table keys and doc-only scaffolding that the writers set positionally or that
# describe the record rather than living in it.
NOT_WRITER_FIELDS = {"PK", "SK"}


def written_keys_by_pk():
    """{"DEPLOY": {"writer:func": {keys...}}} — the real shapes, from the code."""
    out: dict[str, dict[str, set[str]]] = {}
    for path in WRITERS:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for sub in ast.walk(node):
                if not isinstance(sub, ast.Dict):
                    continue
                pairs = {
                    k.value: v
                    for k, v in zip(sub.keys, sub.values)
                    if isinstance(k, ast.Constant) and isinstance(k.value, str)
                }
                pk = pairs.get("PK")
                if isinstance(pk, ast.Constant) and isinstance(pk.value, str):
                    out.setdefault(pk.value, {})[f"{path.name}:{node.name}"] = set(pairs)
    return out


def declared_fields():
    """{"InterfaceName": {field, ...}} from the documentation file."""
    src = MODEL_TS.read_text(encoding="utf-8")
    out = {}
    for m in re.finditer(r"export interface (\w+)[^{]*\{(.*?)\n\}", src, re.S):
        out[m.group(1)] = set(re.findall(r"^\s{2}(\w+)\??\s*:", m.group(2), re.M))
    return out


# interface pairs: (core interface, full interface, PK value)
ROW_TYPES = [
    ("DeploymentRecordCore", "DeploymentRecord", "DEPLOY"),
    ("AgentActivityRecordCore", "AgentActivityRecord", "ACTIVITY"),
    (None, "ProviderHealthRecord", "HEALTH"),
]


def _all_declared(decl, core, full):
    return decl.get(full, set()) | (decl.get(core, set()) if core else set())


def test_the_sweep_finds_both_writer_families():
    """Guard the guard — deriving from nothing would pass everything."""
    written = written_keys_by_pk()
    assert set(written) >= {"DEPLOY", "ACTIVITY", "HEALTH"}, written.keys()
    writers = {w for m in written.values() for w in m}
    assert any("deploy_recorder" in w for w in writers), writers
    assert any("activity_writer" in w for w in writers), writers


def test_the_doc_declares_the_expected_interfaces():
    decl = declared_fields()
    for core, full, _ in ROW_TYPES:
        assert full in decl, f"{full} missing from {MODEL_TS.name}"
        if core:
            assert core in decl, f"{core} missing from {MODEL_TS.name}"


def test_no_field_is_declared_that_no_writer_produces():
    """Catches `duration_ms` / `error_message` — invented shape."""
    written, decl = written_keys_by_pk(), declared_fields()
    for core, full, pk in ROW_TYPES:
        produced = set().union(*written[pk].values())
        phantom = _all_declared(decl, core, full) - produced - NOT_WRITER_FIELDS
        assert not phantom, (
            f"{full} declares {sorted(phantom)}, which no writer of PK={pk} produces — "
            "a reader written against this doc would consume fields that are never there"
        )


def test_every_universally_written_field_is_in_the_documented_core():
    """Catches the omissions: a field *all* writers emit belongs in the core.

    `trace`/`cost_metrics` are correctly optional (one writer family), but
    anything every writer produces is part of the row's identity, and leaving it
    out is how this doc lost `type` and `created_at`-adjacent correlation keys.
    """
    written, decl = written_keys_by_pk(), declared_fields()
    for core, full, pk in ROW_TYPES:
        universal = set.intersection(*written[pk].values()) - NOT_WRITER_FIELDS
        missing = universal - _all_declared(decl, core, full)
        assert not missing, (
            f"every writer of PK={pk} emits {sorted(missing)}, but {core or full} "
            "does not document it"
        )


def test_ttl_and_gsi1_are_not_documented_as_guaranteed():
    """The specific false claim: retention and the provider index.

    Both are written by `activity_writer` only. Declaring them required told the
    reader that every row expires and is indexed by provider; neither is true of
    the agent path, which writes almost every row. If a future change makes them
    universal, the test above will demand they move into the core and this one
    can go.
    """
    written = written_keys_by_pk()
    src = MODEL_TS.read_text(encoding="utf-8")
    for field in ("ttl", "GSI1PK", "GSI1SK"):
        for pk in ("DEPLOY", "ACTIVITY"):
            emitters = [w for w, keys in written[pk].items() if field in keys]
            assert emitters and len(emitters) < len(written[pk]), (
                f"{field} on PK={pk} is now written by {emitters or 'nobody'} — "
                "update the doc and this guard together"
            )
        # Every declaration site, not any of them — these fields are declared on
        # both DEPLOY and ACTIVITY, and checking `any` passed while one of the
        # two had been made required.
        sites = re.findall(rf"^\s+{field}(\??):", src, re.M)
        assert sites, f"{field} is no longer declared in the doc at all"
        assert all(optional for optional in sites), (
            f"{field} is declared as required at {sites.count('')} of {len(sites)} sites; "
            "it must stay optional everywhere while only one writer family emits it"
        )
    assert "NEVER EXPIRE" in src, (
        "the doc must keep stating that agent-path rows carry no ttl — it previously "
        "claimed a 30-day retention that does not hold"
    )
