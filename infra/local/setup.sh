#!/usr/bin/env bash
# infra/local/setup.sh — Create kind cluster with local registry for platform-agent
# Based on: https://kind.sigs.k8s.io/docs/user/local-registry/
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLUSTER_NAME="platform-agent"
REG_NAME="kind-registry"
REG_PORT="5001"
KIND_CONFIG="$SCRIPT_DIR/kind-config.yaml"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[setup]${NC} $*"; }
warn()  { echo -e "${YELLOW}[setup]${NC} $*"; }

# --- Check prerequisites ---
for cmd in docker kind kubectl; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "ERROR: $cmd not found. Install it first."; exit 1; }
done

# --- Check if Docker is running ---
if ! docker info >/dev/null 2>&1; then
  echo "ERROR: Docker is not running. Start Docker Desktop or Colima first."
  exit 1
fi

# --- Check if cluster already exists ---
if kind get clusters 2>/dev/null | grep -q "^${CLUSTER_NAME}$"; then
  warn "Cluster '${CLUSTER_NAME}' already exists. Skipping creation."
  warn "Use 'make local-cluster-down' to destroy and recreate."
  kubectl cluster-info --context "kind-${CLUSTER_NAME}" 2>/dev/null || true
  exit 0
fi

# --- 1. Start local registry container ---
if docker inspect "${REG_NAME}" >/dev/null 2>&1; then
  info "Registry '${REG_NAME}' already running."
else
  info "Starting local registry on localhost:${REG_PORT}..."
  docker run -d --restart=always -p "127.0.0.1:${REG_PORT}:5000" --name "${REG_NAME}" registry:2
fi

# --- 2. Create kind cluster ---
info "Creating kind cluster '${CLUSTER_NAME}' (1 control-plane + 2 workers)..."
kind create cluster --config "${KIND_CONFIG}"

# --- 3. Connect registry to kind network ---
if ! docker network inspect kind | grep -q "\"${REG_NAME}\""; then
  info "Connecting registry to kind network..."
  docker network connect kind "${REG_NAME}" 2>/dev/null || true
fi

# --- 4. Register registry with cluster (kind convention) ---
info "Registering local registry with cluster..."
kubectl apply -f - <<EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: local-registry-hosting
  namespace: kube-public
data:
  localRegistryHosting.v1: |
    host: "localhost:${REG_PORT}"
    help: "https://kind.sigs.k8s.io/docs/user/local-registry/"
EOF

# --- 5. Install NGINX Ingress Controller ---
info "Installing NGINX Ingress Controller..."
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml

# --- 6. Wait for nodes to be Ready ---
info "Waiting for all nodes to be Ready..."
kubectl wait --for=condition=Ready nodes --all --timeout=120s

# --- 7. Wait for ingress controller to be ready ---
info "Waiting for ingress controller..."
kubectl wait --namespace ingress-nginx \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/component=controller \
  --timeout=120s 2>/dev/null || warn "Ingress controller not ready yet (may take a minute)."

# --- Done ---
info "====================================="
info "Cluster '${CLUSTER_NAME}' is ready!"
info "====================================="
info "Registry:  localhost:${REG_PORT}"
info "Ingress:   http://localhost:80"
info "Context:   kind-${CLUSTER_NAME}"
info ""
info "Quick test:"
info "  kubectl get nodes"
info "  docker pull nginx:alpine"
info "  docker tag nginx:alpine localhost:${REG_PORT}/nginx:test"
info "  docker push localhost:${REG_PORT}/nginx:test"
info "  kubectl run nginx-test --image=localhost:${REG_PORT}/nginx:test"
