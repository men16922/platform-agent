"""AWS provisioning adapter — CDK plan first, deploy only after approval."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from src.agents.adapters.provisioning.base import ProvisionResult, ProvisionSpec

_STACK_DIR = Path(__file__).resolve().parents[4] / "src" / "stacks"


def _run(cmd: list[str], cwd: str, timeout: int = 1800) -> tuple[int, str]:
    try:
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError as exc:
        return 127, str(exc)
    except subprocess.TimeoutExpired:
        return 124, f"timed out after {timeout}s"
    return result.returncode, ((result.stdout or "") + (result.stderr or "")).strip()


class AwsProvisionAdapter:
    cdk_dir: Path = _STACK_DIR

    def provision_cluster(self, spec: ProvisionSpec) -> ProvisionResult:
        env = os.environ.copy()
        if spec.region:
            env["AWS_REGION"] = spec.region
        command = ["npx", "cdk", "deploy" if spec.approved else "diff", spec.stack_name]
        if spec.approved:
            command.extend(["--require-approval", "never"])
        rc, output = _run(command, str(self.cdk_dir))
        action = "deploy" if spec.approved else "diff"
        return ProvisionResult(
            success=rc == 0,
            cluster_name=spec.cluster_name,
            context=spec.region,
            output=output[-4000:],
            error=None if rc == 0 else f"cdk {action} failed",
        )

    def teardown_cluster(self, spec: ProvisionSpec) -> ProvisionResult:
        if not spec.approved:
            return ProvisionResult(False, spec.cluster_name, error="AWS destroy requires explicit approved=True")
        rc, output = _run(["npx", "cdk", "destroy", spec.stack_name, "--force"], str(self.cdk_dir))
        return ProvisionResult(rc == 0, spec.cluster_name, output=output[-4000:], error=None if rc == 0 else "cdk destroy failed")
