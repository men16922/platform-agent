# platform-agent Makefile
.DEFAULT_GOAL := help

# ===== Project targets =====

# Test interpreter: pick the first python that can import pytest. Guards against a
# shell that has .venv-mlx (MLX-only, no pytest) activated shadowing the test env.
PY := $(shell for p in python python3 /opt/anaconda3/bin/python3.13; do "$$p" -c 'import pytest' >/dev/null 2>&1 && echo "$$p" && break; done)
PY := $(if $(PY),$(PY),python3)

.PHONY: help install test check lint synth sweep-orphans

help:  ## show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

install:  ## install Python deps (editable + dev)
	pip install -e ".[dev]"

test:  ## run pytest
	$(PY) -m pytest tests/ -v

check: test  ## gate command (overnight harness uses this)

lint:  ## run ruff
	ruff check src/ tests/

sweep-orphans:  ## report over-budget cloud clusters (read-only; deletion stays approval-gated)
	@# Complements the local TTL watchdog, which dies with the machine. Exit 1 =
	@# orphans found, so this is usable as a cron/CI signal. GCP_PROJECT selects
	@# the project — the active gcloud config may not be the one that bills.
	python scripts/sweep_orphan_clusters.py --max-age-min $${SWEEP_MAX_AGE_MIN:-1440}

synth:  ## CDK synth
	cd src/stacks && npx cdk synth

# ===== On-prem (kind) cluster targets =====

local-cluster:  ## create kind cluster + local registry + ingress
	bash infra/local/setup.sh

local-cluster-down:  ## destroy kind cluster + registry
	bash infra/local/teardown.sh

local-cluster-status:  ## show cluster node and pod status
	@kubectl get nodes -o wide 2>/dev/null || echo "No cluster running"
	@echo ""
	@kubectl get pods -A 2>/dev/null || true

sign-image:  ## build + push by digest + cosign sign + verify through the repo's own gate
	bash scripts/build_and_sign_image.sh

.PHONY: local-cluster local-cluster-down local-cluster-status sign-image
.PHONY: mlx-setup

# ===== Local LLM natural-language deploy stack (AI Model Router) =====
# MLX-LM (Qwen) -> tool-call proxy -> AI Model Router API. The dashboard Agents
# chat (LOCAL_DEPLOY_API_URL) drives on-prem deploys through this stack.
MLX_MODEL      ?= mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit
MLX_PORT       ?= 18090
PROXY_PORT     ?= 18091
ROUTER_PORT    ?= 8077
# Working dir for docker build context (orders-api demo builds from its dir).
DEPLOY_WORKDIR ?= examples/orders-api
LLM_LOG_DIR    := /tmp/platform-agent
# Offline activity store: the router WRITES deploy/rollback rows here and the
# dashboard READS them (hybrid = this file + AWS). Same path on both sides.
ACTIVITY_FILE  ?= $(HOME)/.platform-agent/activity.jsonl
# Local-only HMAC keys for the spoke->hub status push. The hub accepts NOTHING
# without keys (an unconfigured hub that accepted unsigned reports would let
# anyone who can reach the port write any tenant's status), so the local stack
# has to hand it one. Fixed value on purpose: this is a loopback dev key, and a
# random one would break the pushers started in a different shell.
PLATFORM_PUSH_KEYS ?= {"acme/dev":"local-dev","globex/dev":"local-dev"}
PUSH_TENANTS   ?= acme globex
APPROVALS_FILE ?= $(HOME)/.platform-agent/pending-approvals.jsonl
INCIDENT_FILE  ?= $(HOME)/.platform-agent/incidents.jsonl
WEBHOOK_PORT   ?= 8078
DASHBOARD_DIR  ?= dashboard
DASHBOARD_PORT ?= 3000

# ===== Add-on console port-forwards =====
# The Provisioning screen links to each add-on's own UI. Those links are only
# reachable while a port-forward is up, and `dev-up` did not start them — so
# every "Open" on that screen was dead unless someone had run kubectl by hand.
#
# The ports live here rather than in the dashboard because the dashboard is the
# CONSUMER: it is handed URLs through NEXT_PUBLIC_*_URL (below), so the forward
# and the link can never disagree. The code's own defaults are a last resort for
# a bare `npm run dev`.
#
# Grafana is NOT on 3001. That default collided with an unrelated local project
# already listening there, and the failure mode is the worst kind — the link
# opens and shows someone else's app instead of erroring.
ARGOCD_PORT       ?= 8090
GRAFANA_PORT      ?= 3002
PROMETHEUS_PORT   ?= 9090
ALERTMANAGER_PORT ?= 9093
ROLLOUTS_PORT     ?= 3101
CONSOLE_URLS = NEXT_PUBLIC_ARGOCD_URL=https://localhost:$(ARGOCD_PORT) \
               NEXT_PUBLIC_GRAFANA_URL=http://localhost:$(GRAFANA_PORT) \
               NEXT_PUBLIC_PROMETHEUS_URL=http://localhost:$(PROMETHEUS_PORT) \
               NEXT_PUBLIC_ALERTMANAGER_URL=http://localhost:$(ALERTMANAGER_PORT) \
               NEXT_PUBLIC_ROLLOUTS_URL=http://localhost:$(ROLLOUTS_PORT)/rollouts

