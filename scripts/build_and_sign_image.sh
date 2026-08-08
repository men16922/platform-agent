#!/usr/bin/env bash
# Build the platform-agent image, push it by digest, sign it, and verify the
# signature — the producer half that never existed.
#
# WHY THIS EXISTS. Measured 2026-08-08 while scoping the Cosign admission
# approval: `cosign sign` appeared nowhere in this repo, there is no CI, and the
# only caller of scripts/verify_image_signature.py was its own unit test. The
# chart shipped `platform-agent:0.1.0` — a bare tag with no registry host and
# `digest: ""` — so a signature had nowhere to live, because a cosign signature
# is an artifact stored in a registry beside a DIGEST. Installing a policy
# controller in that state would not enforce signing; it would deny every
# workload. The prerequisite was this script.
#
# WHAT IT IS NOT. Local development only, the same label Makefile:256 puts on the
# approval signing key: the key is generated here with an empty password and kept
# out of the repo. A real deployment signs in CI with a KMS key or keyless OIDC,
# and `scripts/verify_image_signature.py` already speaks both (--key and
# --certificate-identity/--certificate-oidc-issuer).
#
# Verification deliberately shells out to scripts/verify_image_signature.py
# rather than calling `cosign verify` again: that script already refuses to
# report "could not check" as "fine", and duplicating the check here would mean
# two places that could disagree about what verified means.
#
# Usage:
#   make sign-image                 # build + push + sign + verify
#   IMAGE_VERSION=0.2.0 make sign-image
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REGISTRY="${IMAGE_REGISTRY:-localhost:5001}"
NAME="${IMAGE_NAME:-platform-agent}"
VERSION="${IMAGE_VERSION:-0.1.0}"
# Kept beside the other local-dev credentials, never in the repo. See KEY_DIR
# note below before pointing this at anything shared.
KEY_DIR="${COSIGN_KEY_DIR:-$HOME/.platform-agent/cosign}"
KEY="${KEY_DIR}/cosign.key"
PUB="${KEY_DIR}/cosign.pub"

info() { printf '\033[1;34m→\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31m✗\033[0m %s\n' "$*" >&2; exit 1; }
ok()   { printf '\033[1;32m✓\033[0m %s\n' "$*"; }

command -v docker >/dev/null || fail "docker not found"
command -v cosign >/dev/null || fail "cosign not found (brew install cosign)"

# --- 0. registry reachable ------------------------------------------------
# Checked before the build so a missing registry costs a second rather than a
# full image build. `make local-cluster` is what stands it up.
curl -fsS --max-time 5 "http://${REGISTRY}/v2/" >/dev/null 2>&1 \
  || fail "registry ${REGISTRY} unreachable — run 'make local-cluster' first"

# --- 1. key ---------------------------------------------------------------
if [[ ! -f "$KEY" ]]; then
  info "generating a LOCAL DEV cosign keypair in ${KEY_DIR}"
  mkdir -p "$KEY_DIR"
  # Empty password: this is a development key, and prompting here would make the
  # target unusable in a scripted run. It is not a secret-management story.
  ( cd "$KEY_DIR" && COSIGN_PASSWORD="" cosign generate-key-pair >/dev/null )
  ok "keypair created (dev only — do NOT reuse this for anything real)"
else
  ok "using existing key ${KEY}"
fi

# --- 2. build -------------------------------------------------------------
REF="${REGISTRY}/${NAME}:${VERSION}"
info "building ${REF} from infra/onprem/Dockerfile"
docker build -f "${REPO_ROOT}/infra/onprem/Dockerfile" -t "$REF" "$REPO_ROOT"

# --- 3. push, and take the digest from the push itself --------------------
# The digest is read from `docker push` output rather than from a local
# `docker inspect`: what we sign has to be what the registry actually holds. A
# locally-computed id can differ from the pushed manifest digest, and signing the
# wrong one produces a signature that verifies nowhere.
info "pushing ${REF}"
PUSH_OUT="$(docker push "$REF")"
DIGEST="$(printf '%s\n' "$PUSH_OUT" | sed -n 's/.*digest: \(sha256:[0-9a-f]\{64\}\).*/\1/p' | tail -1)"
[[ -n "$DIGEST" ]] || fail "could not read a digest from docker push output"
BY_DIGEST="${REGISTRY}/${NAME}@${DIGEST}"
ok "pushed ${BY_DIGEST}"

# --- 4. sign the DIGEST ---------------------------------------------------
# Signing the tag would sign whatever the tag points at right now, and a tag is a
# mutable pointer — verify_image_signature.py's docstring records the live
# finding that re-pointing a tag makes verification fail with "no signatures
# found". Only the digest names the thing being signed.
info "signing ${BY_DIGEST}"
COSIGN_PASSWORD="" cosign sign --yes --key "$KEY" \
  --allow-insecure-registry --allow-http-registry "$BY_DIGEST" >/dev/null
ok "signed"

# --- 5. verify through the repo's own gate --------------------------------
info "verifying via scripts/verify_image_signature.py"
COSIGN_REPOSITORY="" python "${REPO_ROOT}/scripts/verify_image_signature.py" \
  "$BY_DIGEST" --key "$PUB" --allow-insecure-registry
ok "signature verified"

cat <<EOF

  digest: ${DIGEST}

Pin it for a deploy that runs what was verified:

  helm upgrade --install platform-agent infra/helm/platform-agent \\
    --set image.repository=${REGISTRY}/${NAME} \\
    --set image.digest=${DIGEST}

The chart's committed values keep image.digest empty on purpose — this digest is
local to this machine's registry, and a digest checked into the chart would be a
claim about an image nobody else has.
EOF
