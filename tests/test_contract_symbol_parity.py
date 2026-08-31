"""
Every shared symbol only some providers read must have a reason written down.

This is the sweep that found five defects on 2026-08-16, turned into a gate.

**The method.** Build the transitive import closure of each provider's
`operations/<provider>/` modules, then ask, for every public symbol defined
outside those folders, which providers reach it. A symbol reached by one or two
of the three is an asymmetry — and the repository's own criterion for a defect is
*읽는 쪽의 provider 간 비대칭*, not an orphaned declaration (M19 ⓑ).

What it surfaced, in order: `evaluate_condition` (runbook step conditions ignored
by GCP/Azure), `run_azure_action` (the Azure executor never calls its runner),
`guard_rollback`/`is_rollback` (following them found two AWS actions missing from
`ROLLBACK_ACTIONS` — and the test meant to catch that had left AWS out of its own
list of clouds), and `apply_gate`/`reconcile` (the reconciliation gate that
refuses to auto-execute an ungrounded analysis ran on AWS only).

⚠️ **The first version of this sweep counted direct imports and was wrong.**
`post_webhook` showed as AWS-only while all three reach it through
`_executor_common.post_incident_slack`. Counting only direct imports both invents
asymmetries and hides them — the eight `['aws', 'gcp']` rows below are invisible
to it. The closure is the instrument; the direct count was the shadow.

**Axes already swept, and what each returned (2026-08-16).** Recorded here so the
next session does not re-dig the same ground — a dry sweep is a measurement too
(M26). Finding more defects will take a *new* lens, not more of this one.

    계약 필드(dict 키)     M19~M26   결함 5 · M26에서 말랐다(ExecutorOutput)
    공용 심볼(이 파일)      M28~M32   결함 4 · 이제 게이트
    provider 액션 컬렉션    M31       결함 1 (ROLLBACK_ACTIONS) · 어댑터에서 유도하게 바꿈
    환경변수                —         **말랐다**. 비대칭은 전부 provider 고유 저장소·모델
                                    설정이고 `APPROVAL_DEFAULT_DECISION`은 AWS 전용
                                    approval bridge의 것(기본값 `reject`=fail-closed).
                                    `LOG_LOOKBACK_SEC`는 셋 다 읽는다.
    시간(Risk 12①)         —         **말랐다** → `test_no_expiring_fixtures.py`가 게이트로
                                    집행한다(절대시각 90건, 살아 있는 시계와 같은 함수에
                                    있는 것 0건).
    하중(Risk 12③)         —         **모듈 단위에선 말랐다**. 테스트가 전이적으로 안 싣는
                                    src 모듈은 0개다 — 처음 27개로 보였지만 전부 `__init__.py`
                                    연쇄를 모델링 못 한 계기의 산물이었다. ⚠️**분기 단위는 못
                                    쟀다**: 커버리지 도구가 없고, 도입은 레포 결정이다
                                    (gate.yml이 ruff에 대해 같은 이유로 경고한다 —
                                    *"a CI job is a bad place to introduce a standard
                                    nobody agreed to"*). 재려면 그 결정이 먼저다.
    테스트의 손-작성 목록    —         **말랐다**. "every/all"을 주장하며 provider를 일부만
                                    센 테스트는 둘뿐이고 **둘 다 정당**했다:
                                    `test_registry_resolves_all_providers`(온프렘엔 관리형
                                    호스팅이 없고 옆 테스트가 ValueError를 못 박는다) ·
                                    `test_every_provider_branch_is_covered_by_the_test_above`
                                    (seam 소스에서 유도 + 부분집합이 아니라 **등호** 비교).
                                    M31은 이 패턴이 흔해서가 아니라 심볼을 따라가다 나왔다.

**Why a table of reasons rather than "no asymmetry".** Most of these are correct:
DynamoDB pagination has no meaning for Firestore, and AWS is the multi-cloud
dispatcher so it legitimately reaches all three runners. Banning asymmetry would
be the unsatisfiable-rule mistake this repo already named (`test_iam_wildcard_
justified.py`). What must not happen is an asymmetry nobody looked at — so a new
one turns this red and has to be classified before the gate goes green.
"""

from __future__ import annotations

import ast
import collections
import pathlib
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROVIDERS = ("aws", "gcp", "azure")

_REPORTING = (
    "`reporting.py` exists only under `aws/` — GCP and Azure have no reporting "
    "module at all, so there is no reader to be asymmetric with (Risk 2: their "
    "incident stores are Phase 4)."
)
_DISPATCHER = (
    "AWS's executor is the multi-cloud dispatcher (`_run_external_action` fans out "
    "to every runner), so it reaches runners no other provider needs."
)