# The local stack runs MLX from its OWN venv, deliberately separate from the test
# env (see the note at the top of this file: an activated .venv-mlx shadows pytest).
#
# Measured 2026-08-30: **nothing in this repo created it.** `.venv-mlx` was a
# hand-made venv holding mlx-lm and mlx and nothing else — not the project, not
# `.[onprem]`. So on a fresh clone `make dev-up` launched a binary that does not
# exist, under `nohup ... &` with stdout to a log, and failed **silently**: the
# stack printed "model load takes ~30-60s" and the proxy then talked to nothing.
# That is this repo's recurring shape — it fails in a way that does not error.
#
# `mlx-lm` is also listed in the `onprem` extra, but nothing installs it that way
# (and that entry is why CI names `pydantic-ai-slim` inline instead of using the
# extra). The extra is not the mechanism; this target is.
MLX_BIN := .venv-mlx/bin/mlx_lm.server
MLX_MISSING = echo "ERROR: $(MLX_BIN) is missing. The local stack runs MLX from its own venv — create it with: make mlx-setup"; exit 1

# ⚠️ One shell block on purpose. The first version of this target guarded with
# `@test ! -x $(MLX_BIN) || { echo ...; exit 0; }` on its own line — and Make runs
# each recipe line in a *separate* shell, so that `exit 0` ended only that line and
# pip ran anyway against an existing venv. A check that does not gate what follows
# is not a check; it is the same shape this repo keeps finding one layer up.
mlx-setup:  ## create .venv-mlx, the MLX-only venv the local stack runs from
	@if [ -x $(MLX_BIN) ]; then \
	  echo "→ $(MLX_BIN) already present — nothing to do"; \
	else \
	  python3 -m venv .venv-mlx && \
	  .venv-mlx/bin/pip install --upgrade pip && \
	  .venv-mlx/bin/pip install "mlx-lm>=0.19" && \
	  echo "ok — $(MLX_BIN) ready (mlx resolves only on macOS/Apple Silicon)"; \
	fi

mlx-serve:  ## start local MLX-LM server (run in its own terminal)
	@test -x $(MLX_BIN) || { $(MLX_MISSING); }
	HF_HUB_DISABLE_XET=1 .venv-mlx/bin/mlx_lm.server --model $(MLX_MODEL) --host 127.0.0.1 --port $(MLX_PORT) --max-tokens 1024 --prompt-cache-bytes 2147483648

mlx-proxy:  ## start the MLX Qwen tool-call proxy
	python -m src.agents.ai.mlx_qwen_tool_proxy --upstream http://127.0.0.1:$(MLX_PORT) --host 127.0.0.1 --port $(PROXY_PORT)

router-api:  ## start the AI Model Router API (natural-language deploy)
	cd $(DEPLOY_WORKDIR) && PYTHONPATH=$(CURDIR) PLATFORM_ACTIVITY_FILE=$(ACTIVITY_FILE) ONPREM_LLM_ENDPOINT=http://127.0.0.1:$(PROXY_PORT)/v1 ONPREM_LLM_MODEL=$(MLX_MODEL) uvicorn src.agents.ai.local_deploy_api:app --host 127.0.0.1 --port $(ROUTER_PORT)

onprem-webhook:  ## start the On-Prem PATH B webhook (Alertmanager -> Day-2 incident pipeline + approval gate). Analyzer prioritises local Qwen (offline); set ANALYZER_LLM_ENDPOINT= to force Bedrock.
	PLATFORM_ACTIVITY_FILE=$(ACTIVITY_FILE) PLATFORM_APPROVALS_FILE=$(APPROVALS_FILE) PLATFORM_INCIDENT_FILE=$(INCIDENT_FILE) ANALYZER_LLM_ENDPOINT=http://127.0.0.1:$(PROXY_PORT)/v1 ANALYZER_LLM_MODEL=$(MLX_MODEL) uvicorn src.agents.ai.onprem_webhook_api:app --host 127.0.0.1 --port $(WEBHOOK_PORT)

