#!/usr/bin/env bash
# Mint a short-lived kubeconfig for the deploy identity.
#
#   python scripts/render_deploy_identity.py | kubectl apply -f -
#   eval "$(scripts/mint_deploy_kubeconfig.sh --export)"
#   # ... deploys now run as platform-agent-deployer, not cluster-admin
#
# Short-lived on purpose (default 1h, same as the per-tenant incident credentials in
# phase1a): a file that never expires is a credential that outlives the reason it was
# minted. Re-run it; that is cheaper than rotating something long-lived.
#
# Why a token and not a client cert: `kubectl create token` is bounded by the API
# server and needs no CA private key, so this works against a managed cluster too.
set -euo pipefail

NAME="${NAME:-platform-agent-deployer}"
NAMESPACE="${NAMESPACE:-platform-agent-system}"
DURATION="${DURATION:-1h}"
OUT="${OUT:-$HOME/.platform-agent/deploy.kubeconfig}"
EXPORT=0

while [ $# -gt 0 ]; do
  case "$1" in
    --export) EXPORT=1 ;;
    --out) OUT="$2"; shift ;;
    --duration) DURATION="$2"; shift ;;
    --name) NAME="$2"; shift ;;
    --namespace) NAMESPACE="$2"; shift ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
  shift
done

context="$(kubectl config current-context)"
cluster="$(kubectl config view -o jsonpath="{.contexts[?(@.name==\"$context\")].context.cluster}")"
server="$(kubectl config view -o jsonpath="{.clusters[?(@.name==\"$cluster\")].cluster.server}")"
ca="$(kubectl config view --raw -o jsonpath="{.clusters[?(@.name==\"$cluster\")].cluster.certificate-authority-data}")"

if [ -z "$server" ]; then
  echo "could not read the API server URL for context '$context'" >&2
  exit 1
fi

token="$(kubectl create token "$NAME" -n "$NAMESPACE" --duration="$DURATION")"

mkdir -p "$(dirname "$OUT")"
umask 077
cat > "$OUT" <<EOF
apiVersion: v1
kind: Config
clusters:
- name: ${cluster}
  cluster:
    server: ${server}
$( [ -n "$ca" ] && echo "    certificate-authority-data: ${ca}" || echo "    insecure-skip-tls-verify: true" )
users:
- name: ${NAME}
  user:
    token: ${token}
contexts:
- name: ${NAME}
  context:
    cluster: ${cluster}
    user: ${NAME}
current-context: ${NAME}
EOF

if [ "$EXPORT" = "1" ]; then
  echo "export PLATFORM_DEPLOY_KUBECONFIG=$OUT"
else
  echo "wrote $OUT (valid $DURATION)" >&2
  echo "  export PLATFORM_DEPLOY_KUBECONFIG=$OUT" >&2
fi
