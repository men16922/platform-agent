"""Run one bounded live read request per call; label = cold|warm. Records tool calls per run."""
import json, sys, time, uuid
from pathlib import Path
import httpx
label = sys.argv[1]
base = Path('docs/evidence/diagnosis-20261020/live-api-previous-logs')
request = json.loads(Path('docs/evidence/diagnosis-20261020/live-api/request.json').read_text())
request['request_id'] = str(uuid.uuid4())
calls_path = base / 'tool-calls.jsonl'
before = calls_path.read_text().splitlines() if calls_path.exists() else []
start = time.monotonic()
with httpx.Client(timeout=200) as c:
    r = c.post('http://127.0.0.1:18780/api/local-deploy/stream', json=request, headers={'X-Platform-Actor': 'diagnosis-local-review'}); r.raise_for_status()
    (base / f'{label}-events.sse').write_text(r.text)
    record = c.get(f"http://127.0.0.1:18780/api/local-deploy/runs/{request['request_id']}", headers={'X-Platform-Actor': 'diagnosis-local-review'}).json()
(base / f'{label}-persisted-run.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
calls = [json.loads(l) for l in calls_path.read_text().splitlines()[len(before):]]
out = {'label': label, 'request_id': request['request_id'], 'seconds': round(time.monotonic() - start, 3), 'status': record.get('status'),
       'tools': [{'tool': c['tool'], 'previous': c['args'].get('previous'), 'dispatched': c['dispatched']} for c in calls]}
(base / f'{label}-summary.json').write_text(json.dumps(out, indent=2) + '\n'); print(json.dumps(out))
