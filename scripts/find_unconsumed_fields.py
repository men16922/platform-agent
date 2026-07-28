"""Find declared-but-unread fields — the defect class this repo keeps paying for.

Six times in two days a field was declared, populated, stored, and read by
nobody: tenant grants the read path consumed but no writer could produce,
runbooks no alarm could select, `resource_types`, `assert_health_check_passing`,
a `reason` filled with a copy of `metric_name`. Every one was found by accident.

This parses every ClassDef under src/agents, collects annotated fields, and
counts reads (attribute and dict-key access) across the tree. A field whose only
appearance is its own declaration is a candidate.

CANDIDATES ARE NOT DEFECTS. Response/DTO fields are serialised out to callers
and legitimately unread here, and `self.x` forms can slip past the pattern
(`TokenBroker.signing_key` did). Every hit needs reading before it is believed.

    python scripts/find_unconsumed_fields.py
"""
import ast, pathlib, re, sys, collections

ROOT = pathlib.Path("src/agents")
files = [p for p in ROOT.rglob("*.py") if "cdk.out" not in str(p)]
source = {p: p.read_text(encoding="utf-8") for p in files}
all_text = "\n".join(source.values())
test_text = "\n".join(p.read_text(encoding="utf-8") for p in pathlib.Path("tests").glob("*.py"))

declared = []  # (module, class, field)
for path, text in source.items():
    try:
        tree = ast.parse(text)
    except SyntaxError:
        continue
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for stmt in node.body:
            if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                declared.append((str(path), node.name, stmt.target.id))

def reads(field):
    # attribute access, dict-key access, or kwarg use anywhere other than the
    # declaration line itself
    pats = [rf"\.{re.escape(field)}\b", rf"[\"']{re.escape(field)}[\"']"]
    return sum(len(re.findall(p, all_text)) for p in pats)

def test_reads(field):
    pats = [rf"\.{re.escape(field)}\b", rf"[\"']{re.escape(field)}[\"']"]
    return sum(len(re.findall(p, test_text)) for p in pats)

seen = collections.Counter(f for _, _, f in declared)
rows = []
for path, cls, field in declared:
    if field.startswith("_"):
        continue
    n = reads(field)
    if n <= 1:  # only the declaration itself
        rows.append((n, test_reads(field), cls, field, path))
rows.sort()
for n, t, cls, field, path in rows:
    print(f"src_reads={n} test_reads={t}  {cls}.{field}   ({path})")
print(f"\n{len(rows)} candidates out of {len(declared)} declared fields")
