"""A deploy ran as cluster-admin, and nothing said so.

Measured 2026-07-30 on the live kind cluster: every deployment adapter shelled out
to a bare `kubectl`, so a deploy ran as the ambient context — `kubernetes-admin` in
`kubeadm:cluster-admins`. `can-i get secrets -A` was yes. `can-i delete namespaces
-A` was yes. To roll out one service.

That is the same ambient execution Phase 1a removed from the incident runner. It
survived on the deploy path because the guard was written for incidents and nobody
asked what the *other* path ran as — which is the shape of this whole milestone: the
question that is never asked stays green forever.

Two things are asserted here, and the second is the one that lasts:

  1. **Every kubectl the deploy path builds goes through the seam.** Derived by
     reading the adapters, so a fifth provider — or a new command on an existing one
     — fails here instead of quietly reintroducing ambient execution. The repo has
     already paid for the enumerated version of this: when a capability was rendered
     per-runner, the third runner simply did not have it.

  2. **The rendered identity cannot do the things the ambient one could.** Derived
     from the rendered manifest rather than from a list of rule names, and stated as
     a prohibition (`secrets`, `namespaces` writes, RBAC, `delete`, `*`) rather than
     an allowance, because an allowance list passes while silently growing.

**What this does NOT claim.** One identity for every deploy. It bounds *what* a
deploy can do, not *whose* namespace it touches — per-tenant deploy credentials
need the request to name a tenant, and it does not (결정 5 C/D,
`docs/plans/2026-07-30-deploy-request-tenant-scoping.md`). Do not let a card, a
schema or a dashboard call this tenant isolation.
"""

import ast
import pathlib
import re

REPO = pathlib.Path(__file__).resolve().parents[1]
DEPLOY_ADAPTERS = sorted((REPO / "src" / "agents" / "adapters" / "deployment").glob("*.py"))
OPS_TOOLS = REPO / "src" / "agents" / "ai" / "ops_tools.py"

#: Modules that legitimately build a bare `kubectl` argv. `base.py` declares the
#: interfaces and runs nothing; the gateway and the incident runner pin to their own
#: (per-incident) credential, which is a *narrower* boundary, not this one.
NOT_DEPLOY_PATH = {"base.py", "__init__.py"}


#: Callables that actually execute a command, for the shell-string form below.
_EXECUTORS = {"run", "Popen", "call", "check_call", "check_output", "system"}


