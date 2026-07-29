"""Find record keys the dashboard reads that no writer in this repo produces.

`find_unconsumed_fields.py` sweeps one direction — "who declares a field nobody
reads" — and that caught nine defects. It structurally cannot catch the reverse,
which is the more expensive shape: a *reader* consuming a key no *writer* emits.
Those neither crash nor read as absent, they render a fallback. Every AWS-live
incident showed "confidence n/a" for the life of that view, and every weekly
on-call report sent `average_mttr_minutes: 0.0` with complete confidence,
because the reading side was right and the producing side was silent.

So this walks the store boundary the other way:

  writers  = string keys of dict literals inside a function that writes a record
             (a put/update call, a JSON dump, a local-store append), plus
             `item["key"] = ...` subscript assignments — the form the most
             recent incident fixes were written in
  readers  = keys the dashboard pulls off an *untyped* record: identifiers bound
             to `Record<string, unknown>` (a mapper parameter or an `as` cast).
             Reading `.severity` off an already-typed `Incident` is not a store
             read and would drown the signal.

CANDIDATES ARE NOT DEFECTS — same rule as the forward sweep. Two known sources
of false positives, both left in deliberately rather than papered over:

  * Third-party producers. Readers legitimately consume keys emitted by
    Alertmanager, boto3, an OAuth profile or a Next.js request body, and those
    writers are not in this repo.
  * Nested literals. A dict built by a helper and embedded by its caller
    (`cost_metrics`) is reported key-by-key, because the helper itself does not
    write. That noise is worth keeping: it is how the rolled-back-deployment
    cost panel was found — the keys were nested *and* one of three writers
    omitted the whole block.

The opposite direction is intentionally not reported here. "Written but nobody
reads" is the forward sweep's job, and it does it at field granularity; doing it
on raw dict keys drowns in k8s manifests, HTTP headers and CDK config.

    python scripts/find_unwritten_keys.py
"""

import ast
import collections
import pathlib
import re

PY_ROOT = pathlib.Path("src")
TS_ROOT = pathlib.Path("dashboard/src")

# Containing one of these makes a function a record-writing site, so its dict
# literals are record shapes. Derived from the call rather than a list of known
# store modules — a new one is picked up for free.
WRITE_CALLS = {
    "put_item",
    "update_item",
    "batch_write_item",
    "transact_write_items",
    "put_record",
    "write",
    "writelines",
    "dumps",
    "dump",
    "append",
}


SKIP_DIRS = ("cdk.out", "node_modules", "__pycache__")


def _py_files():
    # Vendored CDK handlers under src/stacks/node_modules are not our writers;
    # counting them inflates the producer set and hides real candidates.
    return [p for p in PY_ROOT.rglob("*.py") if not any(d in p.parts for d in SKIP_DIRS)]


def _ts_files():
    out = []
    for pattern in ("*.ts", "*.tsx"):
        out += [
            p
            for p in TS_ROOT.rglob(pattern)
            if "node_modules" not in str(p) and not p.name.endswith(".d.ts")
        ]
    return out


def collect_written_keys():
    """Keys a Python writer puts into a stored record."""
    written = collections.defaultdict(set)  # key -> {"path:func", ...}
    for path in _py_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            calls = {
                sub.func.attr
                for sub in ast.walk(node)
                if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute)
            }
            if not (calls & WRITE_CALLS):
                continue
            where = f"{path}:{node.name}"
            for sub in ast.walk(node):
                # `{"key": value}`
                if isinstance(sub, ast.Dict):
                    for key in sub.keys:
                        if isinstance(key, ast.Constant) and isinstance(key.value, str):
                            written[key.value].add(where)
                # `item["key"] = value` — how the incident fixes were written, and
                # invisible to a dict-literal-only sweep.
                elif isinstance(sub, ast.Assign):
                    for target in sub.targets:
                        if (
                            isinstance(target, ast.Subscript)
                            and isinstance(target.slice, ast.Constant)
                            and isinstance(target.slice.value, str)
                        ):
                            written[target.slice.value].add(where)
    return written


def collect_ts_record_reads():
    """Keys the dashboard pulls off an untyped record."""
    reads = collections.defaultdict(set)
    param_pat = re.compile(
        r"(?:\(|,)\s*(\w+)\s*:\s*Record<string,\s*(?:unknown|any)>"
        r"|const\s+(\w+)\s*=\s*\w+\s+as\s+Record<string,\s*(?:unknown|any)>"
    )
    # Array/Object built-ins reached through a record identifier are not keys.
    builtins = {
        "map", "filter", "find", "forEach", "flatMap", "reduce", "sort", "some",
        "every", "length", "slice", "join", "includes", "push", "concat",
        "toString", "valueOf", "hasOwnProperty",
    }
    for path in _ts_files():
        text = path.read_text(encoding="utf-8")
        names = {m.group(1) or m.group(2) for m in param_pat.finditer(text)}
        for name in names:
            for m in re.finditer(rf"\b{re.escape(name)}\.(\w+)\b", text):
                if m.group(1) not in builtins:
                    reads[m.group(1)].add(str(path))
            for m in re.finditer(rf"\b{re.escape(name)}\[[\"'](\w+)[\"']\]", text):
                reads[m.group(1)].add(str(path))
    return reads


def collect_py_record_reads():
    """`.get("key")` / `["key"]` reads — the other consumer side, for context."""
    reads = collections.defaultdict(set)
    for path in _py_files():
        text = path.read_text(encoding="utf-8")
        for m in re.finditer(r"\.get\(\s*[\"'](\w+)[\"']", text):
            reads[m.group(1)].add(str(path))
        for m in re.finditer(r"\[\s*[\"'](\w+)[\"']\s*\]", text):
            reads[m.group(1)].add(str(path))
    return reads


def main():
    written = collect_written_keys()
    ts_reads = collect_ts_record_reads()
    py_reads = collect_py_record_reads()

    rows = [(k, sorted(w), k in py_reads) for k, w in sorted(ts_reads.items()) if k not in written]
    print("=== READ BY THE DASHBOARD, WRITTEN BY NOBODY IN src/ ===\n")
    for key, where, also_py in rows:
        flag = "  [also read in python]" if also_py else ""
        print(f"  {key}{flag}")
        for w in where:
            print(f"      {w}")
    print(f"\n{len(rows)} candidates out of {len(ts_reads)} keys read off untyped records")
    print(f"({len(written)} distinct keys written by {PY_ROOT}/)")


if __name__ == "__main__":
    main()
