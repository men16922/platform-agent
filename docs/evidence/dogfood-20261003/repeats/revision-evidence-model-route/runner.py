import asyncio
import json
import time
from pathlib import Path
from datetime import datetime,timezone
import httpx
from openai import AsyncOpenAI
from pydantic_ai import Agent,capture_run_messages
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.messages import ModelMessagesTypeAdapter
from pydantic_ai.usage import UsageLimits
from src.agents.ai.model_router import route_deploy
from src.agents.ai.local_deployer import DEPLOYER_SYSTEM_PROMPT
from src.agents.ai.ops_tools import describe_deployment
from dataclasses import asdict

async def main():
 out=Path('docs/evidence/dogfood-20261003/repeats/revision-evidence-model-route');out.mkdir(exist_ok=False)
 attempts=[]
 async def on_request(request):
  request.extensions['probe_index']=len(attempts);attempts.append({'at':datetime.now(timezone.utc).isoformat(),'status':None})
 async def on_response(response): attempts[response.request.extensions['probe_index']]['status']=response.status_code
 client=AsyncOpenAI(base_url='http://127.0.0.1:18091/v1',api_key='mlx-local',max_retries=0,http_client=httpx.AsyncClient(timeout=60,event_hooks={'request':[on_request],'response':[on_response]}))
 model=OpenAIChatModel('mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit',provider=OpenAIProvider(openai_client=client))
 agent=Agent(model,system_prompt=DEPLOYER_SYSTEM_PROMPT,tools=[describe_deployment],model_settings={'max_tokens':1024},retries=0)
 usage=None
 class Bounded:
  async def run(self,instruction):
   nonlocal usage
   result=await agent.run(instruction,usage_limits=UsageLimits(request_limit=2,tool_calls_limit=1));usage=result.usage();return result
 instruction='Inspect deployment orders-api-dogfood in namespace acme-dev-observability using describe_deployment exactly once. Make no changes. Report the current revision and rollout result, what health is actually established, whether rollback is a review candidate and why. Preserve the structured recovery assessment and its limitations. A completed rollout does not prove external application health.'
 start=time.monotonic()
 report={'at':datetime.now(timezone.utc).isoformat(),'instruction':instruction,'candidate':'candidate-v11-revision-evidence.json','method':'Actual route_deploy with bounded agent_factory: product prompt and describe_deployment only. Persistent router and default all-tool factory are not this run.','registered_tools':['describe_deployment'],'mutation_tools':0,'request_limit':2,'tool_calls_limit':1,'sdk_retries':0}
 with capture_run_messages() as messages:
  try:
   outcome=await asyncio.wait_for(route_deploy(instruction,'local-qwen','onprem',agent_factory=lambda **_:Bounded()),timeout=60)
   report['outcome']=asdict(outcome)
  except Exception as exc: report['error']={'type':type(exc).__name__,'message':str(exc)}
 report.update(elapsed_sec=round(time.monotonic()-start,3),http_attempts=attempts,messages=json.loads(ModelMessagesTypeAdapter.dump_json(messages)),usage=asdict(usage) if usage else None)
 (out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
 (out/'runner.py').write_bytes(Path(__file__).read_bytes())
 await client.close()
 print(json.dumps({k:v for k,v in report.items() if k in ['elapsed_sec','http_attempts','usage','error']},indent=2))
 print(report.get('outcome',{}).get('summary','No summary'))
asyncio.run(main())
