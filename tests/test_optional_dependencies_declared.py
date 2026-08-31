"""
Every optional import must be a declared dependency.

Why this file exists (2026-08-15). `pyproject.toml` already carries the lesson,
written for exactly one package:

    # Declared 2026-08-08, after the first CI run failed 17 tracing tests ...
    # The gate had been passing on an undeclared package that happened to be
    # installed locally.

The siblings were never counted. Sweeping every `try: import X / except
ImportError:` in `src/` found six more, and each one falls back to a *warning*
rather than an error — so an undeclared package does not fail the install, it
ships an agent that is quietly missing a limb:

    pip install .[gcp]     -> detector cannot read logs (google-cloud-logging)
                              or metrics (google-cloud-monitoring), and there is
                              no incident store (google-cloud-firestore)
    pip install .[azure]   -> no incident store (azure-cosmos), no log/metric
                              enrichment (azure-monitor-query), and **no LLM**
                              (openai — `AzureOpenAI` is the analyzer's model)
    make dev-up            -> nothing declared fastapi/uvicorn, so a fresh clone
                              cannot start the documented local stack

These guards are deliberately environment-independent: they compare the source
tree against `pyproject.toml`, not against what happens to be installed. That is
the whole failure mode — "it works here" is what hid it (Risk 12②).
"""

from __future__ import annotations

import ast
import pathlib
import re
import subprocess
import sys
import tomllib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]

# Import path -> the distribution that provides it. Hand-written on purpose: the
# installed-package view (`importlib.metadata.packages_distributions()`) answers
# "what is here", and "what is here" is precisely the question that misled us.
OPTIONAL_IMPORTS: dict[str, str] = {
    "azure.cosmos": "azure-cosmos",
    "azure.identity": "azure-identity",
    "azure.monitor.query": "azure-monitor-query",
    "fastapi": "fastapi",
    "fastapi.responses": "fastapi",
    "google.auth": "google-cloud-aiplatform",              # transitive: google-auth
    "google.auth.transport.requests": "google-cloud-aiplatform",
    "google.cloud": "google-cloud-firestore",              # firestore/logging/monitoring
    "google.oauth2": "google-cloud-aiplatform",
    "google.protobuf.timestamp_pb2": "google-cloud-monitoring",
    "openai": "openai",
    "vertexai": "google-cloud-aiplatform",
    "vertexai.generative_models": "google-cloud-aiplatform",
}


