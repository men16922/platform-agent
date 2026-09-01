"""
The adapter base class must declare every method callers reach through it.

Found 2026-09-01, by mypy rather than by a test:

    src/agents/operations/aws/executor.py:348: error:
        "ExecutionAdapter" has no attribute "parameters_for_action"  [attr-defined]

All four execution adapters implemented `parameters_for_action`, and
`_build_action_params` called it **through the base-typed accessor**
`get_execution_adapter(provider)`. Nothing was broken at runtime. But the
declared contract said the method did not exist, and — measured — **no test
mentioned it at all** (`git grep parameters_for_action -- tests/` → 0).

⚠️ Why an undeclared method mattered more than usual here. The call site is:

    try:
        params = get_execution_adapter(provider).parameters_for_action(...)
        ...
    except Exception:
        pass
    # AWS alarm-dimension fallback

A fifth provider whose adapter satisfied `ExecutionAdapter` — which required only
`resolve_action` — would raise `AttributeError`, have it swallowed here, and be
handed **AWS's parameter shape** for its own incident. That is failing in the way
that does not error, which is what this repository keeps paying for (Risk 8:
*values는 에러가 아니라 안 읽히는 방식으로 실패한다*).

⚠️ **Not every such call belongs on the base.** `aws/detector.py` calls
`get_signal_adapter("aws").from_alarm_context(...)` — with a **string literal**.
Only AWS's signal adapter defines it, because only AWS receives CloudWatch alarms.
Declaring it on `SignalAdapter` would be a *false* claim about GCP, Azure and
on-prem, and this repo's standing criterion is that an orphaned declaration is not
automatically a defect — the test is *읽는 쪽의 provider 간 비대칭* (M19 ⓑ). A call
pinned to one provider by a literal has no asymmetry to be wrong about.

So the rule below is derived rather than listed: a method reached through a
**variable** provider must be on the base; a method reached through a **literal**
provider need not be, and this file says which is which by reading the AST rather
than by keeping a list someone must remember to update.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
OPERATIONS = ROOT / "src/agents/operations"
BASE = ROOT / "src/agents/adapters/base.py"

# accessor name -> the base class whose surface it promises
ACCESSORS = {
    "get_execution_adapter": "ExecutionAdapter",
    "get_signal_adapter": "SignalAdapter",
}

# Concrete implementations that must satisfy the execution contract. Named
# rather than discovered: a guard that asked "which classes subclass this?" would
# answer about whatever happens to be imported.
EXECUTION_ADAPTERS = {
    "aws": "src/agents/adapters/execution/aws.py",
    "gcp": "src/agents/adapters/execution/gcp.py",
    "azure": "src/agents/adapters/execution/azure.py",
    "onprem": "src/agents/adapters/execution/onprem.py",
}


def _declared_methods(path: pathlib.Path, class_name: str) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return {
                item.name
                for item in node.body
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                and not item.name.startswith("_")
            }
    raise AssertionError(f"{class_name} is no longer defined in {path.relative_to(ROOT)}")


def _calls_through_accessor() -> list[tuple[str, str, str, bool]]:
    """(file, base class, method, provider_is_literal) for every accessor call.

    Reads `get_x_adapter(...).method(...)` out of the AST rather than by regex:
    the thing that matters is whether the *argument* is a constant, and a regex
    cannot tell `get_signal_adapter("aws")` from `get_signal_adapter(provider)`
    without becoming a parser.
    """
    found: list[tuple[str, str, str, bool]] = []
    for path in sorted(OPERATIONS.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
                continue
            inner = node.func.value
            if not (isinstance(inner, ast.Call) and isinstance(inner.func, ast.Name)):
                continue
            if inner.func.id not in ACCESSORS:
                continue
            pinned = bool(inner.args) and isinstance(inner.args[0], ast.Constant)
            found.append(
                (path.relative_to(ROOT).as_posix(), ACCESSORS[inner.func.id],
                 node.func.attr, pinned)
            )
    return found


def test_the_sweep_finds_something():
    """Vacuity guard. An AST walk that silently matches nothing passes every
    assertion below — this repo has already shipped a sweep that counted the wrong
    thing and read as clean (M17's `post_webhook`)."""
    calls = _calls_through_accessor()
    assert len(calls) >= 2, (
        f"only {len(calls)} accessor call(s) found under {OPERATIONS.relative_to(ROOT)}. "
        "Either the operations layer stopped going through the adapter registry — "
        "which is the thing this file exists to watch — or the AST shape moved and "
        "this reader must move with it."
    )


def test_methods_reached_through_a_variable_provider_are_on_the_base():
    """The finding, generalised.

    A call whose provider is a variable can land on **any** implementation, so the
    base class is the only thing promising the method exists. When it did not,
    mypy said so and the tests did not.
    """
    undeclared: list[str] = []
    for file, base_class, method, pinned in _calls_through_accessor():
        if pinned:
            continue
        if method not in _declared_methods(BASE, base_class):
            undeclared.append(f"{file} calls {base_class}.{method}()")
    assert not undeclared, {
        "reached through a variable provider but not declared": sorted(undeclared),
        "why": (
            "the caller holds the base type, so the base is what promises the "
            "method. Declare it (with `raise NotImplementedError`) so a provider "
            "that omits it fails loudly — `aws/executor.py` swallows the "
            "AttributeError and falls through to AWS's parameter shape."
        ),
    }


def test_a_literal_provider_is_what_exempts_a_call():
    """The other half — otherwise the rule above is satisfied by declaring
    everything, including methods that only one provider can honestly offer.

    `get_signal_adapter("aws").from_alarm_context(...)` is the standing example:
    only AWS receives CloudWatch alarms, so putting `from_alarm_context` on
    `SignalAdapter` would claim something false about the other three. The literal
    is the exemption, and it is read from the source rather than trusted.
    """
    pinned = [c for c in _calls_through_accessor() if c[3]]
    assert pinned, (
        "no accessor call pins its provider with a literal any more. If the "
        "provider-specific entry points genuinely moved onto the base, that is a "
        "real change — delete this test and say so; do not let it pass by silence."
    )
    # The exemption must be carrying weight: at least one pinned call reaches a
    # method the base does **not** declare. If every pinned call's method were on
    # the base, the literal would be exempting nothing and the rule above could be
    # tightened to "all of them" — which is a decision, not a silent state.
    #
    # ⚠️ The first version of this test ended in `assert ... or True`, which is not
    # an assertion. It passed, it would have passed against anything, and it was
    # written by the same hand that had just spent the session finding rules that
    # could not fail. Hence this one names what it needs.
    exempted = [
        f"{file}: {base_class}.{method}()"
        for file, base_class, method, _ in pinned
        if method not in _declared_methods(BASE, base_class)
    ]
    assert exempted, {
        "pinned calls found": [f"{f}: {b}.{m}()" for f, b, m, _ in pinned],
        "why this fails": (
            "every provider-pinned call now reaches a method the base already "
            "declares, so the literal exempts nothing. Either tighten "
            "`test_methods_reached_through_a_variable_provider_are_on_the_base` to "
            "cover all calls, or delete this test — but do not leave an exemption "
            "that exempts nothing standing as if it were load-bearing."
        ),
    }


@pytest.mark.parametrize("provider", sorted(EXECUTION_ADAPTERS))
def test_every_execution_adapter_implements_the_whole_contract(provider):
    """Siblings, counted at the moment the contract is counted (Risk 12⑥).

    Declaring a method on the base makes a missing implementation raise
    `NotImplementedError` instead of `AttributeError` — which the same
    `except Exception: pass` swallows just as quietly. The declaration is only
    half; this is the half that says every provider actually answers.
    """
    required = _declared_methods(BASE, "ExecutionAdapter")
    path = ROOT / EXECUTION_ADAPTERS[provider]
    tree = ast.parse(path.read_text(encoding="utf-8"))
    implemented: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            implemented |= {
                item.name for item in node.body
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
    missing = sorted(required - implemented)
    assert not missing, {
        f"{provider} execution adapter is missing": missing,
        "required by": "src/agents/adapters/base.py::ExecutionAdapter",
        "why": (
            "the base's `raise NotImplementedError` is swallowed by "
            "`aws/executor.py`'s `except Exception: pass`, which then hands this "
            "provider AWS's alarm-dimension parameter shape. The failure would be "
            "silent and provider-specific — the hardest kind to see."
        ),
    }


def _accessor_calls_with_enclosing_params() -> list[tuple[str, str, str, list[str]]]:
    """(file, method, literal_provider, params of the enclosing function).

    Only pinned calls are returned — a variable provider is already covered by
    `test_methods_reached_through_a_variable_provider_are_on_the_base`.
    """
    found: list[tuple[str, str, str, list[str]]] = []
    for path in sorted(OPERATIONS.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            params = [a.arg for a in fn.args.args + fn.args.kwonlyargs]
            for node in ast.walk(fn):
                if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
                    continue
                inner = node.func.value
                if not (isinstance(inner, ast.Call) and isinstance(inner.func, ast.Name)):
                    continue
                if inner.func.id not in ACCESSORS or not inner.args:
                    continue
                arg = inner.args[0]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    found.append(
                        (path.relative_to(ROOT).as_posix(), node.func.attr, arg.value, params)
                    )
    return found


def test_a_function_given_a_provider_does_not_hardcode_one():
    """Closes the escape hatch the exemption above opens.

    ⚠️ This test exists because a mutation survived. Changing

        get_execution_adapter(provider).parameters_for_action(...)   # in a
                                                                    # function whose
                                                                    # parameter is
                                                                    # `provider`
    to

        get_execution_adapter("aws").parameters_for_action(...)

    satisfies every rule above — the call becomes "pinned", so the base need not
    declare the method — and **the whole suite stayed green** (2356 passed,
    measured 2026-09-01). That is a provider-generic remediation path quietly
    becoming AWS-only, which is the same shape as `Destroy` being absent from AWS
    alone (M23) and is the asymmetry this repo treats as the definition of a defect.

    The literal is a legitimate exemption only where there is no provider to
    respect. `aws/detector.py::_normalise_incident` takes an `alarm`, not a
    provider — it is AWS's entry point by construction. A function *handed* a
    provider and ignoring it is a different thing entirely.
    """
    offenders = [
        f"{file}: get_..._adapter({literal!r}).{method}() inside a function taking "
        f"`provider`"
        for file, method, literal, params in _accessor_calls_with_enclosing_params()
        if "provider" in params
    ]
    assert not offenders, {
        "hardcoded a provider it was given": sorted(offenders),
        "why": (
            "the function receives `provider` and then asks the registry for a "
            "different, fixed one. Every non-AWS incident would be remediated with "
            "AWS's adapter — silently, because `except Exception: pass` sits under "
            "this call. Pass the parameter through."
        ),
    }
