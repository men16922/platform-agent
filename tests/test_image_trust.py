"""
Guards for the consumer half of image signing.

`make sign-image` (2026-08-08) produced this repo's first signatures and, in the
same stroke, this repo's own favourite defect: a **producer with no consumer**.
Signatures were being minted and nothing read them at the point of use, which
makes them a build artifact rather than a control.

What these guards hold:

  1. The refusal happens **before the cluster call** — a check that runs after the
     workload lands is not a gate.
  2. "Could not evaluate" refuses, exactly like "not signed". Failing open because
     cosign was missing is the failure the verifier was written to prevent, and it
     is worse than no check because everything downstream then believes the image
     was verified.
  3. Off by default, and off means **nothing was checked** — not "checked and
     fine". Same honesty requirement as the scope credentials (STATUS Risk 3).
  4. Enforcement with no identity configured is a configuration error, not a pass.
     Verifying against "any signature" accepts a signature from anyone.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.agents.platform.image_trust import (
    IDENTITY_ENV,
    INSECURE_REGISTRY_ENV,
    ISSUER_ENV,
    PUBLIC_KEY_ENV,
    REQUIRE_SIGNED_ENV,
    ImageTrustError,
    enforcement_enabled,
    require_trusted_image,
)

IMAGE = "localhost:5001/platform-agent@sha256:" + "a" * 64


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for var in (REQUIRE_SIGNED_ENV, PUBLIC_KEY_ENV, IDENTITY_ENV, ISSUER_ENV,
                INSECURE_REGISTRY_ENV):
        monkeypatch.delenv(var, raising=False)


def _verifier_exits(code: int, output: str = ""):
    """Patch the verifier subprocess, not the policy that reads its exit code."""
    proc = MagicMock(returncode=code, stdout=output, stderr="")
    return patch("src.agents.platform.image_trust.subprocess.run", return_value=proc)


class TestItIsOffUntilConfigured:
    def test_unset_means_no_check_runs(self):
        """
        The important half: not "it passed" but "nothing happened". A caller that
        reports this as a verified deploy is making a claim nobody earned.
        """
        assert enforcement_enabled() is False
        with _verifier_exits(1) as run:   # would refuse if it were consulted
            require_trusted_image(IMAGE)
        run.assert_not_called()

    def test_enabling_it_without_an_identity_is_a_config_error(self, monkeypatch):
        monkeypatch.setenv(REQUIRE_SIGNED_ENV, "true")
        with pytest.raises(ImageTrustError, match="any signature"):
            require_trusted_image(IMAGE)

    def test_an_identity_without_an_issuer_is_refused(self, monkeypatch):
        """A SAN alone accepts that name from any issuer willing to mint it."""
        monkeypatch.setenv(REQUIRE_SIGNED_ENV, "1")
        monkeypatch.setenv(IDENTITY_ENV, "ci@example.com")
        with pytest.raises(ImageTrustError, match="must be set together"):
            require_trusted_image(IMAGE)


class TestTheVerdictIsTheVerifiersExitCode:
    @pytest.fixture(autouse=True)
    def _enabled(self, monkeypatch, tmp_path):
        monkeypatch.setenv(REQUIRE_SIGNED_ENV, "true")
        monkeypatch.setenv(PUBLIC_KEY_ENV, str(tmp_path / "cosign.pub"))

    def test_verified_passes(self):
        with _verifier_exits(0):
            require_trusted_image(IMAGE)  # no raise

    def test_unsigned_is_refused(self):
        with _verifier_exits(1, "no signatures found"):
            with pytest.raises(ImageTrustError, match="no valid signature"):
                require_trusted_image(IMAGE)

    def test_could_not_evaluate_is_also_refused(self):
        """
        The one that matters. cosign missing, registry unreachable, bad ref — all
        exit 2, and none of them is evidence the image is fine. Failing open here
        would make every downstream reader believe a check happened.
        """
        with _verifier_exits(2, "cosign is not installed"):
            with pytest.raises(ImageTrustError, match="could not establish"):
                require_trusted_image(IMAGE)

    def test_the_refusal_says_which_kind_of_failure_it_was(self):
        """An operator must not read a broken checker as a forged image."""
        with _verifier_exits(2, "registry unreachable"):
            with pytest.raises(ImageTrustError) as excinfo:
                require_trusted_image(IMAGE)
        assert "failure of the check, not a verdict" in str(excinfo.value)

    def test_an_empty_image_uri_is_refused_not_skipped(self):
        with pytest.raises(ImageTrustError, match="no image URI"):
            require_trusted_image("")

    def test_insecure_registry_flag_is_passed_through(self, monkeypatch):
        monkeypatch.setenv(INSECURE_REGISTRY_ENV, "true")
        with _verifier_exits(0) as run:
            require_trusted_image(IMAGE)
        assert "--allow-insecure-registry" in run.call_args.args[0]


class TestTheDeployPathRefusesBeforeItDeploys:
    """A check that runs after the workload lands is not a gate."""

    def test_a_refused_image_never_reaches_the_cluster_adapter(self, monkeypatch, tmp_path):
        from src.agents.ai import local_deployer

        monkeypatch.setenv(REQUIRE_SIGNED_ENV, "true")
        monkeypatch.setenv(PUBLIC_KEY_ENV, str(tmp_path / "cosign.pub"))

        adapters = MagicMock()
        with _verifier_exits(1, "no signatures found"), \
             patch.object(local_deployer, "get_deployment_adapters", return_value=adapters):
            result = local_deployer.deploy_to_cluster(
                service_name="orders-api", image="orders-api", version="1.0.0",
                image_uri=IMAGE, provider="onprem",
            )

        adapters.cluster.deploy.assert_not_called()
        assert result["status"] == "failed"
        assert "signature refused" in result["error"]

    def test_a_verified_image_still_deploys(self, monkeypatch, tmp_path):
        """Enforcement must not become an outage for correctly signed images."""
        from src.agents.ai import local_deployer

        monkeypatch.setenv(REQUIRE_SIGNED_ENV, "true")
        monkeypatch.setenv(PUBLIC_KEY_ENV, str(tmp_path / "cosign.pub"))

        adapters = MagicMock()
        adapters.cluster.deploy.return_value = MagicMock(
            status=MagicMock(value="succeeded"), deployment_id="d-1",
            namespace="default", replicas_desired=1, endpoint=None, error=None,
        )
        with _verifier_exits(0), \
             patch.object(local_deployer, "get_deployment_adapters", return_value=adapters):
            result = local_deployer.deploy_to_cluster(
                service_name="orders-api", image="orders-api", version="1.0.0",
                image_uri=IMAGE, provider="onprem",
            )

        adapters.cluster.deploy.assert_called_once()
        assert result["status"] == "succeeded"

    def test_with_enforcement_off_the_deploy_is_untouched(self):
        """The default path must not gain a dependency on cosign being present."""
        from src.agents.ai import local_deployer

        adapters = MagicMock()
        adapters.cluster.deploy.return_value = MagicMock(
            status=MagicMock(value="succeeded"), deployment_id="d-1",
            namespace="default", replicas_desired=1, endpoint=None, error=None,
        )
        with _verifier_exits(2) as run, \
             patch.object(local_deployer, "get_deployment_adapters", return_value=adapters):
            result = local_deployer.deploy_to_cluster(
                service_name="orders-api", image="orders-api", version="1.0.0",
                image_uri=IMAGE, provider="onprem",
            )

        run.assert_not_called()
        adapters.cluster.deploy.assert_called_once()
        assert result["status"] == "succeeded"
