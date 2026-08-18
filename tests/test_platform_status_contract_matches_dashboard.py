"""Phase 0's DoD says "로더·타입 검증 (py/ts)". The py half is heavily guarded;
the ts half was not guarded at all.

`dashboard/src/lib/platform-registry.ts` is deliberately **not** a second YAML
reader — it says so in its own header, and that is correct: parsing the registry
in the hub would reintroduce the spoke-credential concentration the design
exists to avoid. So there is no second loader to disagree with.

But there IS a contract, and it crosses a network:

    src/agents/platform/addon_status.py :: NormalizedAddonStatus.to_dict()
        --- pushed by the spoke agent --->
    dashboard/src/lib/platform-registry.ts :: interface NormalizedAddonStatus

Fifteen test files in this repo already read TS source to pin exactly this kind
of producer/consumer pair. This one was missed, and it is the pair with the
sharpest failure mode, because the TS side spells the two axes as **union
literals**:

    export type SyncState = "synced" | "drifted" | "n/a" | "unknown";

A union is a closed set. Adding one enum member on the Python side — the change
that `applicable=False` / `sync n/a` already made once (M37) — produces a value
the dashboard's own type says cannot exist. `tsc` stays green, because the value
crossed a network and the compiler never sees it (STATUS Risk 7, learned by
crashing a live page). The row then renders through whatever branch the UI's
fallback happens to take, which is the "silently degraded" outcome the two-axis
model was designed to prevent.

Measured 2026-08-18 before writing this: the two sides agree exactly (9 fields,
4 sync values, 5 health values). So this guard does not fix a defect — it holds
a boundary that nothing was holding.

Both directions are asserted, because they fail differently:
  * py has a value ts lacks  → the dashboard receives a value it cannot type
  * ts has a value py lacks  → the UI branches on a state no producer emits

Deliberately NOT asserted: the `TenancyPosture` fields. Those are explicitly
optional-with-fallback by design (same Risk 7 comment in that file), so a
producer that lags the UI is the *expected* state there, not a drift.
"""

from __future__ import annotations

import ast
import pathlib
import re

REPO = pathlib.Path(__file__).resolve().parents[1]
PY_SRC = REPO / "src" / "agents" / "platform" / "addon_status.py"
TS_SRC = REPO / "dashboard" / "src" / "lib" / "platform-registry.ts"


# ---------------------------------------------------------------------------
# Producer side (Python)
# ---------------------------------------------------------------------------

def _py_tree() -> ast.Module:
    return ast.parse(PY_SRC.read_text(encoding="utf-8"))


def _py_enum_values(name: str) -> set[str]:
    """String values of an ``Enum`` class body — the wire vocabulary."""
    for node in ast.walk(_py_tree()):
        if isinstance(node, ast.ClassDef) and node.name == name:
            return {
                sub.value.value
                for sub in node.body
                if isinstance(sub, ast.Assign)
                and isinstance(sub.value, ast.Constant)
                and isinstance(sub.value.value, str)
            }
    raise AssertionError(f"{name} not found in {PY_SRC.name}")


def _py_wire_keys() -> set[str]:
    """Keys ``to_dict`` can emit.

    Both shapes count: keys in the dict literal (always present) and the
    conditional ``result["k"] = ...`` assignments below it. The consumer has to
    type both — an optional field is still a field it must know about.
    """
    for node in ast.walk(_py_tree()):
        if not (isinstance(node, ast.ClassDef) and node.name == "NormalizedAddonStatus"):
            continue
        for sub in node.body:
            if not (isinstance(sub, ast.FunctionDef) and sub.name == "to_dict"):
                continue
            keys: set[str] = set()
            for inner in ast.walk(sub):
                if isinstance(inner, ast.Dict):
                    keys |= {
                        k.value for k in inner.keys
                        if isinstance(k, ast.Constant) and isinstance(k.value, str)
                    }
                elif isinstance(inner, ast.Subscript) and isinstance(
                    inner.slice, ast.Constant
                ) and isinstance(inner.slice.value, str):
                    keys.add(inner.slice.value)
            return keys
    raise AssertionError("NormalizedAddonStatus.to_dict not found")