# symbol -> why only some providers read it. Measured 2026-08-16; each entry was
# opened and read, not assumed from its name.
JUSTIFIED: dict[str, str] = {
    # --- AWS-only, and correctly so -------------------------------------------
    "CircuitBreaker": "`adapters/aws_session.py` wraps STS calls in it; no other provider has STS.",
    "assume_role_arn_from_env": (
        "AWS STS role assumption. Each provider acquires credentials its own way — "
        "GCP through `get_gcp_access_token`, Azure through its ARM/Cosmos credential "
        "helpers — so there is no shared contract here for the others to ignore."
    ),
    "assume_role_session": (
        "Same as `assume_role_arn_from_env`: STS is the AWS half of a concern every "
        "provider solves in its own SDK, not a contract module two of them skipped."
    ),
    "paginated_scan": "DynamoDB pagination. GCP/Azure read a single document by id, so there is nothing to paginate.",
    "normalise_runbook": (
        "`Decimal` is a boto3 deserialisation artefact; Firestore and Cosmos return "
        "native ints, so there is no storage type to coerce. Verified before "
        "concluding — this is the odd one out whose *justified* asymmetry led to "
        "the tier-1 validation gap next to it (M28)."
    ),
    "builtin_runbook_items": (
        "`aws/runbook_seed.py` seeds DynamoDB from a CDK custom resource. Nothing "
        "seeds Firestore or Cosmos — the runbook store is Phase 4 for them."
    ),
    "VerificationResult": (
        "The verify path exists only on AWS; the GCP and Azure executors say so at "
        "their resolution verdict (\"GCP/Azure have no verify path yet\")."
    ),
    "record_agent_activity": (
        "The dashboard is documented as hybrid **AWS + On-Prem** (AGENT_BRIEF "
        "Snapshot). GCP/Azure are outside the activity feed by scope, not by omission."
    ),
    "analyze_service_capacity": _REPORTING,
    "build_monthly_capacity_report": _REPORTING,
    "build_daily_slo_report": _REPORTING,
    "calculate_service_slo": _REPORTING,
    "build_weekly_oncall_report": _REPORTING,
    "run_onprem_action": _DISPATCHER,
    "verify_onprem_action": _DISPATCHER,
    "is_rollback": (
        "Reached through `onprem_runner`, which imports the pair; AWS reaches it "
        "as the dispatcher. ⚠️ Following it is what surfaced the real defect next "
        "door — two AWS actions missing from `ROLLBACK_ACTIONS` (test_reconciler_"
        "conflict). `guard_rollback` used to sit beside this entry and no longer "
        "does: as of 2026-08-30 `azure_runner` calls it directly, so all three "
        "providers reach it and it is not an asymmetry any more."
    ),
    # --- Each is its own provider's runner; AWS reaches all of them as dispatcher.
    "run_azure_action": (
        "The Azure runner, and symmetric with `run_gcp_action` since 2026-08-30. "
        "It was the one entry in this table marked NOT justified — Azure's executor "
        "did not call it, so Azure reported actions as executed and incidents as "
        "resolved without performing them. Wired under approval that day, which "
        "also closed the six symptoms downstream of it (`IncidentScope`, "
        "`resolve_incident_scope`, `guard_scoped_action`, `IsolationTier`, "
        "`Registry`, `load_registry`) — one cause, seven rows. "
        "docs/evidence/azure-executor-reports-resolved-without-executing.log"
    ),
    "run_gcp_action": "The GCP runner. AWS reaches it as dispatcher; Azure has its own.",
    "get_gcp_access_token": "GCP runner internals, reached the same way as `run_gcp_action`.",
}


