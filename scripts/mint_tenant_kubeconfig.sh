#!/usr/bin/env bash
# Mint the per-tenant credential the incident scope broker expects.
#
#   python scripts/render_tenancy.py acme -e dev | kubectl apply -f -   # the SA
#   scripts/mint_tenant_kubeconfig.sh acme -e dev                       # the credential
#   export PLATFORM_CREDENTIAL_DIR=~/.platform-agent/credentials
#
# Why this exists: `TokenBroker.credential_path` looks for
# `$PLATFORM_CREDENTIAL_DIR/<tenant>.kubeconfig` (soft tier) and fails closed when it
# is missing — which, measured 2026-07-30, it always was. Phase 1a's live evidence
# says "per-tenant kubeconfigs minted (1h TTL)", but the minting was done by hand in
# that session and never committed, so the boundary could be demonstrated and not
# reproduced. That is the same defect this milestone keeps finding one layer up: the
# thing was proven once and had no producer.
#
# Soft tier is per-TENANT, not per-env: several tenants share one cluster by
# namespace, so a per-env credential would still reach co-tenant namespaces on the
# same cluster (see IsolationTier.credential_scope). The filename follows the broker,
# which is the authority — do not second-guess it here.
set -euo pipefail

TENANT="${1:-}"
[ -n "$TENANT" ] || { sed -n '2,20p' "$0"; exit 2; }
shift

ENV_NAME="dev"
SA="${SA:-platform-agent}"
DURATION="${DURATION:-1h}"
DIR="${PLATFORM_CREDENTIAL_DIR:-$HOME/.platform-agent/credentials}"

while [ $# -gt 0 ]; do
  case "$1" in
    -e|--env) ENV_NAME="$2"; shift ;;
    --sa) SA="$2"; shift ;;
    --duration) DURATION="$2"; shift ;;
    --dir) DIR="$2"; shift ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
  shift
done

# The SA lives in the tenant's own namespaces (render_rbac puts one in each). Any of
# them mints an equivalent token, so take the first that exists rather than hardcoding
# a capability that a given tenant may not have declared.
ns="$(kubectl get namespaces \
  -l "platform-agent.io/tenant=${TENANT},platform-agent.io/env=${ENV_NAME}" \
  -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)"

if [ -z "$ns" ]; then
  echo "no namespaces labelled tenant=${TENANT} env=${ENV_NAME} — run render_tenancy.py first" >&2
  exit 1
fi

context="$(kubectl config current-context)"
cluster="$(kubectl config view -o jsonpath="{.contexts[?(@.name==\"$context\")].context.cluster}")"
server="$(kubectl config view -o jsonpath="{.clusters[?(@.name==\"$cluster\")].cluster.server}")"
ca="$(kubectl config view --raw -o jsonpath="{.clusters[?(@.name==\"$cluster\")].cluster.certificate-authority-data}")"

token="$(kubectl create token "$SA" -n "$ns" --duration="$DURATION")"

out="${DIR}/${TENANT}.kubeconfig"
mkdir -p "$DIR"
umask 077
cat > "$out" <<EOF
apiVersion: v1
kind: Config
clusters:
- name: ${cluster}
  cluster:
    server: ${server}
$( [ -n "$ca" ] && echo "    certificate-authority-data: ${ca}" || echo "    insecure-skip-tls-verify: true" )
users:
- name: ${TENANT}
  user:
    token: ${token}
contexts:
- name: ${TENANT}
  context:
    cluster: ${cluster}
    user: ${TENANT}
    namespace: ${ns}
current-context: ${TENANT}
EOF

echo "wrote $out (SA ${SA} in ${ns}, valid ${DURATION})" >&2
echo "  export PLATFORM_CREDENTIAL_DIR=${DIR}" >&2
