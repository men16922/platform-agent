from src.agents.adapters.provisioning import (
    ProvisionSpec,
    get_provisioning_adapter,
    supported_provisioning_providers,
)
from src.agents.adapters.provisioning import onprem as onprem_mod
from src.agents.adapters.provisioning import aws as aws_mod
from src.agents.adapters.provisioning import gcp as gcp_mod
from src.agents.adapters.provisioning import azure as azure_mod
from src.agents.ai import provision_tools


def test_registry_resolves_onprem():
    assert supported_provisioning_providers() == ["onprem", "aws", "gcp", "azure"]
    adapter = get_provisioning_adapter("onprem")
    assert isinstance(adapter, onprem_mod.OnPremProvisionAdapter)


def test_registry_resolves_aws():
    assert isinstance(get_provisioning_adapter("aws"), aws_mod.AwsProvisionAdapter)


def test_registry_resolves_gcp_and_azure():
    assert isinstance(get_provisioning_adapter("gcp"), gcp_mod.GcpProvisionAdapter)
    assert isinstance(get_provisioning_adapter("azure"), azure_mod.AzureProvisionAdapter)


def test_aws_provision_is_plan_only_without_approval(monkeypatch):
    calls = []
    monkeypatch.setattr(aws_mod, "_run", lambda cmd, cwd, timeout=1800: (calls.append(cmd) or (0, "No changes")))
    result = get_provisioning_adapter("aws").provision_cluster(ProvisionSpec(provider="aws"))
    assert result.success is True
    assert calls == [["npx", "cdk", "diff", "IncidentAgentStack"]]


def test_aws_provision_deploys_only_when_approved(monkeypatch):
    calls = []
    monkeypatch.setattr(aws_mod, "_run", lambda cmd, cwd, timeout=1800: (calls.append(cmd) or (0, "deployed")))
    result = get_provisioning_adapter("aws").provision_cluster(ProvisionSpec(provider="aws", approved=True))
    assert result.success is True
    assert calls == [["npx", "cdk", "deploy", "IncidentAgentStack", "--require-approval", "never"]]


def test_unknown_provider_raises():
    import pytest

    with pytest.raises(ValueError):
        get_provisioning_adapter("linode")


# --- GCP (GKE via gcloud) ---


def test_gcp_provision_is_preflight_only_without_approval(monkeypatch):
    calls = []
    monkeypatch.setenv("GCP_PROJECT", "proj-1")
    monkeypatch.setenv("GCP_REGION", "asia-northeast3")
    monkeypatch.setattr(gcp_mod, "_run", lambda cmd, timeout=1800: (calls.append(cmd) or (0, "")))
    result = get_provisioning_adapter("gcp").provision_cluster(ProvisionSpec(provider="gcp", cluster_name="demo"))
    assert result.success is True
    # read-only list, NOT create
    assert calls == [["gcloud", "container", "clusters", "list", "--project", "proj-1", "--region", "asia-northeast3"]]
    assert result.context == "asia-northeast3"


def test_gcp_provision_creates_only_when_approved(monkeypatch):
    calls = []
    monkeypatch.setenv("GCP_PROJECT", "proj-1")
    monkeypatch.setenv("GCP_REGION", "asia-northeast3")
    monkeypatch.setattr(gcp_mod, "_run", lambda cmd, timeout=1800: (calls.append(cmd) or (0, "Created")))
    result = get_provisioning_adapter("gcp").provision_cluster(
        ProvisionSpec(provider="gcp", cluster_name="demo", approved=True, node_count=3)
    )
    assert result.success is True
    assert calls == [[
        "gcloud", "container", "clusters", "create", "demo",
        "--project", "proj-1", "--region", "asia-northeast3", "--num-nodes", "3", "--quiet",
    ]]
    assert result.context == "gke_proj-1_asia-northeast3_demo"


def test_gcp_requires_project(monkeypatch):
    monkeypatch.delenv("GCP_PROJECT", raising=False)
    result = get_provisioning_adapter("gcp").provision_cluster(ProvisionSpec(provider="gcp"))
    assert result.success is False
    assert "GCP_PROJECT" in (result.error or "")


def test_gcp_teardown_requires_approval(monkeypatch):
    monkeypatch.setenv("GCP_PROJECT", "proj-1")
    result = get_provisioning_adapter("gcp").teardown_cluster(ProvisionSpec(provider="gcp", cluster_name="demo"))
    assert result.success is False
    assert "approved=True" in (result.error or "")


