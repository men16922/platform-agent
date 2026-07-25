"""Verify a container image signature with cosign, as a gate.

Same discipline as the handoff preflight and the orphan sweeper: the dangerous
outcome is not "unsigned", it is "could not check" being reported as "fine". A
CI step that exits 0 because cosign was missing from the runner is worse than no
step at all, because everything downstream now believes the image was verified.

WHAT THE SIGNATURE ACTUALLY COVERS — a digest, not a tag. Verified live: two
tags pointing at the same digest both verify (the second was never signed by
name), and re-pointing a tag at a different image makes verification fail with
"no signatures found". So a tag is a mutable pointer to possibly-signed content,
and only `repo@sha256:...` names the thing that was signed. Deploy by digest
(the chart's image.digest) if you want what you verified to be what runs.

Usage:
  python scripts/verify_image_signature.py IMAGE --key cosign.pub
  python scripts/verify_image_signature.py IMAGE \
      --certificate-identity ... --certificate-oidc-issuer ...   # keyless

Exit codes:
  0 = signature verified
  1 = image is not validly signed (no signature, or signed by another key)
  2 = could not evaluate (cosign missing, registry unreachable, bad usage)
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys

COSIGN_MISSING = 2
NOT_SIGNED = 1
VERIFIED = 0

# cosign says this when the image exists but carries no matching signature. That
# is a real verdict about the image, not a failure of the checker, so it maps to
# 1 rather than 2.
_UNSIGNED_MARKERS = (
    "no signatures found",
    "no matching signatures",
    "none of the expected identities matched",
)


def build_command(args: argparse.Namespace) -> list[str]:
    cmd = ["cosign", "verify"]
    if args.key:
        cmd += ["--key", args.key]
    if args.certificate_identity:
        cmd += ["--certificate-identity", args.certificate_identity]
    if args.certificate_oidc_issuer:
        cmd += ["--certificate-oidc-issuer", args.certificate_oidc_issuer]
    if args.allow_insecure_registry:
        cmd.append("--allow-insecure-registry")
    cmd.append(args.image)
    return cmd


def classify(returncode: int, output: str) -> int:
    if returncode == 0:
        return VERIFIED
    lowered = output.lower()
    if any(marker in lowered for marker in _UNSIGNED_MARKERS):
        return NOT_SIGNED
    # Anything else (network, auth, malformed ref) is a checker failure. Calling
    # it "unsigned" would be inventing a verdict we did not earn.
    return COSIGN_MISSING


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", help="image reference; prefer repo@sha256:... over a tag")
    parser.add_argument("--key", help="cosign public key (keyed verification)")
    parser.add_argument("--certificate-identity", help="keyless: expected SAN")
    parser.add_argument("--certificate-oidc-issuer", help="keyless: expected issuer")
    parser.add_argument("--allow-insecure-registry", action="store_true",
                        help="plain-HTTP registry (local kind registry)")
    args = parser.parse_args()

    if not args.key and not args.certificate_identity:
        print(
            "ERROR: pass --key, or --certificate-identity with --certificate-oidc-issuer.\n"
            "  Verifying against 'any signature' accepts a signature from anyone, which is\n"
            "  indistinguishable from not checking.",
            file=sys.stderr,
        )
        return COSIGN_MISSING

    if shutil.which("cosign") is None:
        print(
            f"CANNOT EVALUATE: cosign is not installed — {args.image} is UNVERIFIED.\n"
            "  Exiting 2 on purpose: a missing verifier must not read as a pass.",
            file=sys.stderr,
        )
        return COSIGN_MISSING

    proc = subprocess.run(build_command(args), capture_output=True, text=True)
    combined = (proc.stdout or "") + (proc.stderr or "")
    verdict = classify(proc.returncode, combined)

    if verdict == VERIFIED:
        print(f"VERIFIED: {args.image}")
    elif verdict == NOT_SIGNED:
        print(f"NOT SIGNED: {args.image} carries no signature from this identity.")
        print(combined.strip()[:500], file=sys.stderr)
    else:
        print(f"CANNOT EVALUATE: {args.image} — cosign failed before reaching a verdict.")
        print(combined.strip()[:500], file=sys.stderr)
    return verdict


if __name__ == "__main__":
    raise SystemExit(main())
