"""On-prem provisioning adapter — Terraform (kind, Tier 1) + Ansible (k3s, Tier 2).

Terraform provisions the substrate (here: a kind cluster + local registry on
Docker — testable on a Mac with no VMs). Ansible configures real Linux nodes
(installs k3s) for the realistic on-prem path. Both are wrapped via subprocess.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from src.agents.adapters.provisioning.base import ProvisionResult, ProvisionSpec

# repo_root/infra/onprem/{terraform,ansible}
_REPO_ROOT = Path(__file__).resolve().parents[4]
_TF_DIR = _REPO_ROOT / "infra" / "onprem" / "terraform"
_ANSIBLE_DIR = _REPO_ROOT / "infra" / "onprem" / "ansible"


def _run(cmd: list[str], cwd: str | None = None, timeout: int = 900) -> tuple[int, str]:
    try:
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError as exc:
        return 127, str(exc)
    except subprocess.TimeoutExpired:
        return 124, f"timed out after {timeout}s"
    return result.returncode, ((result.stdout or "") + (result.stderr or "")).strip()


class OnPremProvisionAdapter:
    tf_dir: Path = _TF_DIR
    ansible_dir: Path = _ANSIBLE_DIR

    def provision_cluster(self, spec: ProvisionSpec) -> ProvisionResult:
        if spec.mode == "kind":
            return self._terraform("apply", spec)
        if spec.mode == "k3s":
            return self._ansible(spec)
        return ProvisionResult(False, spec.cluster_name, error=f"unknown provisioning mode: {spec.mode}")

    def teardown_cluster(self, spec: ProvisionSpec) -> ProvisionResult:
        if spec.mode == "kind":
            return self._terraform("destroy", spec)
        return ProvisionResult(
            False, spec.cluster_name, error="k3s teardown is manual (e.g. `multipass delete <node>`)"
        )

    # --- Terraform (kind) ---
    def _terraform(self, action: str, spec: ProvisionSpec) -> ProvisionResult:
        rc, out = _run(["terraform", "init", "-input=false", "-backend=false"], cwd=str(self.tf_dir))
        if rc != 0:
            return ProvisionResult(False, spec.cluster_name, output=out[-4000:], error="terraform init failed")
        rc, out = _run(
            [
                "terraform",
                action,
                "-auto-approve",
                "-input=false",
                f"-var=cluster_name={spec.cluster_name}",
                f"-var=registry_port={spec.registry_port}",
            ],
            cwd=str(self.tf_dir),
        )
        ok = rc == 0
        return ProvisionResult(
            success=ok,
            cluster_name=spec.cluster_name,
            context=f"kind-{spec.cluster_name}" if action == "apply" else None,
            output=out[-4000:],
            error=None if ok else f"terraform {action} failed",
        )

    # --- Ansible (k3s on VM/bare-metal) ---
    def _ansible(self, spec: ProvisionSpec) -> ProvisionResult:
        inventory = self.ansible_dir / "inventory.ini"
        if not inventory.exists():
            return ProvisionResult(
                False,
                spec.cluster_name,
                error=f"inventory not found at {inventory} (copy inventory.example.ini and set your hosts)",
            )
        rc, out = _run(
            ["ansible-playbook", "-i", str(inventory), str(self.ansible_dir / "k3s.yml")],
            cwd=str(self.ansible_dir),
        )
        ok = rc == 0
        return ProvisionResult(
            success=ok,
            cluster_name=spec.cluster_name,
            context=None,
            output=out[-4000:],
            error=None if ok else "ansible-playbook failed",
        )
