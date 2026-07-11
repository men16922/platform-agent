# platform-agent Makefile
.DEFAULT_GOAL := help

# ===== Project targets =====

.PHONY: help install test check lint synth

help:  ## show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

install:  ## install Python deps (editable + dev)
	pip install -e ".[dev]"

test:  ## run pytest
	python -m pytest tests/ -v

check: test  ## gate command (overnight harness uses this)

lint:  ## run ruff
	ruff check src/ tests/

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

.PHONY: local-cluster local-cluster-down local-cluster-status

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

mlx-serve:  ## start local MLX-LM server (run in its own terminal)
	HF_HUB_DISABLE_XET=1 .venv-mlx/bin/mlx_lm.server --model $(MLX_MODEL) --host 127.0.0.1 --port $(MLX_PORT) --max-tokens 1024 --prompt-cache-bytes 2147483648

mlx-proxy:  ## start the MLX Qwen tool-call proxy
	python -m src.agents.ai.mlx_qwen_tool_proxy --upstream http://127.0.0.1:$(MLX_PORT) --host 127.0.0.1 --port $(PROXY_PORT)

router-api:  ## start the AI Model Router API (natural-language deploy)
	cd $(DEPLOY_WORKDIR) && PYTHONPATH=$(CURDIR) ONPREM_LLM_ENDPOINT=http://127.0.0.1:$(PROXY_PORT)/v1 ONPREM_LLM_MODEL=$(MLX_MODEL) uvicorn src.agents.ai.local_deploy_api:app --host 127.0.0.1 --port $(ROUTER_PORT)

local-llm-up:  ## start MLX + proxy + router API in the background (logs in /tmp/platform-agent)
	@mkdir -p $(LLM_LOG_DIR)
	@echo "→ MLX-LM server (:$(MLX_PORT)) — model load takes ~30-60s"
	@HF_HUB_DISABLE_XET=1 nohup .venv-mlx/bin/mlx_lm.server --model $(MLX_MODEL) --host 127.0.0.1 --port $(MLX_PORT) --max-tokens 1024 --prompt-cache-bytes 2147483648 > $(LLM_LOG_DIR)/mlx.log 2>&1 &
	@echo "→ tool-call proxy (:$(PROXY_PORT))"
	@nohup python -m src.agents.ai.mlx_qwen_tool_proxy --upstream http://127.0.0.1:$(MLX_PORT) --host 127.0.0.1 --port $(PROXY_PORT) > $(LLM_LOG_DIR)/proxy.log 2>&1 &
	@echo "→ router API (:$(ROUTER_PORT), workdir=$(DEPLOY_WORKDIR)) — set PLATFORM_ACTIVITY_TABLE+AWS_REGION to record into Deployments"
	@cd $(DEPLOY_WORKDIR) && PYTHONPATH=$(CURDIR) ONPREM_LLM_ENDPOINT=http://127.0.0.1:$(PROXY_PORT)/v1 ONPREM_LLM_MODEL=$(MLX_MODEL) nohup uvicorn src.agents.ai.local_deploy_api:app --host 127.0.0.1 --port $(ROUTER_PORT) > $(LLM_LOG_DIR)/router.log 2>&1 &
	@echo "stack starting. Watch: tail -f $(LLM_LOG_DIR)/mlx.log | check: make local-llm-status"

local-llm-down:  ## stop the local LLM deploy stack
	-@pkill -f "mlx_lm.server" 2>/dev/null; true
	-@pkill -f "mlx_qwen_tool_proxy" 2>/dev/null; true
	-@pkill -f "uvicorn src.agents.ai.local_deploy_api" 2>/dev/null; true
	@echo "stopped local LLM deploy stack"

local-llm-status:  ## show local LLM deploy stack status
	@curl -s -m 3 localhost:$(MLX_PORT)/v1/models >/dev/null 2>&1 && echo "MLX-LM   :$(MLX_PORT)  up" || echo "MLX-LM   :$(MLX_PORT)  down"
	@curl -s -m 3 localhost:$(ROUTER_PORT)/health >/dev/null 2>&1 && echo "router   :$(ROUTER_PORT)   up" || echo "router   :$(ROUTER_PORT)   down"

.PHONY: mlx-serve mlx-proxy router-api local-llm-up local-llm-down local-llm-status

# ===== overnight harness targets (append to your Makefile) =====
# The overnight runner + helpers are the Single Source of Truth in the overnight-harness
# PLUGIN; this repo does NOT vendor them. These targets resolve the installed plugin at
# runtime and invoke its runner against THIS repo. Per-repo STATE stays here:
#   scripts/overnight/overnight-settings.json  — Claude permission boundary
#   scripts/overnight/opencode.json            — opencode permission boundary
#   .codex/rules/overnight.rules               — Codex command rules
#   scripts/overnight/PROMPT.md                — optional per-repo prompt override (else plugin default)
#   scripts/overnight/{logs,STOP,DONE}         — runtime state
#
# The loop's commit gate is $GATE_CMD (default `make check`). Define a `check` target that proves
# correctness OFFLINE + DETERMINISTICALLY and allow-list it in scripts/overnight/overnight-settings.json.
#
# Select the engine with ENGINE=claude|codex|opencode|agy|kiro. Default stays Claude.
ENGINE ?= claude

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
overnight-where:                    ## print the resolved plugin location (debug)
	@echo "HARNESS_ROOT = $(HARNESS_ROOT)"; echo "runner       = $(OVN_SRC)/run.sh"

.PHONY: overnight overnight-watch overnight-once overnight-claude-once overnight-codex-once overnight-opencode-once overnight-agy-once overnight-kiro-once overnight-stop overnight-clean overnight-status overnight-logs overnight-dashboard overnight-where _harness-guard
# ===== end overnight harness targets =====