local-llm-up:  ## start MLX + proxy + router API in the background (logs in /tmp/platform-agent)
	@mkdir -p $(LLM_LOG_DIR)
	@test -x $(MLX_BIN) || { $(MLX_MISSING); }
	@echo "→ MLX-LM server (:$(MLX_PORT)) — model load takes ~30-60s"
	@HF_HUB_DISABLE_XET=1 nohup .venv-mlx/bin/mlx_lm.server --model $(MLX_MODEL) --host 127.0.0.1 --port $(MLX_PORT) --max-tokens 1024 --prompt-cache-bytes 2147483648 > $(LLM_LOG_DIR)/mlx.log 2>&1 &
	@echo "→ tool-call proxy (:$(PROXY_PORT))"
	@nohup python -m src.agents.ai.mlx_qwen_tool_proxy --upstream http://127.0.0.1:$(MLX_PORT) --host 127.0.0.1 --port $(PROXY_PORT) > $(LLM_LOG_DIR)/proxy.log 2>&1 &
	@echo "→ router API (:$(ROUTER_PORT), workdir=$(DEPLOY_WORKDIR)) — records into $(ACTIVITY_FILE) (add PLATFORM_ACTIVITY_TABLE+AWS_REGION for DynamoDB)"
	@cd $(DEPLOY_WORKDIR) && PYTHONPATH=$(CURDIR) PLATFORM_ACTIVITY_FILE=$(ACTIVITY_FILE) ONPREM_LLM_ENDPOINT=http://127.0.0.1:$(PROXY_PORT)/v1 ONPREM_LLM_MODEL=$(MLX_MODEL) nohup uvicorn src.agents.ai.local_deploy_api:app --host 127.0.0.1 --port $(ROUTER_PORT) > $(LLM_LOG_DIR)/router.log 2>&1 &
	@echo "stack starting. Watch: tail -f $(LLM_LOG_DIR)/mlx.log | check: make local-llm-status"

local-llm-down:  ## stop the local LLM deploy stack
	-@pkill -f "mlx_lm.server" 2>/dev/null; true
	-@pkill -f "mlx_qwen_tool_proxy" 2>/dev/null; true
	-@pkill -f "uvicorn src.agents.ai.local_deploy_api" 2>/dev/null; true
	@echo "stopped local LLM deploy stack"

local-llm-status:  ## show local LLM deploy stack status
	@curl -s -m 3 localhost:$(MLX_PORT)/v1/models >/dev/null 2>&1 && echo "MLX-LM   :$(MLX_PORT)  up" || echo "MLX-LM   :$(MLX_PORT)  down"
	@curl -s -m 3 localhost:$(ROUTER_PORT)/health >/dev/null 2>&1 && echo "router   :$(ROUTER_PORT)   up" || echo "router   :$(ROUTER_PORT)   down"

dashboard-dev:  ## start the dashboard alone (next dev, foreground)
	cd $(DASHBOARD_DIR) && npm run dev

# ===== one-shot local dev stack (MLX + proxy + router + dashboard) =====
dev-up:  ## start the whole local stack in one command (reuses a warm MLX/proxy)
	@mkdir -p $(LLM_LOG_DIR)
	@if curl -s -m 3 localhost:$(MLX_PORT)/v1/models >/dev/null 2>&1; then \
		echo "→ MLX-LM   (:$(MLX_PORT)) already up — reusing"; \
	else \
		test -x $(MLX_BIN) || { $(MLX_MISSING); }; \
		echo "→ MLX-LM   (:$(MLX_PORT)) — model load takes ~30-60s"; \
		HF_HUB_DISABLE_XET=1 nohup .venv-mlx/bin/mlx_lm.server --model $(MLX_MODEL) --host 127.0.0.1 --port $(MLX_PORT) --max-tokens 1024 --prompt-cache-bytes 2147483648 > $(LLM_LOG_DIR)/mlx.log 2>&1 & \
	fi
	@if lsof -iTCP:$(PROXY_PORT) -sTCP:LISTEN -n -P >/dev/null 2>&1; then \
		echo "→ proxy    (:$(PROXY_PORT)) already up — reusing"; \
	else \
		echo "→ proxy    (:$(PROXY_PORT))"; \
		nohup python -m src.agents.ai.mlx_qwen_tool_proxy --upstream http://127.0.0.1:$(MLX_PORT) --host 127.0.0.1 --port $(PROXY_PORT) > $(LLM_LOG_DIR)/proxy.log 2>&1 & \
	fi
	@echo "→ router   (:$(ROUTER_PORT)) — restart, offline recording → $(ACTIVITY_FILE)"
	@pkill -f "uvicorn src.agents.ai.local_deploy_api" 2>/dev/null; true
	@cd $(DEPLOY_WORKDIR) && PYTHONPATH=$(CURDIR) PLATFORM_ACTIVITY_FILE=$(ACTIVITY_FILE) PLATFORM_PUSH_KEYS='$(PLATFORM_PUSH_KEYS)' ONPREM_LLM_ENDPOINT=http://127.0.0.1:$(PROXY_PORT)/v1 ONPREM_LLM_MODEL=$(MLX_MODEL) nohup uvicorn src.agents.ai.local_deploy_api:app --host 127.0.0.1 --port $(ROUTER_PORT) > $(LLM_LOG_DIR)/router.log 2>&1 &
	@echo "→ webhook  (:$(WEBHOOK_PORT)) — restart, On-Prem Day-2 (Alertmanager → pipeline → approval gate)"
	@pkill -f "uvicorn src.agents.ai.onprem_webhook_api" 2>/dev/null; true
	@PLATFORM_ACTIVITY_FILE=$(ACTIVITY_FILE) PLATFORM_APPROVALS_FILE=$(APPROVALS_FILE) PLATFORM_INCIDENT_FILE=$(INCIDENT_FILE) nohup uvicorn src.agents.ai.onprem_webhook_api:app --host 127.0.0.1 --port $(WEBHOOK_PORT) > $(LLM_LOG_DIR)/webhook.log 2>&1 &
	@echo "→ consoles  — port-forward the add-on UIs the dashboard links to"
	@$(MAKE) --no-print-directory stack-consoles
	@echo "→ dashboard(:$(DASHBOARD_PORT)) — restart (next dev)"
	@pkill -f "next-server" 2>/dev/null; pkill -f "next dev" 2>/dev/null; true
	@cd $(DASHBOARD_DIR) && $(CONSOLE_URLS) nohup npm run dev > $(LLM_LOG_DIR)/dashboard.log 2>&1 &
	@echo "→ status   — spoke agents push tenant status/isolation to the hub (60s loop)"
	@pkill -f "scripts/push_addon_status.py" 2>/dev/null; true
	@for t in $(PUSH_TENANTS); do \
		PLATFORM_PUSH_KEY=local-dev nohup python scripts/push_addon_status.py --tenant $$t --env dev --hub http://127.0.0.1:$(ROUTER_PORT) --interval 60 > $(LLM_LOG_DIR)/push-$$t.log 2>&1 & \
	done
	@echo ""
	@echo "stack starting → http://localhost:$(DASHBOARD_PORT)   (check: make dev-status | logs: $(LLM_LOG_DIR)/)"

