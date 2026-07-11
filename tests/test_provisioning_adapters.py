from src.agents.adapters.provisioning import (
    ProvisionSpec,
    get_provisioning_adapter,
    supported_provisioning_providers,
)
from src.agents.adapters.provisioning import onprem as onprem_mod
from src.agents.ai import provision_tools


def test_registry_resolves_onprem():
    assert supported_provisioning_providers() == ["onprem"]
    adapter = get_provisioning_adapter("onprem")
    assert isinstance(adapter, onprem_mod.OnPremProvisionAdapter)


def test_unknown_provider_raises():
    import pytest

    with pytest.raises(ValueError):
        get_provisioning_adapter("aws")


def test_provision_kind_runs_terraform(monkeypatch):
    calls = []

    def fake_run(cmd, cwd=None, timeout=900):
        calls.append(cmd)
        return 0, "Apply complete!"

    monkeypatch.setattr(onprem_mod, "_run", fake_run)
    r = get_provisioning_adapter("onprem").provision_cluster(ProvisionSpec(cluster_name="demo", mode="kind"))
    assert r.success is True
    assert r.context == "kind-demo"
    verbs = [c[1] for c in calls if c[0] == "terraform"]
    assert verbs == ["init", "apply"]
    assert any("cluster_name=demo" in part for c in calls for part in c)


def test_teardown_kind_runs_terraform_destroy(monkeypatch):
    calls = []

    def fake_run(cmd, cwd=None, timeout=900):
        calls.append(cmd)
        return 0, "Destroy complete!"

    monkeypatch.setattr(onprem_mod, "_run", fake_run)
    r = get_provisioning_adapter("onprem").teardown_cluster(ProvisionSpec(cluster_name="demo", mode="kind"))
    assert r.success is True
    assert any(c[0] == "terraform" and c[1] == "destroy" for c in calls)


def test_terraform_init_failure_reported(monkeypatch):
    monkeypatch.setattr(onprem_mod, "_run", lambda cmd, cwd=None, timeout=900: (1, "boom"))
    r = get_provisioning_adapter("onprem").provision_cluster(ProvisionSpec(mode="kind"))
    assert r.success is False
    assert "init failed" in (r.error or "")


def test_unknown_mode_is_error():
    r = get_provisioning_adapter("onprem").provision_cluster(ProvisionSpec(mode="nonsense"))
    assert r.success is False
    assert "unknown provisioning mode" in (r.error or "")


def test_provision_tool_wraps_adapter(monkeypatch):
    monkeypatch.setattr(onprem_mod, "_run", lambda cmd, cwd=None, timeout=900: (0, "ok"))
    out = provision_tools.provision_cluster(cluster_name="demo", mode="kind")
    assert out["success"] is True
    assert out["cluster"] == "demo"
    assert out["context"] == "kind-demo"
