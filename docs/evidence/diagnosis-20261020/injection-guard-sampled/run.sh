#!/bin/zsh
# usage: run.sh ARM   restart the sampler-intervention server, then all cases x seeds for ARM
cd /Users/men1692/Desktop/AWS/platform-agent
W=_workspace/diagnosis-20261020; E=docs/evidence/diagnosis-20261020/injection-guard-sampled
M=experiments.dogfood-diagnosis.consistency-resume.injection_guard_sampled
kill $(lsof -tiTCP:18192 -sTCP:LISTEN) 2>/dev/null; sleep 4
HF_HUB_CACHE=$PWD/$W/hf-hub HF_HUB_OFFLINE=1 nohup .venv-mlx/bin/python docs/evidence/diagnosis-20261020/sampler-boundary/patched_server.py --model mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit --host 127.0.0.1 --port 18192 --max-tokens 1024 --prompt-cache-bytes 2147483648 > $E/mlx-patched-$1.log 2>&1 &
for i in $(seq 1 80); do curl -sf http://127.0.0.1:18192/v1/models >/dev/null && break; sleep 3; done
lsof -tiTCP:18193 -sTCP:LISTEN >/dev/null || { nohup /opt/anaconda3/bin/python -u -m src.agents.ai.mlx_qwen_tool_proxy --upstream http://127.0.0.1:18192 --host 127.0.0.1 --port 18193 > $E/proxy.log 2>&1 & sleep 2; }
/opt/anaconda3/bin/python -m $M $1
