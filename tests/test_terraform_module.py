"""Guards for the reference #7-b Terraform module (infra/terraform/aws-production).

Static checks always run; ``terraform validate`` runs only when the binary is
present AND the module has been ``terraform init``-ed (so CI without network
still passes). The wildcard check enforces the repo IAM guardrail — policies
we author must scope to exact ARNs, never ``Resource: "*"``.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

MODULE = Path(__file__).resolve().parents[1] / "infra" / "terraform" / "aws-production"


def _tf_sources() -> dict[str, str]:
    return {p.name: p.read_text(encoding="utf-8") for p in MODULE.glob("*.tf")}


def test_module_ships_the_advertised_pieces():
    names = set(_tf_sources())
    assert {"versions.tf", "vpc.tf", "eks.tf", "aurora.tf", "irsa.tf", "outputs.tf"} <= names


def test_no_bare_wildcard_resources_in_authored_policies():
    # `"*"` as a standalone quoted token is the banned bare wildcard; ARN
    # suffixes like ".../index/*" live inside longer strings and stay legal,
    # and comments (which may cite the rule itself) are ignored.
    for name, text in _tf_sources().items():
        for lineno, line in enumerate(text.splitlines(), 1):
            code = line.split("#", 1)[0]
            assert '"*"' not in code, f"bare wildcard in {name}:{lineno}"


def test_state_store_wiring_is_consistent_with_the_code_seam():
    sources = _tf_sources()
    # Aurora provisions the exact database the DSN seam expects…
    assert 'database_name               = "platform_state"' in sources["aurora.tf"]
    # …and the output hands operators a PLATFORM_STATE_DSN-shaped string.
    assert "postgresql://" in sources["outputs.tf"]
    # The managed password never lands in plain outputs.
    assert "manage_master_user_password = true" in sources["aurora.tf"]


def test_irsa_trust_is_scoped_to_the_chart_service_account():
    irsa = _tf_sources()["irsa.tf"]
    assert "system:serviceaccount:${var.chart_namespace}:${var.chart_service_account}" in irsa
    assert "sts.amazonaws.com" in irsa  # aud condition, not just sub


@pytest.mark.skipif(
    shutil.which("terraform") is None or not (MODULE / ".terraform").exists(),
    reason="terraform not installed or module not initialised",
)
def test_terraform_validate_passes():
    proc = subprocess.run(
        ["terraform", "validate", "-no-color"],
        cwd=MODULE,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
