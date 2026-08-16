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

    @pytest.mark.parametrize("package", ["fastapi", "uvicorn"])
    def test_ci_does_not_inline_a_declared_package(self, package):
        line = _ci_install_line()
        # Strip the bracketed extras list so `.[...,serving]` is not a false hit.
        outside_extras = re.sub(r"\.\[[^\]]*\]", "", line)
        assert package not in outside_extras, (
            f"gate.yml names {package!r} on the command line, but it is declared in "
            "an extra — an inline install here means the gate can be green on "
            "something `pip install .` does not provide"
        )

    def test_the_documented_exception_is_still_documented(self):
        """`pydantic-ai-slim` IS inlined, on purpose: `onprem` also pulls
        Apple-only mlx-lm. Pin that the reason stays written next to it."""
        workflow = (ROOT / ".github/workflows/gate.yml").read_text(encoding="utf-8")
        assert "pydantic-ai-slim" in _ci_install_line()
        assert "mlx-lm" in workflow, "the reason for bypassing the onprem extra is gone"
