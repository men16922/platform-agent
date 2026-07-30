"""A deliberate exception is only as good as the consumer it cites.

Three times now this repo has found the same shape at three different levels:

  M13   a field is declared, written, and read by nobody
  D38   a mechanism is correct and no production code can reach it
  결정 2  a security exception is held open for a caller that does not exist

The third is the most expensive, because the exception was *load-bearing prose*.
`MUTATING_CLUSTER_TOOLS` refused writes without a scoped credential and let reads
through, on the stated grounds that "the verified anonymous kagent round trip goes
through them". It does not: that round trip is outbound, `k8s_get_resources` is
kagent's own tool, and nothing in `src/` even constructs an `MCPServer`. So an
unscoped read — reaching, via a free-form `resource`, whatever the ambient
credential can see — stayed open for years of commits because the sentence
explaining it was never checked against the code.

This file checks the sentences.

It is deliberately narrow. It does not try to validate every comment; it takes the
places where the codebase *names a consumer as the reason a boundary is not
enforced*, and asserts that consumer is constructed somewhere real. A carve-out
whose justification cannot be pointed at is a carve-out nobody can re-evaluate —
which is exactly how this one survived.

Not asserted: that a carve-out is wrong. Some are right. The claim is only that the
reason has to be checkable, because an unfalsifiable reason decays into a default.
"""

import ast
import pathlib
import re

REPO = pathlib.Path(__file__).resolve().parents[1]
SRC = REPO / "src"
SKIP_PARTS = {"cdk.out", "__pycache__", "node_modules", ".git"}


def _production_modules():
    for path in SRC.rglob("*.py"):
        if not SKIP_PARTS & set(path.parts):
            yield path


def _constructed_classes():
    """Every class instantiated anywhere in `src/`, by name.

    Name-based on purpose: this asks "does anything build one of these", which is a
    question about reachability, not about types. Import aliasing would defeat a
    stricter check and is not what goes wrong here — what goes wrong is that the
    call site simply is not there.
    """
    built = set()
    for path in _production_modules():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                fn = node.func
                name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
                # A class, by convention: CamelCase.
                if name and name[0].isupper():
                    built.add((path, name))
    return built


class TestTheGatewayCarveOutIsNoLongerJustifiedByAGhost:
    """The specific one this file was written for, pinned so it cannot come back."""

    GATEWAY = SRC / "agents" / "ai" / "gateway" / "mcp_server.py"

    def test_the_kagent_justification_is_gone(self):
        """The sentence was wrong. If it returns, so does the exception it licensed."""
        text = self.GATEWAY.read_text(encoding="utf-8")
        offenders = [
            line.strip()
            for line in text.splitlines()
            if re.search(r"kagent", line, re.I)
            and re.search(r"unscoped|reads stay|keeps working|round trip", line, re.I)
            and "does not" not in line.lower()
            and "not in that path" not in line.lower()
        ]
        assert not offenders, (
            "the gateway again cites the kagent round trip as the reason unscoped "
            f"reads are allowed. Checked 2026-07-31: that path is outbound and does "
            f"not go through this gateway. {offenders}"
        )

    def test_unscoped_reads_are_not_the_default(self):
        """Derived from behaviour, not from the comment above it."""
        from src.agents.ai.gateway.mcp_server import MCPServer

        result = MCPServer().call_tool("kubectl_get", {"resource": "secrets"})
        assert result.success is False, (
            "an unscoped read succeeded — `resource` is free-form, so this is not a "
            "narrow tool: it reaches whatever the ambient credential can, which was "
            "measured as cluster-admin"
        )

    def test_if_the_gateway_gains_a_production_constructor_it_is_scoped(self):
        """The trap this carve-out was waiting for.

        The reference work contemplates MCP-over-HTTP. On the day someone puts this
        gateway on a port, an unscoped read path stops being dormant and becomes an
        unauthenticated cluster read API. If a constructor appears, it must pass a
        scope — or this test says why that matters, at the moment it matters.
        """
        constructors = [
            (path, name) for path, name in _constructed_classes()
            if name == "MCPServer" and path != self.GATEWAY
        ]
        # `bridge.py` builds a default one as a library fallback; that is not a
        # server. Anything with a network entrypoint would also import FastAPI.
        serving = [
            path for path, _ in constructors
            if re.search(r"FastAPI|uvicorn|APIRouter", path.read_text(encoding="utf-8"))
        ]
        assert not serving, (
            f"{serving} serves the MCP gateway over the network. Unscoped reads are "
            "refused by default now, but confirm the request path supplies a scope "
            "rather than relying on the escape hatch — see 결정 2."
        )


class TestSecurityCommentsPointAtRealCode:
    """Generalised: a symbol named as the reason a boundary is relaxed must exist.

    Scanned only in `src/`, and only for the pattern that actually bit: a comment
    that justifies an exception by naming something, where the something is a symbol
    this codebase should be able to resolve.
    """

    #: Phrases that mark a comment as licensing an exception rather than describing one.
    LICENCE = re.compile(
        r"(stays? (available|ambient)|keeps? working|unchanged behaviour|"
        r"so the .* (round trip|path) )", re.I
    )

    def test_no_exception_is_licensed_by_an_unresolvable_backtick_symbol(self):
        """`some_function` cited as the reason a gate is open must be findable.

        A prose justification naming code that does not exist is unfalsifiable, and
        an unfalsifiable justification is how the gateway kept an ambient read path.
        """
        offenders = []
        for path in _production_modules():
            text = path.read_text(encoding="utf-8")
            for n, line in enumerate(text.splitlines(), 1):
                stripped = line.strip()
                if not (stripped.startswith("#") or stripped.startswith("*")):
                    continue
                if not self.LICENCE.search(stripped):
                    continue
                for symbol in re.findall(r"``([a-z_][a-z0-9_]{4,})``", stripped):
                    found = any(
                        re.search(rf"\b(def|class)\s+{re.escape(symbol)}\b", p.read_text(encoding="utf-8"))
                        for p in _production_modules()
                    )
                    if not found:
                        offenders.append(f"{path.relative_to(REPO)}:{n}: {symbol}")
        assert not offenders, (
            "these comments justify relaxing a boundary by naming code that does not "
            f"exist — the justification cannot be re-evaluated: {offenders}"
        )
