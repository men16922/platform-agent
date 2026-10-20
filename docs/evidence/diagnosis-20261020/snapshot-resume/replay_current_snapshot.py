import asyncio
import json
import time
import hashlib
from pathlib import Path
from dataclasses import asdict
from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.profiles.openai import OpenAIModelProfile
from pydantic_ai.providers.openai import OpenAIProvider
from src.agents.ai.local_deployer import create_local_deployer
from src.agents.ai.model_router import route_deploy
async def main():
 out=Path('docs/evidence/diagnosis-20261020/snapshot-resume');out.mkdir(exist_ok=False)
 cases=json.loads(Path('experiments/dogfood-diagnosis/cases.json').read_text());(out/'cases.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2)+'\n')
 client=AsyncOpenAI(base_url='http://127.0.0.1:18191/v1',api_key='mlx-local',max_retries=0,timeout=120)
 model=OpenAIChatModel('mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit',provider=OpenAIProvider(openai_client=client),profile=OpenAIModelProfile(openai_chat_supports_multiple_system_messages=False))
 factory=lambda **kwargs:create_local_deployer(model=model,model_settings={'max_tokens':1024,'temperature':0},retries=0,**kwargs)
 try:
  for case in cases:
   q=case['input'];start=time.monotonic()
   outcome=await route_deploy(q['question'],'local-qwen','onprem',read_only=True,snapshot=q,agent_factory=factory)
   row={'case_id':case['id'],'request':q,'outcome':asdict(outcome),'seconds':round(time.monotonic()-start,3)}
   (out/(case['id']+'.json')).write_text(json.dumps(row,ensure_ascii=False,indent=2)+'\n')
   report=outcome.snapshot_analysis
   print(json.dumps({'case_id':case['id'],'status':report['status'],'model_called':report['model_called'],'diagnosis':report['diagnosis'],'raw':(outcome.model_completion or {}).get('text')},ensure_ascii=False),flush=True)
 finally:await client.close()
 (out/'manifest.json').write_text(json.dumps({'model_revision':'6e302ea604ad9ab206367e2c501d1571023e7b6d','max_tokens':1024,'temperature':0,'http_request_limit':1,'tools':0,'retries':0,'scope':'Current production supplied-text snapshot path, exact original seven fixtures; no cluster calls. Revalidation, not a modified candidate.','source_hashes':{p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in ['src/agents/ai/snapshot_diagnosis.py','src/agents/ai/local_deployer.py','src/agents/ai/model_router.py']}},indent=2)+'\n')
asyncio.run(main())
