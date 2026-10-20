"""Derived re-run of snapshot_temperature.py against the sampler-intervention server.

Only differences: base_url -> proxy 18193 whose upstream 18192 runs mlx_lm 0.31.3 with categorical_sampling
replaced by an uncompiled per-thread RNG call (_workspace/diagnosis-20261020/sampler-boundary/patched_server.py),
and the output folder. Inputs, prompt/schema, seeds, temperatures, budgets are identical.

All predeclared seeds and outputs are retained. Explicit seeds select MLX's
non-batch generation path in both arms. Not a same-path repeat of unseeded runs,
not an accuracy estimate, and never best-of-N or an automatic setting change.
"""
import asyncio
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

import httpx
from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.profiles.openai import OpenAIModelProfile
from pydantic_ai.providers.openai import OpenAIProvider

from src.agents.ai.local_deployer import create_local_deployer
from src.agents.ai.model_router import route_deploy

ROOT=Path(__file__).resolve().parents[3]
SEEDS=(42,31415,27182)
TEMPERATURES=(0,0.7)
IDS=('lookalike','counterexample','supported-recovery')


async def main():
    out=ROOT/'docs/evidence/diagnosis-20261020/snapshot-temperature-sampler'
    out.mkdir(exist_ok=False)
    cases={c['id']:c for c in json.loads((ROOT/'experiments/dogfood-diagnosis/cases.json').read_text())}
    sources=['src/agents/ai/snapshot_diagnosis.py','src/agents/ai/local_deployer.py',
             'src/agents/ai/model_router.py','src/agents/ai/mlx_qwen_tool_proxy.py',str(Path(__file__).relative_to(ROOT))]
    manifest={'at':datetime.now(timezone.utc).isoformat(),'model_revision':'6e302ea604ad9ab206367e2c501d1571023e7b6d',
        'seeds':SEEDS,'temperatures':TEMPERATURES,'case_ids':IDS,'max_tokens':1024,'request_limit':1,
        'tools':0,'retries':0,'top_p':1,'top_k':0,'repetition_penalty':0,
        'scope':__doc__,'reference':'https://huggingface.co/Qwen/Qwen3-Coder-30B-A3B-Instruct',
        'source_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    attempts=[]
    async def requested(request):
        request.extensions['attempt_index']=len(attempts)
        attempts.append({'request':json.loads(request.content),'at':datetime.now(timezone.utc).isoformat()})
    async def responded(response):
        attempts[response.request.extensions['attempt_index']]['status']=response.status_code
    client=AsyncOpenAI(base_url='http://127.0.0.1:18193/v1',api_key='mlx-local',max_retries=0,
        http_client=httpx.AsyncClient(timeout=120,event_hooks={'request':[requested],'response':[responded]}))
    model=OpenAIChatModel('mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit',provider=OpenAIProvider(openai_client=client),
        profile=OpenAIModelProfile(openai_chat_supports_multiple_system_messages=False))
    try:
        for cid in IDS:
            q=cases[cid]['input']
            for seed in SEEDS:
                for temperature in TEMPERATURES:
                    settings={'max_tokens':1024,'temperature':temperature,'top_p':1,
                              'extra_body':{'seed':seed,'top_k':0,'repetition_penalty':0}}
                    factory=lambda **kwargs:create_local_deployer(model=model,model_settings=settings,retries=0,**kwargs)
                    first=len(attempts);start=time.monotonic()
                    result=await route_deploy(q['question'],'local-qwen','onprem',read_only=True,snapshot=q,agent_factory=factory)
                    row={'case_id':cid,'seed':seed,'temperature':temperature,'input':q,
                         'settings':settings,'seconds':round(time.monotonic()-start,3),
                         'http_attempts':attempts[first:],'outcome':asdict(result)}
                    (out/f'{cid}-{seed}-{temperature}.json').write_text(json.dumps(row,ensure_ascii=False,indent=2)+'\n')
                    report=result.snapshot_analysis;c=result.model_completion or {}
                    print(json.dumps({'case':cid,'seed':seed,'temperature':temperature,'seconds':row['seconds'],
                          'completion':c.get('status'),'citation':report['citation_status'],
                          'recovery':(report['diagnosis'] or {}).get('recovery')},ensure_ascii=False),flush=True)
                    if c.get('model_responses')!=1:
                        raise RuntimeError('Unexpected request completion; preserve and investigate before further measurements')
    finally:
        await client.close()


if __name__=='__main__':
    asyncio.run(main())
