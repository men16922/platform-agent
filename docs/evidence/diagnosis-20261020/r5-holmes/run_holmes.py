"""R5: HolmesGPT 0.43.0 on the 7 original supplied snapshots, same local Qwen via proxy 18191, all toolsets disabled."""
import json, os, subprocess, sys, time, hashlib
from pathlib import Path
ROOT = Path.cwd(); R = ROOT / '_workspace/r5-holmes'; OUT = ROOT / 'docs/evidence/diagnosis-20261020/r5-holmes'
cases = json.loads((ROOT / 'experiments/dogfood-diagnosis/cases.json').read_text())
env = {**os.environ, 'OPENAI_API_BASE': 'http://127.0.0.1:18191/v1', 'OPENAI_API_KEY': 'mlx-local',
       'LITELLM_LOCAL_MODEL_COST_MAP': 'True', 'KUBECONFIG': '/nonexistent', 'SENTRY_DSN': '', 'OVERRIDE_MAX_OUTPUT_TOKEN': '1024'}
for c in cases:
    q = c['input']
    prompt = (q['question'] + '\n\nSupplied snapshot (records supplied by the caller with target and observation-time metadata; '
              'not live observations; no actions are possible):\n' + json.dumps(q, ensure_ascii=False, indent=1))
    pf = R / f"prompt-{c['id']}.txt"; pf.write_text(prompt)
    jf = OUT / f"{c['id']}.json"
    start = time.monotonic()
    p = subprocess.run([str(R / 'venv/bin/holmes'), 'ask', '--prompt-file', str(pf), '--model', 'openai/mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit',
                        '--config', str(R / 'config.yaml'), '--no-interactive', '--max-steps', '2', '--json-output-file', str(jf)],
                       capture_output=True, text=True, env=env, timeout=600, stdin=subprocess.DEVNULL)
    row = {'case_id': c['id'], 'seconds': round(time.monotonic() - start, 2), 'returncode': p.returncode,
           'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest(), 'stdout_tail': p.stdout[-4000:], 'stderr_tail': p.stderr[-1500:]}
    (OUT / f"{c['id']}-run.json").write_text(json.dumps(row, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: row[k] for k in ('case_id', 'seconds', 'returncode')}), flush=True)
