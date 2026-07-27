#!/bin/bash
# Put the cluster and the hub back to the demo's OPENING state: acme/dev declared
# in the registry and present nowhere else.
#
# The empty frame is the point. The video's whole arc is a tenant being built, and
# you cannot show something being built if it is already there — every previous cut
# of this demo opened on a finished screen and had nothing left to show.
#
# Two different kinds of emptiness have to be arranged:
#   cluster — no namespaces, no quota, no Applications for acme
#   hub     — no STORED status for acme/dev, so the row reads "never reported"
#             rather than "no heartbeat". The store is in-memory, so the hub is
#             restarted; globex is pushed once straight after so the fleet table
#             still has a healthy neighbour to contrast against.
#
# Usage: bash scripts/demo/prep_fullstack.sh
set -u
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO"

ROUTER_PORT=${ROUTER_PORT:-8077}
PROXY_PORT=${PROXY_PORT:-18091}
MLX_MODEL=${MLX_MODEL:-mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit}
PUSH_KEYS='{"acme/dev":"local-dev","globex/dev":"local-dev"}'
LOG_DIR=/tmp/platform-agent
mkdir -p "$LOG_DIR"

echo "→ stopping the acme pusher (its reports are what we are clearing)"
pkill -f "push_addon_status.py --tenant acme" 2>/dev/null; true

echo "→ removing acme's Applications (finalizer cascades to the workloads)"
kubectl delete application -n argocd acme-dev-logging acme-dev-tracing \
  --ignore-not-found --timeout=120s 2>/dev/null

echo "→ removing acme's namespaces"
kubectl delete namespace acme-dev-logging acme-dev-observability \
  acme-dev-progressive acme-dev-tracing --ignore-not-found --timeout=180s 2>/dev/null

echo "→ removing the Capsule Tenant (so the quota panel starts empty too)"
kubectl delete tenant.capsule.clastix.io acme-dev --ignore-not-found --timeout=60s 2>/dev/null

echo "→ restarting the hub to clear its in-memory status store"
pkill -f "uvicorn src.agents.ai.local_deploy_api" 2>/dev/null; true
sleep 2
( cd examples/orders-api && PYTHONPATH="$REPO" \
    PLATFORM_ACTIVITY_FILE="$HOME/.platform-agent/activity.jsonl" \
    PLATFORM_PUSH_KEYS="$PUSH_KEYS" \
    ONPREM_LLM_ENDPOINT="http://127.0.0.1:$PROXY_PORT/v1" ONPREM_LLM_MODEL="$MLX_MODEL" \
    nohup uvicorn src.agents.ai.local_deploy_api:app --host 127.0.0.1 --port "$ROUTER_PORT" \
    > "$LOG_DIR/router.log" 2>&1 & )
until curl -s -m 2 "http://127.0.0.1:$ROUTER_PORT/health" >/dev/null 2>&1; do sleep 1; done
echo "   hub back up on :$ROUTER_PORT with an empty store"

echo "→ one globex push, so the neighbour tenant is on screen from frame one"
PLATFORM_PUSH_KEY=local-dev python scripts/push_addon_status.py \
  --tenant globex --env dev --hub "http://127.0.0.1:$ROUTER_PORT" --once

echo
echo "opening state ready:"
curl -s -m 5 "http://127.0.0.1:$ROUTER_PORT/api/platform/status" | python3 -c "
import json,sys
d = json.load(sys.stdin)
print('  reporting :', sorted({s['tenant'] + '/' + s['env'] for s in d['statuses']}) or 'none')
print('  missing   :', d.get('missing'))
"
