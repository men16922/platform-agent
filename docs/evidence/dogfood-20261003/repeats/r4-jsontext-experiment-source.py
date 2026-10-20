"""Same evidence contract, JSON-text output instead of final_result tool calls."""
from pathlib import Path
import asyncio
import datetime as dt
import hashlib
import importlib.util
import json
import time
from pydantic_ai import Agent,PromptedOutput,capture_run_messages
from pydantic_ai.messages import ModelMessagesTypeAdapter
from pydantic_ai.usage import UsageLimits
p=Path(__file__).with_name('diagnose_evidence_experiment.py');spec=importlib.util.spec_from_file_location('dx',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
agent=Agent(m.model,output_type=PromptedOutput(m.DiagnosisDraft),deps_type=dict,system_prompt=m.PROMPT,retries=1)
agent.output_validator(m.check_sources)
async def main():
 manifest={'at':dt.datetime.now(dt.timezone.utc).isoformat(),'model':m.MODEL,'system_prompt_sha256':hashlib.sha256(m.PROMPT.encode()).hexdigest(),'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'changed_variable':'PromptedOutput JSON text instead of output tool; same schema/prompt/cases/model endpoint; explicit request limit 2/time limit 60s','operational_tools':0,'cases':m.CASES}
 (m.OUT/'r4-jsontext-experiment.json').write_text(json.dumps(manifest,indent=2)+'\n')
 for case in m.CASES:
  report={'case':case,'started_at':dt.datetime.now(dt.timezone.utc).isoformat(),'operational_tools':0};start=time.monotonic()
  with capture_run_messages() as messages:
   try:
    result=await asyncio.wait_for(agent.run(json.dumps({'question':case['question'],'sources':case['sources']}),deps=case['sources'],usage_limits=UsageLimits(request_limit=2)),timeout=60)
    report.update(status='schema_and_citations_valid',output=result.output.model_dump())
   except Exception as exc:report.update(status='failed',error_type=type(exc).__name__,error=str(exc))
  report['elapsed_sec']=round(time.monotonic()-start,3);report['messages']=json.loads(ModelMessagesTypeAdapter.dump_json(messages))
  (m.OUT/('r4-jsontext-'+case['id']+'.json')).write_text(json.dumps(report,indent=2)+'\n')
  print(json.dumps({k:v for k,v in report.items() if k!='messages'}),flush=True)
asyncio.run(main())
