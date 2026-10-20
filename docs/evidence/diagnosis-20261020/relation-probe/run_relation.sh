#!/bin/zsh
# usage: run.sh ARM MODE   MODE=cold (restart per case) | warm (one restart, all cases in sequence)
cd /Users/men1692/Desktop/AWS/platform-agent
W=_workspace/diagnosis-20261020; M=experiments.dogfood-diagnosis.consistency-resume.relation_probe
CASES=(lookalike relation-same relation-different counterexample supported-recovery)
restart(){ kill $(lsof -tiTCP:18190 -sTCP:LISTEN) 2>/dev/null; sleep 4
 HF_HUB_CACHE=$PWD/$W/hf-hub HF_HUB_OFFLINE=1 nohup .venv-mlx/bin/mlx_lm.server --model mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit --host 127.0.0.1 --port 18190 --max-tokens 1024 --prompt-cache-bytes 2147483648 > $W/relation-probe/mlx-$1.log 2>&1 &
 for i in $(seq 1 80); do curl -sf http://127.0.0.1:18190/v1/models >/dev/null && break; sleep 3; done; }
lsof -tiTCP:18191 -sTCP:LISTEN >/dev/null || { nohup /opt/anaconda3/bin/python -u -m src.agents.ai.mlx_qwen_tool_proxy --upstream http://127.0.0.1:18190 --host 127.0.0.1 --port 18191 > $W/relation-probe/proxy.log 2>&1 & sleep 2; }
if [[ $2 == cold ]]; then for c in $CASES; do restart $1-cold-$c; /opt/anaconda3/bin/python -m $M $1 $c cold; done
else restart $1-warm; /opt/anaconda3/bin/python -m $M $1 ${(j:,:)CASES} warm; fi