dev-down:  ## stop the whole local stack (dashboard + webhook + consoles + MLX + proxy + router)
	-@pkill -f "next-server" 2>/dev/null; pkill -f "next dev" 2>/dev/null; true
	-@pkill -f "uvicorn src.agents.ai.onprem_webhook_api" 2>/dev/null; true
	-@pkill -f "scripts/push_addon_status.py" 2>/dev/null; true
	@$(MAKE) --no-print-directory stack-consoles-down
	@$(MAKE) local-llm-down
	@echo "stopped dashboard + webhook + consoles + pushers + local LLM deploy stack"

dev-status:  ## show the whole local stack status
	@curl -s -m 3 localhost:$(MLX_PORT)/v1/models >/dev/null 2>&1 && echo "MLX-LM    :$(MLX_PORT)  up" || echo "MLX-LM    :$(MLX_PORT)  down"
	@lsof -iTCP:$(PROXY_PORT) -sTCP:LISTEN -n -P >/dev/null 2>&1 && echo "proxy     :$(PROXY_PORT)  up" || echo "proxy     :$(PROXY_PORT)  down"
	@curl -s -m 3 localhost:$(ROUTER_PORT)/health >/dev/null 2>&1 && echo "router    :$(ROUTER_PORT)   up" || echo "router    :$(ROUTER_PORT)   down"
	@curl -s -m 3 localhost:$(WEBHOOK_PORT)/health >/dev/null 2>&1 && echo "webhook   :$(WEBHOOK_PORT)   up" || echo "webhook   :$(WEBHOOK_PORT)   down"
	@curl -s -m 3 localhost:$(DASHBOARD_PORT) >/dev/null 2>&1 && echo "dashboard :$(DASHBOARD_PORT)   up" || echo "dashboard :$(DASHBOARD_PORT)   down"

# ===== add-on console port-forwards =====
stack-consoles:  ## port-forward every add-on console the dashboard links to
	@mkdir -p $(LLM_LOG_DIR)
	@pkill -f "kubectl port-forward.*(argocd-server|monitoring-grafana|kube-prometheus-prometheus|kube-prometheus-alertmanager|argo-rollouts-dashboard)" 2>/dev/null; true
	@kubectl port-forward -n argocd svc/argocd-server $(ARGOCD_PORT):443 > $(LLM_LOG_DIR)/pf-argocd.log 2>&1 &
	@kubectl port-forward -n monitoring svc/monitoring-grafana $(GRAFANA_PORT):80 > $(LLM_LOG_DIR)/pf-grafana.log 2>&1 &
	@kubectl port-forward -n monitoring svc/monitoring-kube-prometheus-prometheus $(PROMETHEUS_PORT):9090 > $(LLM_LOG_DIR)/pf-prometheus.log 2>&1 &
	@kubectl port-forward -n monitoring svc/monitoring-kube-prometheus-alertmanager $(ALERTMANAGER_PORT):9093 > $(LLM_LOG_DIR)/pf-alertmanager.log 2>&1 &
	@kubectl port-forward -n argo-rollouts svc/argo-rollouts-dashboard $(ROLLOUTS_PORT):3100 > $(LLM_LOG_DIR)/pf-rollouts.log 2>&1 &
	@echo "consoles forwarding → argocd:$(ARGOCD_PORT) grafana:$(GRAFANA_PORT) prometheus:$(PROMETHEUS_PORT) alertmanager:$(ALERTMANAGER_PORT) rollouts:$(ROLLOUTS_PORT)"
	@echo "   (verify: make stack-consoles-status)"

stack-consoles-down:  ## stop the add-on console port-forwards
	-@pkill -f "kubectl port-forward.*(argocd-server|monitoring-grafana|kube-prometheus-prometheus|kube-prometheus-alertmanager|argo-rollouts-dashboard)" 2>/dev/null; true
	@echo "stopped console port-forwards"