def _kubectl_literals(path):
    """Every `kubectl` argv this module *builds*, with its line number.

    AST rather than grep, and narrower than "the word appears": a list literal whose
    first element is ``"kubectl"`` is a command; a shell string is a command only
    when it is handed to something that runs it.

    That last clause is not hypothetical caution. The first version of this matched
    any string starting with ``kubectl``, and immediately flagged
    ``"kubectl not found on PATH"`` and ``"kubectl timed out after 30s"`` — two error
    messages — as ambient execution. A guard that cannot tell a command from prose
    about a command reports work that does not exist, which is the same failure as
    missing work that does.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.List, ast.Tuple)) and node.elts:
            first = node.elts[0]
            if isinstance(first, ast.Constant) and first.value == "kubectl":
                hits.append(node.lineno)
        # `subprocess.run("kubectl get pods", shell=True)` — only when it is the
        # argument of a call that executes.
        if isinstance(node, ast.Call) and node.args:
            fn = node.func
            name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
            if name in _EXECUTORS:
                first = node.args[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    if re.match(r"^kubectl(\s|$)", first.value):
                        hits.append(node.lineno)
    return hits


class TestEveryDeployCommandGoesThroughTheSeam:
    def test_no_deployment_adapter_builds_a_bare_kubectl(self):
        offenders = []
        for path in DEPLOY_ADAPTERS:
            if path.name in NOT_DEPLOY_PATH:
                continue
            for lineno in _kubectl_literals(path):
                offenders.append(f"{path.relative_to(REPO)}:{lineno}")
        assert not offenders, (
            "these build kubectl argv directly instead of through `deploy_kubectl`, so "
            "they run as the ambient context — measured on kind, that is cluster-admin "
            f"with `get secrets -A`: {offenders}"
        )

    def test_the_read_only_tools_share_the_same_credential(self):
        """They share a process with the deploy tools, so they share an identity.

        Pinning the mutating half while `get_logs` still reads through the ambient
        context is a boundary that is closed only on the side you tested.
        """
        assert not _kubectl_literals(OPS_TOOLS), (
            "ops_tools builds a bare kubectl — read-only is not harmless, and someone "
            "else's pod logs are still someone else's data"
        )

    def test_every_adapter_that_deploys_warns_when_unpinned(self):
        """Derived over the adapters: absence must be loud at the point of use.

        The default stays ambient on purpose — a fail-closed default would break the
        two-line demo, and a boundary nobody can run is exactly what this
        investigation found. So the compensating control is that it says so.
        """
        missing = []
        for path in DEPLOY_ADAPTERS:
            if path.name in NOT_DEPLOY_PATH:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.FunctionDef) or node.name != "deploy":
                    continue
                calls = {
                    n.func.id for n in ast.walk(node)
                    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                }
                if "warn_if_ambient" not in calls:
                    missing.append(f"{path.relative_to(REPO)}:{node.lineno}")
        assert not missing, (
            f"{missing} deploy without saying they may be running unpinned — silence "
            "is how the ambient path survived Phase 1a in the first place"
        )

    def test_the_names_the_adapters_call_actually_resolve(self):
        """A call site is not proof the name exists.

        This is not a hypothetical either: the check above passed on all four
        adapters while three of them could not import `warn_if_ambient` at all — a
        linter had stripped it as unused in the window between adding the import and
        adding the call. Reading the AST tells you what a module *says*; only
        importing it tells you what it *has*. The tests that caught it were the ones
        that ran the code.
        """
        import importlib

        broken = []
        for path in DEPLOY_ADAPTERS:
            if path.name in NOT_DEPLOY_PATH:
                continue
            module = importlib.import_module(
                f"src.agents.adapters.deployment.{path.stem}"
            )
            tree = ast.parse(path.read_text(encoding="utf-8"))
            called = {
                n.func.id for n in ast.walk(tree)
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
            }
            for name in called & {"deploy_kubectl", "warn_if_ambient"}:
                if not hasattr(module, name):
                    broken.append(f"{path.relative_to(REPO)}: calls {name}, cannot resolve it")
        assert not broken, broken

    def test_the_seam_pins_only_when_configured(self):
        from src.agents.platform import deploy_identity

        original = deploy_identity.os.environ.get(deploy_identity.DEPLOY_KUBECONFIG_ENV)
        try:
            deploy_identity.os.environ.pop(deploy_identity.DEPLOY_KUBECONFIG_ENV, None)
            assert deploy_identity.deploy_kubectl("get", "pods") == ["kubectl", "get", "pods"]

            # An exported-but-empty variable has not configured anything; pinning to
            # "" would fail in a way that reads like a broken cluster. Asserted on
            # `deploy_kubeconfig` too, not just the argv: the argv happens to be
            # right either way because `if kubeconfig:` is falsy on "", so testing
            # only the argv left the normalisation unguarded — a reversion of it
            # passed. The contract worth holding is "None means ambient", because
            # that is what a caller writing `is None` will rely on.
            deploy_identity.os.environ[deploy_identity.DEPLOY_KUBECONFIG_ENV] = ""
            assert deploy_identity.deploy_kubeconfig() is None
            assert deploy_identity.deploy_kubectl("get", "pods") == ["kubectl", "get", "pods"]

            deploy_identity.os.environ[deploy_identity.DEPLOY_KUBECONFIG_ENV] = "/tmp/d.kubeconfig"
            assert deploy_identity.deploy_kubectl("get", "pods") == [
                "kubectl", "--kubeconfig", "/tmp/d.kubeconfig", "get", "pods",
            ]
        finally:
            if original is None:
                deploy_identity.os.environ.pop(deploy_identity.DEPLOY_KUBECONFIG_ENV, None)
            else:
                deploy_identity.os.environ[deploy_identity.DEPLOY_KUBECONFIG_ENV] = original


class TestTheIdentityCannotDoWhatAmbientCould:
    """Stated as prohibitions, from the rendered manifest.

    An allowance list ("it should have deployments and services") keeps passing while
    something quietly adds secrets next to them. The interesting assertion is the one
    that fails when the grant *grows*.
    """

    def _cluster_role(self):
        import sys

        sys.path.insert(0, str(REPO / "scripts"))
        from render_deploy_identity import manifests

        docs = manifests("platform-agent-deployer", "platform-agent-system")
        return next(d for d in docs if d["kind"] == "ClusterRole")

    def test_it_cannot_read_secrets(self):
        """The single most consequential thing ambient could do. `get secrets -A`
        was yes on the live cluster."""
        for rule in self._cluster_role()["rules"]:
            assert "secrets" not in rule["resources"], rule

    def test_it_cannot_touch_any_of_the_forbidden_resources(self):
        from render_deploy_identity import FORBIDDEN_RESOURCES

        granted = {r for rule in self._cluster_role()["rules"] for r in rule["resources"]}
        overlap = granted & FORBIDDEN_RESOURCES
        assert not overlap, (
            f"the deploy identity grants {overlap} — every one of these is a step back "
            "toward the ambient credential this replaced"
        )

    def test_it_holds_no_wildcard_or_destructive_verb(self):
        from render_deploy_identity import FORBIDDEN_VERBS

        for rule in self._cluster_role()["rules"]:
            bad = set(rule["verbs"]) & FORBIDDEN_VERBS
            assert not bad, (
                f"{rule['resources']} grants {bad}. `*` silently re-grants everything; "
                "the deploy path deletes no Kubernetes object (teardown is "
                "provision_tools, and rollback is a patch)"
            )

    def test_it_can_only_read_namespaces_never_create_them(self):
        """Creating tenant boundaries is `setup_tenancy`'s job, and D30 keeps the
        agent's mutating range inside a tenant. A deployer that can make namespaces
        can make itself somewhere new to deploy."""
        for rule in self._cluster_role()["rules"]:
            if "namespaces" in rule["resources"]:
                assert set(rule["verbs"]) <= {"get", "list", "watch"}, rule

    def test_the_serviceaccount_is_not_in_a_tenant_namespace(self):
        """Its own namespace, so a tenant with edit rights in theirs cannot mint a
        token for the deployer."""
        import sys

        sys.path.insert(0, str(REPO / "scripts"))
        from render_deploy_identity import DEFAULT_NAMESPACE, manifests

        sa = next(d for d in manifests("platform-agent-deployer", DEFAULT_NAMESPACE)
                  if d["kind"] == "ServiceAccount")
        assert sa["metadata"]["namespace"] == DEFAULT_NAMESPACE
        assert DEFAULT_NAMESPACE.startswith("platform-agent"), DEFAULT_NAMESPACE


class TestTheGrantCoversWhatTheAdaptersActuallyRun:
    """The other direction — derived, so a new adapter command that needs a verb
    nobody granted fails here rather than at 2am against a real cluster.

    Not exhaustive RBAC simulation: it maps the kubectl verbs the adapters use onto
    the resources they name, which is the drift that actually happens.
    """

    #: kubectl subcommand -> the RBAC verbs the API server requires for it.
    VERBS_FOR = {
        "apply": {"get", "patch", "create"},
        "get": {"get"},
        "logs": {"get"},
        "describe": {"get", "list"},
        "rollout": {"get", "list", "patch"},
    }

    def _subcommands(self):
        found = set()
        for path in [*DEPLOY_ADAPTERS, OPS_TOOLS]:
            if path.name in NOT_DEPLOY_PATH:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
                    continue
                if node.func.id != "deploy_kubectl" or not node.args:
                    continue
                first = node.args[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    found.add(first.value)
        return found

    def test_every_subcommand_the_adapters_use_is_understood(self):
        """If a new kubectl verb shows up, this file must decide what it needs —
        rather than the grant silently not covering it."""
        unknown = self._subcommands() - set(self.VERBS_FOR)
        assert not unknown, (
            f"the adapters run `kubectl {unknown}` and this guard has no verb mapping "
            "for it, so nothing checked whether the deploy identity may do it"
        )

    def test_the_deployments_rule_covers_apply_and_rollout(self):
        import sys

        sys.path.insert(0, str(REPO / "scripts"))
        from render_deploy_identity import manifests

        role = next(d for d in manifests("x", "y") if d["kind"] == "ClusterRole")
        deployments = next(r for r in role["rules"] if "deployments" in r["resources"])
        needed = self.VERBS_FOR["apply"] | self.VERBS_FOR["rollout"]
        missing = needed - set(deployments["verbs"])
        assert not missing, (
            f"deploy/rollback would be Forbidden: deployments rule is missing {missing}"
        )