def _tracked_sources() -> list[pathlib.Path]:
    out = subprocess.run(
        ["git", "ls-files", "src/*.py", "src/**/*.py"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout.split()
    return [ROOT / rel for rel in out]


def _guarded_imports() -> dict[str, set[str]]:
    """Third-party modules imported inside a `try/except ImportError`."""
    found: dict[str, set[str]] = {}
    for path in _tracked_sources():
        source = path.read_text(encoding="utf-8")
        if "except ImportError" not in source:
            continue
        for node in ast.walk(ast.parse(source)):
            if not isinstance(node, ast.Try):
                continue
            if not any(
                isinstance(h.type, ast.Name) and h.type.id == "ImportError"
                for h in node.handlers
            ):
                continue
            for inner in ast.walk(node):
                module = None
                if isinstance(inner, ast.Import):
                    module = inner.names[0].name
                elif isinstance(inner, ast.ImportFrom) and inner.module:
                    module = inner.module
                if not module:
                    continue
                if module.split(".")[0] in sys.stdlib_module_names:
                    continue
                if module.startswith("src"):
                    continue
                found.setdefault(module, set()).add(
                    path.relative_to(ROOT).as_posix()
                )
    return found


def _declared_distributions() -> set[str]:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = data["project"]
    specs = list(project.get("dependencies", []))
    for extra in project.get("optional-dependencies", {}).values():
        specs.extend(extra)
    return {re.split(r"[<>=!~\[;]", s)[0].strip().lower() for s in specs}


class TestEveryOptionalImportIsDeclared:
    def test_the_sweep_finds_something(self):
        """A sweep that finds nothing would pass vacuously (Risk 12④ⓐ).

        ⚠️ Honest note: mutating **this assert** to `True` survives — nothing
        guards the guard. It is kept as documentation, not as the protection.
        The protection is `test_the_table_has_no_dead_entries` below: if the
        sweep ever returns nothing, every mapped import reads as stale and that
        test goes red. Verified by mutation (sweep -> `{}` : 2 failed;
        stdlib filter removed: 1 failed).
        """
        assert len(_guarded_imports()) >= 10

    @pytest.mark.parametrize("module", sorted(OPTIONAL_IMPORTS))
    def test_declared_in_pyproject(self, module):
        distribution = OPTIONAL_IMPORTS[module]
        assert distribution in _declared_distributions(), (
            f"{module} is imported behind `except ImportError` but "
            f"{distribution!r} is in no dependency list — the fallback is a "
            "warning, so this ships an agent missing that capability rather "
            "than failing the install"
        )

    def test_no_guarded_import_is_unmapped(self):
        """A new optional import must be declared, not silently added.

        This is the direction that actually holds the line: the table above can
        only stay honest if adding an import to `src/` without adding it here
        turns the gate red.
        """
        unmapped = sorted(set(_guarded_imports()) - set(OPTIONAL_IMPORTS))
        assert unmapped == [], (
            f"new optional imports {unmapped} — add each to OPTIONAL_IMPORTS "
            "and declare its distribution in pyproject.toml"
        )

    def test_the_table_has_no_dead_entries(self):
        """Reverse direction: an entry for an import nobody makes any more."""
        stale = sorted(set(OPTIONAL_IMPORTS) - set(_guarded_imports()))
        assert stale == [], f"OPTIONAL_IMPORTS lists imports no source makes: {stale}"


class TestTheServingStackIsInstallable:
    """`make dev-up` is documented in AGENT_BRIEF; nothing declared its server."""

    @pytest.mark.parametrize("distribution", ["fastapi", "uvicorn"])
    def test_declared(self, distribution):
        assert distribution in _declared_distributions()

    def test_makefile_still_uses_uvicorn(self):
        """Pins the premise — if dev-up stops using uvicorn, revisit the extra."""
        assert "uvicorn" in (ROOT / "Makefile").read_text(encoding="utf-8")


def _ci_install_line() -> str:
    workflow = (ROOT / ".github/workflows/gate.yml").read_text(encoding="utf-8")
    lines = [ln.strip() for ln in workflow.splitlines() if "pip install -e" in ln]
    assert len(lines) == 1, f"expected one editable install in gate.yml, found {len(lines)}"
    return lines[0]


class TestCIAsksForTheExtraInsteadOfWorkingAroundIt:
    """CI was carrying the undeclared ASGI stack so the gate would pass.

    `gate.yml` named `fastapi "uvicorn[standard]"` on the command line while no
    extra declared them — so the gate was green on packages that
    `pip install .` did not ship. That is the same failure the 2026-08-08
    opentelemetry note describes, one layer up: the workaround lived in CI, so
    nothing local could notice.
    """

    def test_ci_requests_the_serving_extra(self):
        assert "serving" in _ci_install_line(), (
            "gate.yml no longer installs the `serving` extra — if the ASGI stack "
            "moved, move the declaration too rather than naming packages inline"
        )

    @pytest.mark.parametrize("package", ["fastapi", "uvicorn", "pydantic-ai-slim"])
    def test_ci_does_not_inline_a_declared_package(self, package):
        line = _ci_install_line()
        # Strip the bracketed extras list so `.[...,serving]` is not a false hit.
        outside_extras = re.sub(r"\.\[[^\]]*\]", "", line)
        assert package not in outside_extras, (
            f"gate.yml names {package!r} on the command line, but it is declared in "
            "an extra — an inline install here means the gate can be green on "
            "something `pip install .` does not provide"
        )

    def test_ci_requests_the_onprem_extra(self):
        """The last inline package, removed 2026-09-01.

        `pydantic-ai-slim` was named on the command line because the `onprem`
        extra also pulled `mlx-lm`, which could not resolve on a linux runner.
        The fix was not to relax that — it was to measure the entry and find that
        **nothing consumed it**: `src/` never imports `mlx_lm`, and the machine's
        `.venv-mlx` had no `pydantic-ai-slim` in it, so it was never
        `pip install .[onprem]`. With `mlx-lm` out of the extra, CI can ask for
        the extra by name like every other one.
        """
        assert "onprem" in _ci_install_line(), (
            "gate.yml stopped installing the `onprem` extra. If `pydantic-ai-slim` "
            "moved, move the declaration with it — do not go back to naming it "
            "inline, which is what let the gate be green on something "
            "`pip install .` did not ship."
        )


class TestMlxIsNotAProjectDependency:
    """`mlx-lm` is installed by `make mlx-setup`, into a venv kept separate.

    ⚠️ This is not "it was unused, so we deleted it". Putting `mlx` into the
    project environment is contrary to a separation the Makefile maintains on
    purpose: an activated `.venv-mlx` **shadows pytest**, which is why the
    Makefile picks its interpreter by probing for one that can import it. So the
    declaration was not merely inert — it described the wrong mechanism.

    ⚠️ And it had gotten worse rather than stale. At the old floor the failure was
    loud: `mlx-lm==0.19.0` requires `mlx>=0.17.0` with **no platform marker**, so a
    linux resolve genuinely fails. Today's 0.31.3 requires `mlx>=0.31.2;
    platform_system == "Darwin"` and ships a `py3-none-any` wheel — it installs on
    linux and **the engine silently is not there** (re-measured 2026-09-01). A
    guard that only asked "does CI install it" would have been happy either way.
    """

    def test_no_extra_declares_mlx(self):
        declared = _declared_distributions()
        offenders = sorted(d for d in declared if d.startswith("mlx"))
        assert not offenders, (
            f"{offenders} is declared as a project dependency. The local stack runs "
            "MLX from its own venv (`make mlx-setup`) precisely so it does not land "
            "in the environment pytest runs from. If this is deliberate, say so in "
            "the Makefile's note above MLX_BIN and delete this test."
        )

    def test_the_source_tree_still_does_not_import_mlx(self):
        """The premise, asked of the code rather than assumed.

        The agent reaches MLX over an OpenAI-compatible HTTP endpoint, so the
        engine is a *process*, not an import. If that ever changes, `mlx-lm`
        becomes a real dependency and this whole class is wrong.
        """
        importers = [
            path.relative_to(ROOT).as_posix()
            for path in (ROOT / "src").rglob("*.py")
            if re.search(r"^\s*(import|from)\s+mlx", path.read_text(encoding="utf-8"), re.M)
        ]
        assert not importers, (
            f"{importers} import mlx directly. The separation this class pins "
            "assumes src/ only ever talks to the MLX server over HTTP."
        )

    # ⚠️ There is deliberately no test here that `make mlx-setup` still installs
    # mlx-lm, even though that is the premise making this removal safe.
    #
    # The first draft had one, and it asserted `"mlx-lm" in Makefile` — which the
    # *comments* above `MLX_BIN` satisfy on their own. Breaking the recipe
    # (`pip install "mlx-lm>=0.19"` → something else) left it green: a rule whose
    # subject is a comment is not a rule.
    #
    # ⚠️ Reading that as "nothing guards the recipe" was also wrong, and wrong in
    # the way this repo has already paid for (Risk 12⑦): the mutation was asked of
    # **this file only**. Against the whole suite it is red —
    # `test_local_stack_prerequisites.py::test_something_creates_the_venv_the_stack_runs_from`
    # asks the recipe itself, which is the right place and the right question.
    # Adding a second, weaker copy here would just be its shadow.
