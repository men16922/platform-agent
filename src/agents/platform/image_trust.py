"""Refuse to deploy an image whose signature does not check out.

WHY THIS EXISTS. `make sign-image` (2026-08-08) gave this repo a signing path for
the first time — and immediately created the defect this repo has spent the day
hunting: a **producer with no consumer**. Signatures were being made and nothing
read them. A signature nobody verifies at the moment of use is a build artifact,
not a control.

This is the consumer. It sits in front of the deploy step, where the image URI is
already resolved, and it is the last point before a workload reaches a cluster.

VERIFICATION IS DELEGATED, NOT REIMPLEMENTED. The verdict comes from
`scripts/verify_image_signature.py` — the same script `build_and_sign_image.sh`
verifies with — invoked as a subprocess so its exit codes are the contract:

    0 = verified   1 = not validly signed   2 = could not evaluate

Re-deriving the verdict here would create a second place that decides what
"verified" means, and those two places would eventually disagree. In particular
that script already refuses to report "could not check" as "fine", which is the
whole discipline: **exit 2 refuses the deploy.** A verifier that fails open
because cosign was missing is worse than no verifier, because everything
downstream now believes the image was checked.

OPT-IN, AND SAID SO. Unset means no verification happens at all — the same shape,
and the same honesty requirement, as the scope and deploy-identity credentials
(STATUS Risk 3): "설정하면 집행되고, 안 하면 조용히 안 된다." Do not describe this
as "the platform verifies image signatures". It verifies them when
:data:`REQUIRE_SIGNED_ENV` is set, and refuses to guess otherwise.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

#: Turns enforcement on. Absent -> no check runs and none is claimed.
REQUIRE_SIGNED_ENV = "PLATFORM_REQUIRE_SIGNED_IMAGES"

#: Keyed verification: path to the cosign public key.
PUBLIC_KEY_ENV = "PLATFORM_COSIGN_PUBLIC_KEY"

#: Keyless verification. Both are required together — an identity without an
#: issuer would accept that SAN from any issuer that will mint it.
IDENTITY_ENV = "PLATFORM_COSIGN_CERTIFICATE_IDENTITY"
ISSUER_ENV = "PLATFORM_COSIGN_CERTIFICATE_OIDC_ISSUER"

#: Plain-HTTP registries (the local kind registry at localhost:5001).
INSECURE_REGISTRY_ENV = "PLATFORM_COSIGN_ALLOW_INSECURE_REGISTRY"

_VERIFIER = Path(__file__).resolve().parents[3] / "scripts" / "verify_image_signature.py"

VERIFIED = 0
NOT_SIGNED = 1
CANNOT_EVALUATE = 2


class ImageTrustError(RuntimeError):
    """Raised when an image may not be deployed. Always fail-closed."""


def _truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def enforcement_enabled() -> bool:
    """Whether signature enforcement is configured. Ask before claiming it."""
    return _truthy(os.getenv(REQUIRE_SIGNED_ENV, ""))


def _verifier_args() -> list[str]:
    """Build the identity flags, refusing a configuration that verifies nothing.

    `verify_image_signature.py` already rejects "no identity" for the same reason
    it is rejected here — verifying against *any* signature accepts a signature
    from anyone — but reaching that error through a subprocess would surface as
    "could not evaluate" and read like a broken tool rather than a misconfigured
    policy. Named here instead.
    """
    key = os.getenv(PUBLIC_KEY_ENV, "").strip()
    identity = os.getenv(IDENTITY_ENV, "").strip()
    issuer = os.getenv(ISSUER_ENV, "").strip()

    args: list[str] = []
    if key:
        args += ["--key", key]
    if identity or issuer:
        if not (identity and issuer):
            raise ImageTrustError(
                f"{IDENTITY_ENV} and {ISSUER_ENV} must be set together — an identity "
                "without an issuer accepts that name from any issuer willing to mint it"
            )
        args += ["--certificate-identity", identity, "--certificate-oidc-issuer", issuer]

    if not args:
        raise ImageTrustError(
            f"{REQUIRE_SIGNED_ENV} is on but no verification identity is configured — "
            f"set {PUBLIC_KEY_ENV}, or {IDENTITY_ENV} with {ISSUER_ENV}. Refusing to "
            "verify against 'any signature', which is indistinguishable from not checking"
        )

    if _truthy(os.getenv(INSECURE_REGISTRY_ENV, "")):
        args.append("--allow-insecure-registry")
    return args


def require_trusted_image(image_uri: str) -> None:
    """Raise :class:`ImageTrustError` unless ``image_uri`` may be deployed.

    Returns quietly — and checks nothing — when enforcement is off. That is the
    documented default; the caller must not report it as a passed check.
    """
    if not enforcement_enabled():
        return

    if not image_uri:
        raise ImageTrustError(
            "no image URI to verify — refusing rather than deploying something "
            "whose identity cannot be established"
        )

    # A signature binds to a digest. A tag is a mutable pointer, so verifying a
    # tag and deploying that tag leaves a window where the tag moves in between;
    # this is the live finding recorded in the verifier's own docstring. Warned
    # rather than refused: `deploy_service` resolves tags today, and turning that
    # into a hard failure would be a policy change hidden inside a trust check.
    if "@sha256:" not in image_uri:
        logger.warning(
            "image_trust.verifying_a_tag_not_a_digest",
            extra={"image_uri": image_uri},
        )

    proc = subprocess.run(
        [sys.executable, str(_VERIFIER), image_uri, *_verifier_args()],
        capture_output=True, text=True,
    )
    combined = ((proc.stdout or "") + (proc.stderr or "")).strip()

    if proc.returncode == VERIFIED:
        logger.info("image_trust.verified", extra={"image_uri": image_uri})
        return

    if proc.returncode == NOT_SIGNED:
        raise ImageTrustError(
            f"{image_uri} carries no valid signature for the configured identity — "
            f"refusing to deploy it. {combined[:300]}"
        )

    # Exit 2 and anything unexpected. Deliberately the same outcome as unsigned:
    # "we could not check" is not "it is fine", and treating it as a pass is the
    # failure mode the verifier was written to prevent.
    raise ImageTrustError(
        f"could not establish whether {image_uri} is signed — refusing to deploy. "
        f"This is a failure of the check, not a verdict about the image. {combined[:300]}"
    )
