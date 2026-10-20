"""Task-owned loopback API (copy of live_readonly_scoped_api.py): measures get_logs(previous) selection on the restarted live target."""
from dataclasses import replace
from datetime import datetime,timezone
from functools import wraps
import inspect
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from fastapi import Request
from fastapi.responses import JSONResponse
from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.profiles.openai import OpenAIModelProfile
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import UsageLimits
from src.agents.ai import local_deployer as ld,local_deploy_api as api

OUT=ROOT/'docs/evidence/diagnosis-20261020/live-api-previous-logs';OUT.mkdir(exist_ok=True)
TARGET={'namespace':'acme-dev-observability','deployment':'orders-api-dogfood'}

def audit(value):
    with (OUT/'tool-calls.jsonl').open('a') as f:f.write(json.dumps({'at':datetime.now(timezone.utc).isoformat(),**value})+'\n')

def scoped(func):
    @wraps(func)
    def run(*args,**kwargs):
        bound=inspect.signature(func).bind(*args,**kwargs);bound.apply_defaults();values=dict(bound.arguments)
        allowed=(func.__name__!='list_namespaces' and values.get('namespace')==TARGET['namespace']
                 and ('deployment' not in values or values['deployment']==TARGET['deployment']))
        audit({'tool':func.__name__,'args':values,'dispatched':allowed})
        if not allowed:return {'ok':False,'output':'','error':'This bounded read is restricted to the declared namespace/workload; no out-of-scope query was dispatched.'}
        return func(*args,**kwargs)
    return run

import importlib.util
spec=importlib.util.spec_from_file_location('scope_selection',ROOT/'experiments/dogfood-diagnosis/consistency-resume/scope_selection.py')
selection=importlib.util.module_from_spec(spec);spec.loader.exec_module(selection)
ld.AGENT_TOOL_CATALOG=selection.scoped_catalog(ld.AGENT_TOOL_CATALOG,True)
# Replace no-dispatch experiment functions with original live functions plus the same advertised metadata.
from src.agents.ai import ops_tools
from functools import update_wrapper
fixed=[]
for t in ld.AGENT_TOOL_CATALOG:
    if t.category=='Investigate':
        live=scoped(getattr(ops_tools,t.name))
        live.__doc__=t.func.__doc__
        t=replace(t,func=live)
    fixed.append(t)
ld.AGENT_TOOL_CATALOG=fixed
client=AsyncOpenAI(base_url='http://127.0.0.1:18191/v1',api_key='mlx-local',max_retries=0,timeout=90)
model=OpenAIChatModel('mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit',provider=OpenAIProvider(openai_client=client),
 profile=OpenAIModelProfile(openai_chat_supports_multiple_system_messages=False))

def factory(**kwargs):
    if kwargs.get('read_only') is not True:raise ValueError('This task-owned API supports only read-only inspection.')
    agent=ld.create_local_deployer(model=model,model_settings={'max_tokens':1024,'temperature':0},retries=0,**kwargs)
    class Bounded:
        async def run(self,instruction):return await agent.run(instruction,usage_limits=UsageLimits(request_limit=5,tool_calls_limit=5))
        def iter(self,instruction):return agent.iter(instruction,usage_limits=UsageLimits(request_limit=5,tool_calls_limit=5))
    return Bounded()

api.app.dependency_overrides[api.get_deployer_factory]=lambda:factory
@api.app.middleware('http')
async def readonly_only(request:Request,call_next):
    if request.method=='POST':
        body=await request.json()
        if body.get('read_only') is not True:return JSONResponse({'detail':'This isolated task server accepts read-only requests only.'},status_code=403)
    return await call_next(request)

(OUT/'manifest.json').write_text(json.dumps({'target':TARGET,'model_endpoint':'http://127.0.0.1:18191/v1','max_tokens':1024,'temperature':0,'request_limit':5,'tool_limit':5,'retries':0,
 'scope':'Actual current kind target and same renewed ServiceAccount, all five Investigate tools registered, bounded workload guard. Not unrestricted tenant isolation or cloud operation.'},indent=2)+'\n')
if __name__=='__main__':
    import uvicorn
    uvicorn.run(api.app,host='127.0.0.1',port=18780)
