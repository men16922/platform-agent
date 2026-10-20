"""Single local-model generation per phase-aware case; no tools or mutations."""
import argparse
import asyncio
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time

import httpx
from openai import AsyncOpenAI
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from applicable_proposals import PROMPT,prepare,output_schema,validate,state_report,render
from src.agents.ai.deployment_evidence import digest

ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'docs/evidence/diagnosis-20261020'

def dump(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')

async def main():
    parser=argparse.ArgumentParser();parser.add_argument('output',type=Path);args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    rows=json.loads((BASE/'replay-after/cases.json').read_text())
    cases=[]
    for row in rows:
        cases.append({'id':row['id'],'raw_sha256':digest(row['raw']),'prepared':prepare(row['tool_result']),
                      'state':state_report(row['tool_result'])})
    dump(args.output/'cases.json',cases)
    manifest={'at':datetime.now(timezone.utc).isoformat(),'model':'mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit',
        'revision':'6e302ea604ad9ab206367e2c501d1571023e7b6d','max_tokens':1024,'temperature':0,'retries':0,
        'scope':'Experimental phase-aware proposal contract, one generation/no tool per unchanged after-case. Not the free-text production route or causal accuracy.',
        'endpoint':os.environ.get('DIAGNOSIS_REPLAY_ENDPOINT','http://127.0.0.1:18191/v1'),
        'cases_sha256':digest(cases),'prompt':PROMPT,
        'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),Path(__file__).with_name('applicable_proposals.py'),Path(__file__).parent.parent/'proposal_contract.py']}}
    dump(args.output/'manifest.json',manifest)
    for name in manifest['source_sha256']:
        p=ROOT/name;(args.output/p.name).write_bytes(p.read_bytes())
    async with httpx.AsyncClient(timeout=httpx.Timeout(90,connect=5)) as http:
        client=AsyncOpenAI(base_url=manifest['endpoint'],api_key='mlx-local',max_retries=0,http_client=http)
        try:
            for row in cases:
                request={'model':manifest['model'],'max_tokens':1024,'temperature':0,
                    'messages':[{'role':'system','content':PROMPT+'\nOutput schema:\n'+json.dumps(output_schema(row['prepared']))},
                                {'role':'user','content':json.dumps(row['prepared'],ensure_ascii=False)}]}
                record={'id':row['id'],'case_sha256':digest(row),'request':request,'schema_applicability':'not_validated',
                        'semantic_review':'required','state':row['state']}
                started=time.monotonic()
                try:
                    response=await client.chat.completions.create(**request)
                    record['response']=response.model_dump(mode='json');choice=response.choices[0]
                    record['raw']=choice.message.content or ''
                    if choice.finish_reason!='stop' or choice.message.tool_calls:raise ValueError('Incomplete/unrequested tool output')
                    proposal=validate(record['raw'],row['prepared'])
                    record.update(schema_applicability='valid',proposal=proposal.model_dump(),rendered=render(proposal,row['state'],row['prepared']))
                except Exception as exc:record['error']={'type':type(exc).__name__,'message':str(exc)}
                record['seconds']=round(time.monotonic()-started,3)
                dump(args.output/(row['id']+'.json'),record)
                print(json.dumps({'id':row['id'],'schema_applicability':record['schema_applicability'],'seconds':record['seconds'],'error':record.get('error')}),flush=True)
                if 'response' not in record:break
        finally:await client.close()

if __name__=='__main__':asyncio.run(main())
