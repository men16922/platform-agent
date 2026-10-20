from types import SimpleNamespace

from src.agents.ai import ops_tools


def _fake_run(stdout="", stderr="", returncode=0):
    def run(cmd, capture_output=True, text=True, timeout=None):
        run.cmd = cmd
        return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)

    return run


def test_list_pods_reads_namespace(monkeypatch):
    fake = _fake_run(stdout="NAME   READY\npod-1  1/1")
    monkeypatch.setattr(ops_tools.subprocess, "run", fake)
    out = ops_tools.list_pods("obs-demo")
    assert out["ok"] is True
    assert "pod-1" in out["output"]
    assert fake.cmd == ["kubectl", "get", "pods", "-n", "obs-demo", "-o", "wide"]


def test_kubectl_nonzero_is_error(monkeypatch):
    monkeypatch.setattr(ops_tools.subprocess, "run", _fake_run(stderr="not found", returncode=1))
    out = ops_tools.describe_deployment("missing")
    assert out["ok"] is False
    assert "not found" in out["error"]


def test_all_ops_tools_use_readonly_verbs(monkeypatch):
    commands = []

    def run(cmd, **kwargs):
        commands.append(cmd[1:])
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(ops_tools.subprocess, "run", run)
    ops_tools.list_pods()
    ops_tools.get_logs("d")
    ops_tools.describe_deployment("d")
    ops_tools.rollout_status("d")
    ops_tools.list_namespaces()
    # Only read verbs — no apply/delete/create/scale/patch.
    for command in commands:
        while command[0] in {"--context", "--kubeconfig"}:
            command = command[2:]
        if command[0] == "config":
            assert command == ["config", "current-context"]
        elif command[0] == "rollout":
            assert command[1] == "status"
        else:
            assert command[0] in {"get", "logs", "describe"}


def test_ops_tools_exported():
    names = {t.__name__ for t in ops_tools.OPS_TOOLS}
    assert names == {"list_pods", "get_logs", "describe_deployment", "rollout_status", "list_namespaces"}
