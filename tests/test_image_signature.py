"""
Guards for the cosign verification gate.

The rule every case here encodes: "could not check" must never be reported as
"checked and fine". An unsigned image is a verdict; a missing verifier is not,
and collapsing the two is how a supply-chain gate becomes decoration.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


def _script():
    path = Path(__file__).resolve().parents[1] / "scripts" / "verify_image_signature.py"
    spec = importlib.util.spec_from_file_location("verify_image_signature", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


verify = _script()


class TestClassify:
    def test_success_is_verified(self):
        assert verify.classify(0, "") == verify.VERIFIED

    @pytest.mark.parametrize(
        "output",
        [
            "Error: no signatures found",
            "error during command execution: no matching signatures",
            "none of the expected identities matched what was in the certificate",
        ],
    )
    def test_absent_signature_is_a_verdict_about_the_image(self, output):
        assert verify.classify(1, output) == verify.NOT_SIGNED

    @pytest.mark.parametrize(
        "output",
        [
            "connection refused",
            "UNAUTHORIZED: authentication required",
            "could not parse reference",
        ],
    )
    def test_checker_failures_are_not_downgraded_to_unsigned(self, output):
        """Calling a network error 'unsigned' invents a verdict we did not earn."""
        assert verify.classify(1, output) == verify.COSIGN_MISSING

    def test_case_is_not_load_bearing(self):
        assert verify.classify(1, "Error: NO SIGNATURES FOUND") == verify.NOT_SIGNED


class TestUsage:
    def test_missing_cosign_exits_could_not_evaluate(self, monkeypatch, capsys):
        monkeypatch.setattr(verify.shutil, "which", lambda _: None)
        monkeypatch.setattr("sys.argv", ["v", "img", "--key", "k.pub"])
        assert verify.main() == verify.COSIGN_MISSING
        assert "UNVERIFIED" in capsys.readouterr().err

    def test_no_identity_is_refused(self, monkeypatch, capsys):
        """Verifying against 'any signature' accepts a signature from anyone."""
        monkeypatch.setattr("sys.argv", ["v", "img"])
        assert verify.main() == verify.COSIGN_MISSING
        assert "--key" in capsys.readouterr().err

    def test_keyed_command_shape(self):
        args = verify.argparse.Namespace(
            image="repo@sha256:abc",
            key="cosign.pub",
            certificate_identity=None,
            certificate_oidc_issuer=None,
            allow_insecure_registry=True,
        )
        cmd = verify.build_command(args)
        assert cmd[:2] == ["cosign", "verify"]
        assert "--key" in cmd and "cosign.pub" in cmd
        assert "--allow-insecure-registry" in cmd
        assert cmd[-1] == "repo@sha256:abc", "the image ref must be the final positional arg"

    def test_keyless_command_shape(self):
        args = verify.argparse.Namespace(
            image="repo:tag",
            key=None,
            certificate_identity="https://github.com/men16922/platform-agent/.github/workflows/x.yml@refs/heads/main",
            certificate_oidc_issuer="https://token.actions.githubusercontent.com",
            allow_insecure_registry=False,
        )
        cmd = verify.build_command(args)
        assert "--certificate-identity" in cmd and "--certificate-oidc-issuer" in cmd
        assert "--key" not in cmd
