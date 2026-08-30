"""
Where detector/analyzer/decision are byte-identical across providers, they must stay so.

**The claim this file measured.** `NEXT_PLAN`'s maintenance rules say
*"detector/analyzer/decision은 SDK가 **90%+ 상이**해 의도적으로 DRY 안 함"*, and D15
spells out why: Pub/Sub vs EventGrid, Cloud Logging vs KQL, Firestore vs Cosmos,
Vertex Gemini vs Azure OpenAI. Measured 2026-08-30, that reason is right about
**what differs** and quiet about how little of the file it is:

    SDK 심볼에 닿는 줄        aws 2.9% · gcp 4.7% · azure 3.9%   (나머지 95%+는 SDK가 아니다)

    정규화 후 provider 쌍 유사도        detector   analyzer   decision
      gcp ↔ azure                        24.7%      69.7%      78.5%
      aws ↔ gcp                          11.8%      52.9%      26.5%

    8줄 이상 **글자 그대로 같은** 블록 (gcp↔azure)
      detector    0 블록 /   0줄  ← D15가 말한 그대로
      analyzer    6 블록 /  95줄  (gcp 186줄의 51%)
      decision    6 블록 / 135줄  (gcp 239줄의 56%)

So the decision not to DRY is defensible for `detector` and describes something
else for the other two. This file does not undo that decision — a 230-line
extraction across four modules is a structural change, and 작업 규칙 puts those
behind approval. It applies the refinement the repo already wrote for itself after
M18/M19:

    공유되는 게 **SDK가 아니라 계약**인 블록은 계약 모듈에 한 벌만 두고
    **provider 간 일치를 묻는 가드**로 묶는다 — 복사본 둘은 다음 고침이
    한쪽에만 닿는 방식이다.

Both halves of that have already cost this repo: M18 found three defects **copied
into two files**, and M23 found `Destroy` missing from AWS's list alone. Until the
extraction happens, this guard is the second half: a fix to one copy that does not
reach its twin goes red here.

⚠️ Pinned as a **table, not a discovery**. Sweeping for "functions that happen to
match today" would grow silently and turn every deliberate divergence into a
mystery failure. Diverging a pair is allowed — it just has to be an edit to
`IDENTICAL_ACROSS`, in the same commit, with a reason.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]

# (module, function) -> providers whose implementations were byte-identical when
# measured 2026-08-30, after stripping blank lines, comments, and indentation.
#
# `analyzer._fallback_analysis` is listed for gcp/azure because **AWS does not have
# it**: on LLM failure AWS returns a hardcoded `(msg, P2, 0.0)` while gcp/azure run
# a keyword heuristic that can return **P1**, and P1 maps to AUTO. That asymmetry is
# real and it is *closed*: `reconciliation.py` raises "P1 severity with low
# confidence" below 0.5 and `apply_gate` downgrades AUTO → APPROVE, and the fallback
# returns 0.3. Traced end-to-end 2026-08-30 — recorded here because the next reader
# of this pair will ask the same question.
IDENTICAL_ACROSS: dict[tuple[str, str], tuple[str, ...]] = {
    ("detector", "_serialise"): ("gcp", "azure"),
    ("analyzer", "_serialise"): ("aws", "gcp", "azure"),
    ("analyzer", "_deserialise_detector"): ("gcp", "azure"),
    ("analyzer", "_parse_llm_response"): ("gcp", "azure"),
    ("analyzer", "_fallback_analysis"): ("gcp", "azure"),
    ("decision", "_serialise"): ("aws", "gcp", "azure"),
    ("decision", "_deserialise_analyzer"): ("gcp", "azure"),
}


def _normalised_functions(provider: str, module: str) -> dict[str, str]:
    path = ROOT / f"src/agents/operations/{provider}/{module}.py"
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines()
    out: dict[str, str] = {}
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out[node.name] = "\n".join(
                line.strip()
                for line in lines[node.lineno - 1 : node.end_lineno]
                if line.strip() and not line.strip().startswith("#")
            )
    return out


def test_the_table_is_not_empty():
    """Vacuity guard — an emptied table would satisfy every assertion below."""
    assert len(IDENTICAL_ACROSS) >= 7, (
        f"IDENTICAL_ACROSS holds {len(IDENTICAL_ACROSS)} entries; 7 were measured on "
        "2026-08-30. Removing one is allowed, but it is a decision — say why."
    )


@pytest.mark.parametrize(
    "module,function", sorted(IDENTICAL_ACROSS), ids=lambda v: v if isinstance(v, str) else str(v)
)
def test_the_shared_contract_has_not_drifted(module, function):
    providers = IDENTICAL_ACROSS[(module, function)]
    bodies = {}
    for provider in providers:
        found = _normalised_functions(provider, module)
        assert function in found, (
            f"{provider}/{module}.py no longer defines `{function}`, which this table "
            f"records as shared with {sorted(set(providers) - {provider})}. If it moved "
            "into a contract module, delete the row — that is the outcome this file wants."
        )
        bodies[provider] = found[function]

    distinct = {body: [p for p in providers if bodies[p] == body] for body in set(bodies.values())}
    assert len(distinct) == 1, {
        "function": f"{module}.{function}",
        "groups": {i: sorted(ps) for i, ps in enumerate(distinct.values())},
        "why": (
            "these were byte-identical on 2026-08-30, so this is a contract living in "
            "two files, not provider-specific code. A fix that reached only one copy is "
            "exactly how M18 found three defects duplicated and M23 found `Destroy` "
            "missing from AWS alone. Either apply it to both, or extract it and drop "
            "this row."
        ),
    }