stack-consoles-status:  ## are the dashboard's console links actually reachable?
	@for pair in "argocd https://localhost:$(ARGOCD_PORT)" "grafana http://localhost:$(GRAFANA_PORT)/login" \
	             "prometheus http://localhost:$(PROMETHEUS_PORT)/-/ready" "alertmanager http://localhost:$(ALERTMANAGER_PORT)/-/ready" \
	             "rollouts http://localhost:$(ROLLOUTS_PORT)/rollouts"; do \
		name=$${pair%% *}; url=$${pair#* }; \
		code=$$(curl -sk -m 4 -o /dev/null -w "%{http_code}" "$$url" 2>/dev/null); \
		case "$$code" in 2*|3*) echo "$$name  $$code  $$url";; *) echo "$$name  DEAD ($$code)  $$url";; esac; \
	done

# ===== demo baseline (CHANGES THE CLUSTER — kind only) =====
# Everything the isolation-falsification demo needs on screen, in one command:
# tenancy objects for both tenants, the tenant-scoped add-ons, and one forced push
# so the dashboard is current instead of up to 60s behind.
#
# Deliberately separate from dev-up: dev-up starts processes, this applies objects
# to a cluster. Running it against the wrong kubectl context is the failure worth
# making someone type a second command to avoid, so it prints the context first.
demo-baseline:  ## apply the demo's tenancy + tenant add-ons to the CURRENT kube context
	@echo "→ context: $$(kubectl config current-context)"
	@echo "→ tenancy (acme, globex)"
	@for t in $(PUSH_TENANTS); do \
		python scripts/render_tenancy.py $$t -e dev 2>/dev/null | kubectl apply -f - >/dev/null || exit 1; \
	done
	@echo "→ tenant-scoped add-ons (acme/dev)"
	@python scripts/render_addons.py acme -e dev 2>/dev/null | kubectl apply -f - >/dev/null
	@echo "→ waiting for Applications to report Healthy (ctrl-c is safe)"
	@until [ "$$(kubectl get app -n argocd acme-dev-logging -o jsonpath='{.status.health.status}' 2>/dev/null)" = "Healthy" ] \
	   && [ "$$(kubectl get app -n argocd acme-dev-tracing -o jsonpath='{.status.health.status}' 2>/dev/null)" = "Healthy" ]; do sleep 5; done
	@for t in $(PUSH_TENANTS); do \
		PLATFORM_PUSH_KEY=local-dev python scripts/push_addon_status.py --tenant $$t --env dev --hub http://127.0.0.1:$(ROUTER_PORT) --once; \
	done
	@echo "ready → http://localhost:$(DASHBOARD_PORT)/provisioning   (all four isolation axes should read enforced)"

# The identity a deploy runs as. Measured 2026-07-30: unset, deploys ran as the
# ambient context — cluster-admin on kind, i.e. every secret and every namespace, to
# roll out one service (docs/evidence/deploy-path-authorization.log).
#
# Separate from dev-up and NOT applied automatically: it creates cluster-scoped RBAC,
# and the repo's rule is that objects going onto a cluster are a command someone
# types. It also prints the context first, for the same reason demo-baseline does.
#
# This bounds WHAT a deploy can do, not WHOSE namespace it touches — that needs the
# request to name a tenant, which it does not (결정 5 C/D).
deploy-identity:  ## create + mint the restricted credential the deploy path should use
	@echo "→ context: $$(kubectl config current-context)"
	@python scripts/render_deploy_identity.py | kubectl apply -f -
	@bash scripts/mint_deploy_kubeconfig.sh
	@echo "→ export the variable above, then deploys stop running as cluster-admin"

# The two things the incident-scope broker needs before it can mint anything. Until
# 2026-07-31 nothing produced an attestation and nothing set these, so
# `guard_scoped_action` refused every live remediation — a gate that could not be
# opened (docs/evidence/deploy-path-authorization.log). The producer now exists
# (`attest_decision`); this is the other half.
#
# Local development only. The signing key is derived from the cluster name so a
# `make` run is reproducible, and it is NOT a secret-management story: in a real
# deployment both values come from a secret manager, and the key must be the same
# for whoever signs and whoever verifies. Keep them out of the repo.
#
# Rotating that key (2026-08-08). "The key must be the same for whoever signs and
# whoever verifies" used to mean it could not be rotated without an outage: the
# signer and the verifier are different processes, so the swap is never atomic and
# whichever rolled first produced records the other reported as `failed
# attestation` — i.e. as tampering. PLATFORM_APPROVAL_SIGNING_KEYS_RETIRING (comma
# separated) is verify-only: it never signs, and D42's TTL is what keeps the
# overlap bounded. The procedure, each step rolled everywhere before the next:
#   1. RETIRING=<current key>                       (accepts old + new)
#   2. SIGNING_KEY=<new key>, RETIRING=<old key>    (signs new, accepts old)
#   3. wait out PLATFORM_APPROVAL_TTL_SECONDS, unset RETIRING   (accepts new only)
# Step 3 is not optional and nothing enforces it — a listed key is valid for as
# long as it is listed. The broker logs `verified_under_retiring_key` for every
# record that lands on an old key, so step 3 is safe once that has gone quiet.
SCOPE_CREDENTIAL_DIR ?= $(HOME)/.platform-agent/credentials

