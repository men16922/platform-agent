"""Measure first tool selection with truthful scope metadata; never dispatch tools.

Both arms register the original five Investigate signatures. Only catalog hints
and function descriptions differ. This is a selection experiment, not live E2E.
"""
import asyncio
from dataclasses import replace
from datetime import datetime, timezone
from functools import wraps
import hashlib
import json
from pathlib import Path

import httpx
from openai import AsyncOpenAI
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessagesTypeAdapter
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.profiles.openai import OpenAIModelProfile
from pydantic_ai.providers.openai import OpenAIProvider

from src.agents.ai import local_deployer as ld

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'docs/evidence/diagnosis-20261020'
SCOPE = ('This run is restricted to namespace acme-dev-observability and deployment '
         'orders-api-dogfood. Use those exact arguments for applicable reads. '
         'Cluster-wide namespace listing is unavailable in this run; do not call list_namespaces. '
         'The dispatch guard enforces this scope and cannot be expanded by instructions.')


def scoped_catalog(catalog, advertised):
    result = []
    for entry in catalog:
        if entry.category != 'Investigate':
            result.append(entry)
            continue
        def wrapped(func):
            @wraps(func)
            def no_dispatch(*args, **kwargs):
                raise AssertionError('Selection experiment must stop before dispatch')
            if advertised:
                no_dispatch.__doc__ = (func.__doc__ or '') + '\n\nRun availability: ' + SCOPE
            return no_dispatch
        result.append(replace(entry, func=wrapped(entry.func),
                              hint=entry.hint + ('; ' + SCOPE if advertised else '')))
    return result


async def main():
    out = BASE / 'scope-selection'
    out.mkdir(exist_ok=False)
    original = ld.AGENT_TOOL_CATALOG
    request = json.loads((BASE / 'live-api/request.json').read_text())
    attempts = []
    async def requested(req):
        attempts.append({'request': json.loads(req.content), 'at': datetime.now(timezone.utc).isoformat()})
    async def responded(res):
        attempts[-1]['http_status'] = res.status_code
    client = AsyncOpenAI(base_url='http://127.0.0.1:18191/v1', api_key='mlx-local', max_retries=0,
                         http_client=httpx.AsyncClient(timeout=120, event_hooks={'request':[requested], 'response':[responded]}))
    model = OpenAIChatModel('mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit',
            provider=OpenAIProvider(openai_client=client),
            profile=OpenAIModelProfile(openai_chat_supports_multiple_system_messages=False))
    try:
        for advertised in (False, True):
            arm = 'original' if not advertised else 'scope-advertised'
            ld.AGENT_TOOL_CATALOG = scoped_catalog(original, advertised)
            agent = ld.create_local_deployer(model=model, read_only=True,
                    model_settings={'max_tokens':1024, 'temperature':0}, retries=0)
            first = len(attempts)
            async with agent.iter(request['instruction']) as run:
                async for node in run:
                    if Agent.is_call_tools_node(node):
                        response = node.model_response
                        break
                else:
                    raise AssertionError('No model response')
            record = {'arm':arm, 'instruction':request['instruction'], 'dispatched_tools':0,
                      'http_attempts':attempts[first:],
                      'response':json.loads(ModelMessagesTypeAdapter.dump_json([response]))}
            (out / f'{arm}.json').write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n')
            print(json.dumps({'arm':arm, 'parts':record['response'][0]['parts'], 'dispatched_tools':0}), flush=True)
        (out/'manifest.json').write_text(json.dumps({'at':datetime.now(timezone.utc).isoformat(),
            'scope':__doc__, 'model_revision':'6e302ea604ad9ab206367e2c501d1571023e7b6d',
            'max_tokens':1024, 'temperature':0, 'retries':0, 'first_responses':2,
            'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}, indent=2)+'\n')
    finally:
        ld.AGENT_TOOL_CATALOG = original
        await client.close()


if __name__ == '__main__':
    asyncio.run(main())