def _module_map() -> dict[str, str]:
    files = subprocess.run(
        ["git", "ls-files", "src/*.py", "src/**/*.py"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout.split()
    # `git ls-files` rather than a filesystem walk: `src/stacks/cdk.out/` is an
    # untracked build artefact holding copies of this tree, and counting it has
    # already produced a wrong measurement in this repo more than once.
    return {f[:-3].replace("/", "."): f for f in files if f.endswith(".py")}


def _asymmetries() -> list[tuple[tuple[str, ...], str, str]]:
    mods = _module_map()
    imports_mod: dict[str, set[str]] = collections.defaultdict(set)
    imports_name: dict[str, set[str]] = collections.defaultdict(set)

    for module, rel in mods.items():
        try:
            tree = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("src.agents"):
                imports_mod[module].add(node.module)
                for alias in node.names:
                    imports_name[module].add(alias.name)
                    # `from pkg import submodule` — the name is a module, not a symbol.
                    if f"{node.module}.{alias.name}" in mods:
                        imports_mod[module].add(f"{node.module}.{alias.name}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("src.agents"):
                        imports_mod[module].add(alias.name)

    def closure(seed: list[str]) -> set[str]:
        seen, stack = set(seed), list(seed)
        while stack:
            for nxt in imports_mod.get(stack.pop(), ()):
                if nxt in mods and nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        return seen

    reach_of = {
        p: closure([m for m in mods if f".operations.{p}." in m]) for p in PROVIDERS
    }

    owner: dict[str, str] = {}
    for module, rel in mods.items():
        if any(f".operations.{p}." in module for p in PROVIDERS):
            continue
        try:
            body = ast.parse((ROOT / rel).read_text(encoding="utf-8")).body
        except SyntaxError:
            continue
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if not node.name.startswith("_"):
                    owner.setdefault(node.name, module)

    found = []
    for symbol, module in owner.items():
        readers = tuple(
            p for p in PROVIDERS if any(symbol in imports_name.get(m, ()) for m in reach_of[p])
        )
        if 0 < len(readers) < len(PROVIDERS):
            found.append((readers, symbol, module))
    return sorted(found, key=lambda r: r[1])


ASYMMETRIES = _asymmetries()


def test_the_sweep_still_finds_asymmetries():
    """Vacuity check — a broken closure walk reports perfect symmetry, and every
    assertion below would then pass by finding nothing.

    This was a floor on the count (``>= 20``, from 26 measured on 2026-08-16).
    On 2026-08-30 wiring the Azure executor closed seven rows at once and the
    count fell to 19, so the floor failed and the only way to green was to edit
    the number down. **A number that gets lowered whenever it fails is not a
    check** — it is the allowlist-nobody-prunes shape this file names elsewhere,
    and it cannot tell a real fix from a broken instrument.

    So the control is structural instead: two symbols whose reader sets are fixed
    by architecture rather than by any open finding. A walk that breaks reports
    them as absent; a walk that computes reader sets wrongly reports them with
    the wrong set. Both are caught, and neither goes stale when a defect closes.
    """
    by_symbol = {symbol: set(readers) for readers, symbol, _ in ASYMMETRIES}

    assert by_symbol.get("paginated_scan") == {"aws"}, (
        "`paginated_scan` is DynamoDB pagination — AWS-only by construction, and "
        f"the sweep reports {by_symbol.get('paginated_scan')}. The instrument is "
        "broken, not the code."
    )
    assert by_symbol.get("run_gcp_action") == {"aws", "gcp"}, (
        "`run_gcp_action` is GCP's own runner, reached by GCP and by AWS as the "
        f"multi-cloud dispatcher; the sweep reports {by_symbol.get('run_gcp_action')}. "
        "A closure walk that cannot see this pair cannot see any of the rest."
    )


@pytest.mark.parametrize(
    "readers,symbol,module",
    ASYMMETRIES,
    ids=[f"{s}:{'+'.join(r)}" for r, s, _ in ASYMMETRIES],
)
def test_each_asymmetry_is_accounted_for(readers, symbol, module):
    assert symbol in JUSTIFIED, (
        f"`{symbol}` ({module}) is read by {list(readers)} and not by the rest, and "
        "nothing says why. Open it and decide: either the other providers should "
        "read it — five defects on 2026-08-16 were exactly this — or the asymmetry "
        "is correct and belongs in JUSTIFIED with the reason."
    )


def test_no_stale_justification():
    """Reverse direction: an entry for a symbol that is now symmetric.

    `apply_gate`, `reconcile` and `evaluate_condition` all left this table the
    moment their providers were wired. A reason that outlives its asymmetry is a
    claim nothing checks.
    """
    live = {symbol for _, symbol, _ in ASYMMETRIES}
    stale = sorted(set(JUSTIFIED) - live)
    assert not stale, (
        f"JUSTIFIED explains {stale}, which are no longer asymmetric — remove them."
    )


@pytest.mark.parametrize("symbol", sorted(JUSTIFIED))
def test_the_reason_says_something(symbol):
    """`test_iam_wildcard_justified`'s rule: mechanical checks cannot judge whether
    a reason is true, only that someone had to write one."""
    assert len(JUSTIFIED[symbol]) > 60, symbol
