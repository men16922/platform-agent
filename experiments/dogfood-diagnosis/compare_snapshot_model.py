"""One bounded local-cache comparison through the production snapshot factory."""
import argparse
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


async def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('output',type=Path)
    parser.add_argument('--model',choices=['mlx-community/Qwen3.8-27B-4bit','mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit'],required=True)
    parser.add_argument('--disable-thinking',action='store_true')
    args=parser.parse_args();args.output.mkdir(exist_ok=False)
    root=Path(__file__).resolve().parents[2]
    case_file=root/'docs/evidence/dogfood-20261003/repeats/r4-snapshot-ui/cases.json'
    cases={c['id']:c for c in json.loads(case_file.read_text())}
    attempts=[]
    async def request(request):
        request.extensions['comparison_attempt']=len(attempts)
        attempts.append({'started_at':datetime.now(timezone.utc).isoformat(),'status':None})
    async def response(response):attempts[response.request.extensions['comparison_attempt']]['status']=response.status_code
    client=AsyncOpenAI(base_url='http://127.0.0.1:18091/v1',api_key='mlx-local',max_retries=0,
        http_client=httpx.AsyncClient(timeout=httpx.Timeout(90,connect=5),event_hooks={'request':[request],'response':[response]}))
    model=OpenAIChatModel(args.model,provider=OpenAIProvider(openai_client=client),
        profile=OpenAIModelProfile(openai_chat_supports_multiple_system_messages=False))
    settings={'max_tokens':1024}
    if args.disable_thinking:settings['extra_body']={'chat_template_kwargs':{'enable_thinking':False}}
    factory=lambda **kwargs:create_local_deployer(model=model,model_settings=settings,**kwargs)
    files=[case_file,Path(__file__),root/'src/agents/ai/snapshot_diagnosis.py',root/'src/agents/ai/local_deployer.py',root/'src/agents/ai/model_router.py']
    manifest={'at':datetime.now(timezone.utc).isoformat(),'candidate':'candidate-v15-snapshot-contract.json','model':args.model,
              'case_ids':['counterexample','lookalike','supported-recovery'],'settings':settings,'timeout_seconds':90,'sdk_http_retries':0,
              'path':'route_deploy(snapshot=...) -> current snapshot factory; no tools; direct local test, not browser',
              'files':{str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
              'limits':'Same cases/factory, changed model and explicit no-thinking setting. Not general accuracy/latency; no automatic model replacement.'}
    (args.output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    for path in files:(args.output/path.name).write_bytes(path.read_bytes())
    try:
        for cid in manifest['case_ids']:
            case=cases[cid];start=time.monotonic();first=len(attempts)
            outcome=await route_deploy(case['input']['question'],'local-qwen','onprem',read_only=True,snapshot=case['input'],agent_factory=factory)
            data={'case_id':cid,'request':case['input'],'outcome':asdict(outcome),'elapsed_sec':round(time.monotonic()-start,3),
                  'http_attempts':attempts[first:],'http_attempt_count':len(attempts)-first}
            (args.output/f'{cid}.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
            report=outcome.snapshot_analysis;completion=outcome.model_completion or {}
            print(json.dumps({'case_id':cid,'status':report['status'],'model_responses':completion.get('model_responses'),
                              'finish_reason':completion.get('finish_reason'),'http_attempts':data['http_attempt_count'],'elapsed_sec':data['elapsed_sec'],
                              'diagnosis':report.get('diagnosis'),'error':report.get('error')},ensure_ascii=False),flush=True)
            if not completion.get('model_responses'):
                print('No completed model response: stop bounded comparison; inspect/restore owned server.',flush=True)
                break
    finally:await client.close()


if __name__=='__main__':asyncio.run(main())
