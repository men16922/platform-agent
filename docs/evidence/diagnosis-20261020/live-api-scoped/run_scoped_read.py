import json
import time
import uuid
from pathlib import Path
import httpx
base=Path('docs/evidence/diagnosis-20261020/live-api-scoped')
request=json.loads(Path('docs/evidence/diagnosis-20261020/live-api/request.json').read_text())
request['request_id']=str(uuid.uuid4())
(base/'request.json').write_text(json.dumps(request,indent=2)+'\n')
headers={'X-Platform-Actor':'diagnosis-local-review'}
url='http://127.0.0.1:18779'
start=time.monotonic()
with httpx.Client(timeout=150) as c:
 r=c.post(url+'/api/local-deploy/stream',json=request,headers=headers);r.raise_for_status()
 (base/'events.sse').write_text(r.text)
 r=c.get(url+'/api/local-deploy/runs/'+request['request_id'],headers=headers);r.raise_for_status()
 record=r.json();(base/'persisted-run.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
 calls=(base/'tool-calls.jsonl').read_bytes()
 replay=c.post(url+'/api/local-deploy/stream',json=request,headers=headers);replay.raise_for_status()
 (base/'replay.sse').write_text(replay.text)
 assert calls==(base/'tool-calls.jsonl').read_bytes(),'Replay dispatched more reads'
 mismatch=c.get(url+'/api/local-deploy/runs/'+request['request_id'],headers={'X-Platform-Actor':'other-review'})
 verification={'request_id':request['request_id'],'duration_seconds':round(time.monotonic()-start,3),'actor_mismatch_status':mismatch.status_code,'same_replay_tail':json.loads([line[6:] for line in (base/'events.sse').read_text().splitlines() if line.startswith('data: ')][-1])==json.loads([line[6:] for line in replay.text.splitlines() if line.startswith('data: ')][-1]),'no_additional_tools_on_replay':True,'persisted_status':record.get('status')}
 (base/'verification.json').write_text(json.dumps(verification,indent=2)+'\n')
 print(json.dumps(verification))
 print(json.dumps({'keys':list(record),'tools':[json.loads(line) for line in calls.decode().splitlines()]}))