scope-credentials:  ## mint per-tenant credentials + print the broker env for this shell
	@echo "→ context: $$(kubectl config current-context)"
	@for t in $(PUSH_TENANTS); do \
		PLATFORM_CREDENTIAL_DIR=$(SCOPE_CREDENTIAL_DIR) bash scripts/mint_tenant_kubeconfig.sh $$t -e dev || exit 1; \
	done
	@echo ""
	@echo "# eval these, then the incident path can actually mint a scope:"
	@echo "export PLATFORM_CREDENTIAL_DIR=$(SCOPE_CREDENTIAL_DIR)"
	@echo "export PLATFORM_APPROVAL_SIGNING_KEY=local-dev-$$(kubectl config current-context)"
	@echo ""
	@echo "# then verify it is actually reachable (it prints REFUSED when it is not):"
	@echo "python scripts/probe_scope_reachability.py"

spend-check:  ## what AWS/Azure are actually spending + whether GCP is readable (read-only)
	@# Every provider here had a default that answers a reassuring question instead of
	@# the one being asked. AWS: Cost Explorer nets out credits, so a credited account
	@# reads as $$0 while it consumes, and describe-instances is one region. Azure:
	@# `az consumption usage list` returns rows whose pretaxCost is null, so summing it
	@# gives 0 for a subscription that is spending — Cost Management is asked instead.
	@# GCP: there is no cost API at all, so it prints a state (is the BigQuery billing
	@# export on yet?) rather than a number. Saying nothing would read as zero.
	@python scripts/probe_cloud_spend.py

spend-watch:  ## has anything started costing money since the last look? (read-only)
	@# Budgets answer "how much", eventually — the AWS one worked, 18 days late. This
	@# answers "what is new", which is the shape every incident here has had. Exit 1 =
	@# something is charging that was not before, so it is usable as a cron signal.
	@# Deliberately no threshold: a rule you cannot satisfy teaches people to route
	@# around it, which is what the ₩20 budget cost us.
	python scripts/watch_cloud_spend.py

spend-watch-baseline:  ## accept the current spend as the new baseline (no report)
	python scripts/watch_cloud_spend.py --baseline

SPEND_WATCH_HOOK := $(HOME)/.zshrc

spend-watch-install:  ## run spend-watch once a day when a terminal opens (read-only)
	@# NOT launchd, and that is a finding rather than a preference: this repo lives
	@# under ~/Desktop, which macOS TCC protects. A LaunchAgent gets "Operation not
	@# permitted" reading the repo at all (measured — exit 127), and the only way
	@# through is granting Full Disk Access to /bin/zsh, which hands every zsh script
	@# on the machine the whole disk. An interactive shell already has the access it
	@# needs, so the check rides on the thing that is already permitted.
	@grep -q 'platform-agent spend-watch' $(SPEND_WATCH_HOOK) 2>/dev/null \
	  && { echo "already installed in $(SPEND_WATCH_HOOK)"; exit 0; } || true
	@printf '%s\n' \
	  '' \
	  '# >>> platform-agent spend-watch >>>' \
	  '# Once a day, ask whether anything started costing money. Silent unless it did.' \
	  '# Remove with: make spend-watch-uninstall (in $(CURDIR))' \
	  '(  _sw_stamp="$(CURDIR)/.state/last-watch"' \
	  '   if [ ! -f "$$_sw_stamp" ] || [ -z "$$(find "$$_sw_stamp" -mtime -1 2>/dev/null)" ]; then' \
	  '     mkdir -p "$(CURDIR)/.state" && touch "$$_sw_stamp"' \
	  '     ( "$(CURDIR)/scripts/spend_watch_launchd.sh" >/dev/null 2>&1 & ) ' \
	  '   fi ) 2>/dev/null' \
	  '# <<< platform-agent spend-watch <<<' >> $(SPEND_WATCH_HOOK)
	@echo "installed in $(SPEND_WATCH_HOOK) — 새 터미널에서 하루 한 번, 발견 시에만 알림"
	@$(MAKE) --no-print-directory spend-watch-status

spend-watch-uninstall:  ## remove the daily spend-watch hook
	@if grep -q 'platform-agent spend-watch' $(SPEND_WATCH_HOOK) 2>/dev/null; then \
	  sed -i '' '/# >>> platform-agent spend-watch >>>/,/# <<< platform-agent spend-watch <<</d' $(SPEND_WATCH_HOOK); \
	  echo "removed from $(SPEND_WATCH_HOOK)"; \
	else echo "not installed"; fi

spend-watch-status:  ## is the daily spend-watch hook installed, and when did it last run?
	@grep -q 'platform-agent spend-watch' $(SPEND_WATCH_HOOK) 2>/dev/null \
	  && echo "spend-watch: 설치됨 ($(SPEND_WATCH_HOOK))" \
	  || echo "spend-watch: 설치 안 됨 — 'make spend-watch-install'"
	@test -f $(CURDIR)/.state/last-watch \
	  && echo "  마지막 실행: $$(date -r $(CURDIR)/.state/last-watch '+%Y-%m-%d %H:%M')" \
	  || echo "  마지막 실행: 없음"

