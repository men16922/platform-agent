"""Experimental recovery support obligations; no production schema change.

Exact quotes establish source binding only. A reviewer must still assess whether
the quoted text supports its assigned role. Original inputs and raw output stay.
"""
import asyncio
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from typing import Literal

from openai import AsyncOpenAI
from pydantic import Field, model_validator
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.profiles.openai import OpenAIModelProfile
from pydantic_ai.providers.openai import OpenAIProvider

from src.agents.ai import snapshot_diagnosis as sd
from src.agents.ai.local_deployer import create_local_deployer
from src.agents.ai.model_router import route_deploy

ROOT = Path(__file__).resolve().parents[3]


class RecoverySupport(sd.Record):
    role: Literal['current_revision_failure', 'previous_revision_healthy', 'previous_revision_restorable']
    source_id: str
    quote: str = Field(min_length=8, max_length=250,
        description='Verbatim observation of this fact. An instruction, decision or recommendation is not a health or availability observation.')


class SupportedDiagnosis(sd.Diagnosis):
    recovery_support: list[RecoverySupport] = Field(max_length=3,
        description='For review_candidate, cite observed current revision failure, observed healthy previous revision, and its available restorable image/specification. Otherwise may be empty. Do not infer missing facts from a source directive.')

    @model_validator(mode='after')
    def necessary_support(self):
        roles = [s.role for s in self.recovery_support]
        if len(roles) != len(set(roles)):
            raise ValueError('Duplicate recovery support role')
        if self.recovery == 'review_candidate' and set(roles) != {
            'current_revision_failure', 'previous_revision_healthy', 'previous_revision_restorable'}:
            raise ValueError('Recovery candidate lacks necessary cited support')
        return self


async def main():
    out = ROOT/'docs/evidence/diagnosis-20261020/snapshot-support'
    out.mkdir(exist_ok=False)
    cases = json.loads((ROOT/'experiments/dogfood-diagnosis/cases.json').read_text())
    original_schema, original_validate = sd.Diagnosis, sd.validate_citations
    def validate(draft, prepared):
        original_validate(draft, prepared)
        sources = {s['source_id']:s['text'] for s in prepared['sources']}
        for support in draft.recovery_support:
            if support.source_id not in sources or support.quote not in sources[support.source_id]:
                raise ValueError('Recovery support must quote an applicable source')
    sd.Diagnosis, sd.validate_citations = SupportedDiagnosis, validate
    client = AsyncOpenAI(base_url='http://127.0.0.1:18191/v1',api_key='mlx-local',max_retries=0,timeout=120)
    model = OpenAIChatModel('mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit',
        provider=OpenAIProvider(openai_client=client),
        profile=OpenAIModelProfile(openai_chat_supports_multiple_system_messages=False))
    factory = lambda **kwargs:create_local_deployer(model=model,
        model_settings={'max_tokens':1024,'temperature':0},retries=0,**kwargs)
    try:
        for case in cases:
            q=case['input']
            result=await route_deploy(q['question'],'local-qwen','onprem',read_only=True,snapshot=q,agent_factory=factory)
            row={'request':q,'outcome':asdict(result)}
            (out/(case['id']+'.json')).write_text(json.dumps(row,ensure_ascii=False,indent=2)+'\n')
            print(json.dumps({'case':case['id'],'status':result.snapshot_analysis['status'],
                'completion':(result.model_completion or {}).get('status'),
                'diagnosis':result.snapshot_analysis['diagnosis']},ensure_ascii=False),flush=True)
        (out/'manifest.json').write_text(json.dumps({'model_revision':'6e302ea604ad9ab206367e2c501d1571023e7b6d',
            'settings':{'max_tokens':1024,'temperature':0,'requests':1,'tools':0,'retries':0},
            'changed':'Experimental output schema and its exact-source support validator only; original prompt and seven sources unchanged.',
            'limits':__doc__, 'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},indent=2)+'\n')
    finally:
        sd.Diagnosis, sd.validate_citations = original_schema, original_validate
        await client.close()


if __name__=='__main__':
    asyncio.run(main())