def test_gcp_teardown_deletes_when_approved(monkeypatch):
    calls = []
    monkeypatch.setenv("GCP_PROJECT", "proj-1")
    monkeypatch.setenv("GCP_REGION", "asia-northeast3")
    monkeypatch.setattr(gcp_mod, "_run", lambda cmd, timeout=1800: (calls.append(cmd) or (0, "Deleted")))
    result = get_provisioning_adapter("gcp").teardown_cluster(
        ProvisionSpec(provider="gcp", cluster_name="demo", approved=True)
    )
    assert result.success is True
    assert calls == [[
        "gcloud", "container", "clusters", "delete", "demo",
        "--project", "proj-1", "--region", "asia-northeast3", "--quiet",
    ]]


def test_gcp_cli_absent_reported(monkeypatch):
    monkeypatch.setenv("GCP_PROJECT", "proj-1")
    monkeypatch.setattr(gcp_mod, "_run", lambda cmd, timeout=1800: (127, "gcloud: not found"))
    result = get_provisioning_adapter("gcp").provision_cluster(ProvisionSpec(provider="gcp", approved=True))
    assert result.success is False
    assert "create failed" in (result.error or "")


# --- Azure (AKS via az) ---


def test_azure_provision_is_preflight_only_without_approval(monkeypatch):
    calls = []
    monkeypatch.setenv("AZURE_RESOURCE_GROUP", "rg-1")
    monkeypatch.setattr(azure_mod, "_run", lambda cmd, timeout=1800: (calls.append(cmd) or (0, "")))
    result = get_provisioning_adapter("azure").provision_cluster(ProvisionSpec(provider="azure", cluster_name="demo"))
    assert result.success is True
    assert calls == [["az", "aks", "list", "--resource-group", "rg-1", "--output", "table"]]
    assert result.context == "rg-1"


def test_azure_provision_creates_only_when_approved(monkeypatch):
    calls = []
    monkeypatch.setenv("AZURE_RESOURCE_GROUP", "rg-1")
    monkeypatch.setenv("AZURE_REGION", "koreacentral")
    monkeypatch.setattr(azure_mod, "_run", lambda cmd, timeout=1800: (calls.append(cmd) or (0, "Created")))
    result = get_provisioning_adapter("azure").provision_cluster(
        ProvisionSpec(provider="azure", cluster_name="demo", approved=True, node_count=3)
    )
    assert result.success is True
    assert calls == [[
        "az", "aks", "create", "--resource-group", "rg-1", "--name", "demo",
        "--location", "koreacentral", "--node-count", "3", "--generate-ssh-keys", "--yes",
    ]]
    assert result.context == "demo"


def test_azure_requires_resource_group(monkeypatch):
    monkeypatch.delenv("AZURE_RESOURCE_GROUP", raising=False)
    result = get_provisioning_adapter("azure").provision_cluster(ProvisionSpec(provider="azure"))
    assert result.success is False
    assert "AZURE_RESOURCE_GROUP" in (result.error or "")


def test_azure_teardown_requires_approval(monkeypatch):
    monkeypatch.setenv("AZURE_RESOURCE_GROUP", "rg-1")
    result = get_provisioning_adapter("azure").teardown_cluster(ProvisionSpec(provider="azure", cluster_name="demo"))
    assert result.success is False
    assert "approved=True" in (result.error or "")


def test_azure_teardown_deletes_when_approved(monkeypatch):
    calls = []
    monkeypatch.setenv("AZURE_RESOURCE_GROUP", "rg-1")
    monkeypatch.setattr(azure_mod, "_run", lambda cmd, timeout=1800: (calls.append(cmd) or (0, "Deleted")))
    result = get_provisioning_adapter("azure").teardown_cluster(
        ProvisionSpec(provider="azure", cluster_name="demo", approved=True)
    )
    assert result.success is True
    assert calls == [["az", "aks", "delete", "--resource-group", "rg-1", "--name", "demo", "--yes"]]


def test_cloud_provision_tool_is_preflight_only(monkeypatch):
    """The agent tool never passes approved -> cloud provider stays read-only."""
    calls = []
    monkeypatch.setenv("GCP_PROJECT", "proj-1")
    monkeypatch.setattr(gcp_mod, "_run", lambda cmd, timeout=1800: (calls.append(cmd) or (0, "")))
    out = provision_tools.provision_cluster(cluster_name="demo", provider="gcp")
    assert out["success"] is True
    assert calls and calls[0][3] == "list"  # never "create"


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
