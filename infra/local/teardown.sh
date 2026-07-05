#!/usr/bin/env bash
# infra/local/teardown.sh — Destroy kind cluster and local registry
set -euo pipefail

CLUSTER_NAME="platform-agent"
REG_NAME="kind-registry"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[teardown]${NC} $*"; }
warn()  { echo -e "${YELLOW}[teardown]${NC} $*"; }

# --- Delete kind cluster ---
if kind get clusters 2>/dev/null | grep -q "^${CLUSTER_NAME}$"; then
  info "Deleting kind cluster '${CLUSTER_NAME}'..."
  kind delete cluster --name "${CLUSTER_NAME}"
else
  warn "Cluster '${CLUSTER_NAME}' does not exist."
fi

# --- Remove registry container ---
if docker inspect "${REG_NAME}" >/dev/null 2>&1; then
  info "Removing registry container '${REG_NAME}'..."
  docker rm -f "${REG_NAME}"
else
  warn "Registry '${REG_NAME}' does not exist."
fi

# --- Clean up docker network (kind auto-creates, auto-deletes with cluster) ---
info "Done. All resources cleaned up."