# ---------------------------------------------------------------------------
# Consumer side (TypeScript) — read as source; this repo has no TS runner.
# ---------------------------------------------------------------------------

def _ts() -> str:
    return TS_SRC.read_text(encoding="utf-8")


def _ts_union_values(name: str) -> set[str]:
    m = re.search(rf"export type {name}\s*=(.*?);", _ts(), re.S)
    assert m, f"export type {name} not found in {TS_SRC.name}"
    return set(re.findall(r'"([^"]+)"', m.group(1)))


def _ts_interface_fields(name: str) -> set[str]:
    m = re.search(rf"export interface {name} \{{(.*?)\n\}}", _ts(), re.S)
    assert m, f"export interface {name} not found in {TS_SRC.name}"
    body = re.sub(r"/\*.*?\*/", "", m.group(1), flags=re.S)  # strip JSDoc
    body = re.sub(r"//[^\n]*", "", body)
    return set(re.findall(r"^\s*(\w+)\??\s*:", body, re.M))


# ---------------------------------------------------------------------------
# 1. Guard the guard — a parser that finds nothing passes vacuously
# ---------------------------------------------------------------------------

class TestBothSidesWereActuallyParsed:
    """Every assertion below is a set comparison, and two empty sets are equal."""

    def test_the_python_producer_was_read(self):
        assert len(_py_wire_keys()) >= 8, _py_wire_keys()
        assert len(_py_enum_values("SyncState")) >= 4
        assert len(_py_enum_values("HealthState")) >= 5

    def test_the_typescript_consumer_was_read(self):
        assert len(_ts_interface_fields("NormalizedAddonStatus")) >= 8
        assert len(_ts_union_values("SyncState")) >= 4
        assert len(_ts_union_values("HealthState")) >= 5


# ---------------------------------------------------------------------------
# 2. The contract itself
# ---------------------------------------------------------------------------

class TestPushedStatusMatchesWhatTheDashboardTypes:
    def test_field_names_agree(self):
        py, ts = _py_wire_keys(), _ts_interface_fields("NormalizedAddonStatus")
        assert py == ts, (
            f"pushed-only {sorted(py - ts)} / typed-only {sorted(ts - py)} — "
            "the spoke pushes this dict straight into the dashboard's read model, "
            "so a field on one side and not the other is either data no view can "
            "reach or a view branching on data no producer sends"
        )

    def test_sync_axis_vocabulary_agrees(self):
        py, ts = _py_enum_values("SyncState"), _ts_union_values("SyncState")
        assert py == ts, (
            f"producer-only {sorted(py - ts)} / consumer-only {sorted(ts - py)} — "
            "SyncState is a closed union in TS; a value the producer emits and the "
            "union omits is untypeable at runtime and tsc cannot see it (Risk 7)"
        )

    def test_health_axis_vocabulary_agrees(self):
        py, ts = _py_enum_values("HealthState"), _ts_union_values("HealthState")
        assert py == ts, (
            f"producer-only {sorted(py - ts)} / consumer-only {sorted(ts - py)} — "
            "a health value the dashboard cannot type is rendered by whichever "
            "fallback branch happens to catch it, which is how 'unknown' becomes "
            "indistinguishable from 'healthy'"
        )

    def test_not_applicable_survives_the_crossing(self):
        """M37's decision only exists if it reaches the reader.

        Managed backends render no manifest and report the sync axis as `n/a`
        with `applicable=False`. Both halves of that have to be typed on the
        dashboard side or the honest answer arrives as an untypeable one.
        """
        assert "n/a" in _py_enum_values("SyncState")
        assert "n/a" in _ts_union_values("SyncState")
        assert "applicable" in _py_wire_keys()
        assert "applicable" in _ts_interface_fields("NormalizedAddonStatus")