deploy-identity-check:  ## show what the minted deploy credential can and cannot do
	@test -n "$$PLATFORM_DEPLOY_KUBECONFIG" || { echo "PLATFORM_DEPLOY_KUBECONFIG is not set → deploys run AMBIENT (likely cluster-admin)"; exit 1; }
	@echo "→ identity: $$(kubectl --kubeconfig $$PLATFORM_DEPLOY_KUBECONFIG auth whoami -o jsonpath='{.status.userInfo.username}')"
	@for q in "get secrets -A" "delete namespaces -A" "create clusterrolebindings" "create deployments -A" "patch deployments -A"; do \
		printf "   can-i %-30s : %s\n" "$$q" "$$(kubectl --kubeconfig $$PLATFORM_DEPLOY_KUBECONFIG auth can-i $$q 2>&1 | tail -1)"; \
	done

.PHONY: mlx-serve mlx-proxy router-api onprem-webhook local-llm-up local-llm-down local-llm-status dashboard-dev dev-up dev-down dev-status demo-baseline deploy-identity deploy-identity-check scope-credentials stack-consoles stack-consoles-down stack-consoles-status

# ===== overnight harness targets (append to your Makefile) =====
# The overnight runner + helpers are the Single Source of Truth in the overnight-harness
# PLUGIN; this repo does NOT vendor them. These targets resolve the installed plugin at
# runtime and invoke its runner against THIS repo. Per-repo STATE stays here:
#   scripts/overnight/overnight-settings.json  — Claude permission boundary
#   scripts/overnight/opencode.json            — opencode permission boundary
#   .codex/rules/overnight.rules               — Codex command rules
#   scripts/overnight/PROMPT.md                — optional per-repo prompt override (else plugin default)
#   scripts/overnight/{logs,STOP,DONE}         — runtime state
#   docs/LESSONS.md                            — the actor's memory surface (committed)
#
# The loop's commit gate is $GATE_CMD (default `make check`). Define a `check` target that proves
# correctness OFFLINE + DETERMINISTICALLY and allow-list it in scripts/overnight/overnight-settings.json.
#
# Select the engine with ENGINE=claude|codex|opencode|agy|kiro. Default stays Claude.
ENGINE ?= claude

# Model routing (1.4.0, Claude engine). The actor does bounded implementation; the critic is a
# read-only reviewer whose judgment is what you pay for. Blank = the CLI's own default. These
# are per-repo policy, so edit them here rather than in the plugin.
CLAUDE_MODEL ?= claude-sonnet-5
CLAUDE_EFFORT ?=
OVERNIGHT_CRITIC_MODEL ?= claude-fable-5-1
CLAUDE_CRITIC_EFFORT ?=
export CLAUDE_MODEL CLAUDE_EFFORT OVERNIGHT_CRITIC_MODEL CLAUDE_CRITIC_EFFORT

# HARNESS_ROOT resolution (env override → per-repo pin → highest installed version). This mirrors
# the plugin's bin/harness-locate.sh; override ad hoc with `make overnight HARNESS_ROOT=/path`.
HARNESS_ROOT ?= $(shell \
  if [ -n "$$OVERNIGHT_HARNESS_ROOT" ] && [ -d "$$OVERNIGHT_HARNESS_ROOT/templates/scripts/overnight" ]; then \
    echo "$$OVERNIGHT_HARNESS_ROOT"; \
  elif [ -n "$$OVERNIGHT_HARNESS_ROOT" ] && [ -d "$$OVERNIGHT_HARNESS_ROOT/plugins/overnight-harness/templates/scripts/overnight" ]; then \
    echo "$$OVERNIGHT_HARNESS_ROOT/plugins/overnight-harness"; \
  elif [ -f .claude/harness-config.json ] && grep -q '"harness_root"' .claude/harness-config.json; then \
    pin="$$(sed -n 's/.*"harness_root"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' .claude/harness-config.json | head -1)"; \
    if [ -d "$$pin/templates/scripts/overnight" ]; then echo "$$pin"; \
    elif [ -d "$$pin/plugins/overnight-harness/templates/scripts/overnight" ]; then echo "$$pin/plugins/overnight-harness"; fi; \
  else \
    { \
      ls -d $$HOME/.claude/plugins/cache/overnight-harness/overnight-harness/*/ 2>/dev/null; \
      find $$HOME/.codex/plugins/cache -path '*/overnight-harness/*' -type d 2>/dev/null; \
      [ -d $$HOME/.gemini/antigravity-cli/plugins/overnight-harness ] && echo $$HOME/.gemini/antigravity-cli/plugins/overnight-harness; \
      [ -d $$HOME/.cache/opencode/node_modules/opencode-overnight-harness ] && echo $$HOME/.cache/opencode/node_modules/opencode-overnight-harness; \
    } | while read d; do [ -d "$$d/templates/scripts/overnight" ] && echo "$$d"; done | sort -V | tail -1; \
  fi)

# OVN_SRC = runner + helpers (in the plugin); OVN = per-repo state (in this repo).
# NB: no inline comments on these := lines — make would fold the gap into the value.
OVN_SRC := $(HARNESS_ROOT:%/=%)/templates/scripts/overnight
OVN := scripts/overnight

_harness-guard:
	@test -x "$(OVN_SRC)/run.sh" || { \
	  echo "overnight-harness not found (resolved HARNESS_ROOT='$(HARNESS_ROOT)')."; \
	  echo "Install the plugin, or pass HARNESS_ROOT=/path/to/plugin, or re-run /harness-init."; \
	  exit 1; }

overnight: _harness-guard           ## run the unattended loop (caffeinate keeps macOS awake)
	OVERNIGHT_ENGINE=$(ENGINE) caffeinate -dimsu $(OVN_SRC)/run.sh &
overnight-watch: overnight          ## start the loop and tail its log
	@sleep 1; tail -f $(OVN)/logs/runner.log
overnight-once: _harness-guard      ## single iteration (smoke test the loop)
	OVERNIGHT_ENGINE=$(ENGINE) $(OVN_SRC)/run.sh --once
overnight-claude-once: _harness-guard
	OVERNIGHT_ENGINE=claude $(OVN_SRC)/run.sh --once
overnight-codex-once: _harness-guard
	OVERNIGHT_ENGINE=codex $(OVN_SRC)/run.sh --once
overnight-opencode-once: _harness-guard
	OVERNIGHT_ENGINE=opencode $(OVN_SRC)/run.sh --once
overnight-agy-once: _harness-guard
	OVERNIGHT_ENGINE=agy $(OVN_SRC)/run.sh --once
overnight-kiro-once: _harness-guard
	OVERNIGHT_ENGINE=kiro $(OVN_SRC)/run.sh --once
overnight-stop:                     ## graceful stop after the current iteration
	@touch $(OVN)/STOP && echo "STOP created — loop will exit after current iteration"
overnight-clean:                    ## clear STOP/DONE sentinels before the next run
	@rm -f $(OVN)/STOP $(OVN)/DONE && echo "cleared STOP/DONE"
overnight-status: _harness-guard    ## aggregate iteration status across lanes
	@bash $(OVN_SRC)/status.sh
overnight-logs:                     ## tail the runner log
	@mkdir -p $(OVN)/logs; touch $(OVN)/logs/runner.log; tail -f $(OVN)/logs/runner.log
overnight-dashboard: _harness-guard ## tmux dashboard (falls back to status.sh)
	@bash $(OVN_SRC)/dashboard.sh
overnight-ledger-check: _harness-guard ## validate event history before trusting status/report
	@python3 $(OVN_SRC)/lib/ledger.py check $(OVN)/logs/events.jsonl
overnight-ledger-state: _harness-guard ## project deterministic per-mission state as JSON
	@python3 $(OVN_SRC)/lib/ledger.py project $(OVN)/logs/events.jsonl
overnight-trajectory: _harness-guard ## render causal node/edge trajectory; optional MISSION and FORMAT=json
	@python3 $(OVN_SRC)/lib/trajectory.py $(OVN)/logs/events.jsonl \
	  $(if $(MISSION),--mission "$(MISSION)",) --format "$(or $(FORMAT),text)"
overnight-resume: _harness-guard       ## resume MISSION with DECISION=approve|reject
	@test -x "$(OVN_SRC)/resume.sh" || { echo "installed overnight-harness does not provide resume.sh"; exit 1; }
	@test -n "$(MISSION)" || { echo "MISSION=<mission-id> is required"; exit 2; }
	@test "$(DECISION)" = "approve" -o "$(DECISION)" = "reject" || { echo "DECISION=approve|reject is required"; exit 2; }
	@HARNESS_REPO_ROOT="$(CURDIR)" bash $(OVN_SRC)/resume.sh "$(MISSION)" --"$(DECISION)"
overnight-provenance-compare: _harness-guard ## compare two manifests; optional LEFT_RESULT/RIGHT_RESULT
	@test -n "$(LEFT)" -a -n "$(RIGHT)" || { echo "LEFT=<manifest> and RIGHT=<manifest> are required"; exit 2; }
	@python3 $(OVN_SRC)/lib/provenance.py compare --left "$(LEFT)" --right "$(RIGHT)" \
	  --left-result "$(LEFT_RESULT)" --right-result "$(RIGHT_RESULT)"
overnight-where:                    ## print the resolved plugin location (debug)
	@echo "HARNESS_ROOT = $(HARNESS_ROOT)"; echo "runner       = $(OVN_SRC)/run.sh"

.PHONY: overnight overnight-watch overnight-once overnight-claude-once overnight-codex-once overnight-opencode-once overnight-agy-once overnight-kiro-once overnight-stop overnight-clean overnight-status overnight-logs overnight-dashboard overnight-ledger-check overnight-ledger-state overnight-trajectory overnight-resume overnight-provenance-compare overnight-where _harness-guard
# ===== end overnight harness targets =====
