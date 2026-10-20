from pathlib import Path
from datetime import datetime,timezone
import json
import hashlib
import subprocess
base=Path('docs/evidence/diagnosis-20261020');out=base/'live-api-scoped'
def load(p):return json.loads(p.read_text())
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()
a=load(base/'scope-selection/original.json')['http_attempts'][0]['request']
b=load(base/'scope-selection/scope-advertised.json')['http_attempts'][0]['request']
def tool_schemas(r):return {t['function']['name']:t['function']['parameters'] for t in r['tools']}
assert tool_schemas(a)==tool_schemas(b) and len(a['tools'])==5
assert [m for m in a['messages'] if m['role']=='user']==[m for m in b['messages'] if m['role']=='user']
assert all(a.get(k)==b.get(k) for k in ['model','max_tokens','temperature'])
original=[p['tool_name'] for p in load(base/'scope-selection/original.json')['response'][0]['parts']]
advertised=[p['tool_name'] for p in load(base/'scope-selection/scope-advertised.json')['response'][0]['parts']]
assert 'list_namespaces' in original and 'list_namespaces' not in advertised
runs=[load(out/name) for name in ['persisted-run.json','ui-persisted-run.json']]
for r in runs:
 assert r['status']=='succeeded' and r['request']['read_only'] is True
 done=r['events'][-1];report=done['inspection'][0]
 assert report['current_revision']==37 and report['rollout_complete'] is True
 assert report['current_health']=='not_established' and report['recovery_status']=='not_established'
 assert report['investigation_proposal']['status']=='applicability_checked'
 assert done['model_completion']['status']=='complete' and done['model_completion']['model_responses']==2
 assert done['model_completion']['tool_call_attempts']==4 and not report['execution_authorized']
 assert all(e.get('tool')!='list_namespaces' for e in r['events'])
calls=[json.loads(l) for l in (out/'tool-calls.jsonl').read_text().splitlines()]
assert len(calls)==8 and all(c['dispatched'] and c['args'].get('namespace')=='acme-dev-observability' for c in calls)
p=subprocess.run(['kubectl','--kubeconfig','_workspace/diagnosis-20261020/private/deployer.kubeconfig','get','deployment','orders-api-dogfood','-n','acme-dev-observability','-o','json'],capture_output=True,text=True,check=True)
current=json.loads(p.stdout);(out/'after-deployment.json').write_text(json.dumps(current,indent=2)+'\n')
before=load(base/'live-after-deployment.json')
assert current['metadata']['uid']==before['metadata']['uid'] and current['spec']==before['spec']
ui=(out/'ui-reloaded.ax.txt').read_text();assert '8548bb49-85d9-4aa2-8207-f160652af103' in ui and 'Response complete' in ui and 'Model interpretation' in ui
result={'at':datetime.now(timezone.utc).isoformat(),'selection_control':{'same_registered_tools':5,'same_parameter_schemas':True,'same_user_request':True,'same_model_settings':True,'changed':'Only truthful run availability metadata in inventory hints and function descriptions. No tool dispatch in either selection arm.','original_selection':original,'scope_advertised_selection':advertised,'conclusion':'Missing scope metadata contributed in this pair. One adaptive pair is not general instruction-following evidence.'},'live_runs':[{'request_id':r['request_id'],'status':r['status'],'actor':r['request'].get('actor'),'model_completion':r['events'][-1]['model_completion']['status']} for r in runs],'scope':'Task-only wrapper description correction; production API has not acquired a new universal scope policy. Original failure remains failed. Same five tools, guard, ServiceAccount, 1024 tokens, temperature0, request5/tool4/retry0.','browser':{'origin':'http://localhost:13001','auth':'Existing explicitly enabled local dev Credentials provider, local-dev admin session; not GitHub OAuth or tenant isolation.','refresh':'Same UUID and recorded observations restored; tool audit unchanged at8.','raw_model_output':'Expanded and visible with Unverified label.','initial_login_limit':'127.0.0.1 redirected to localhost, first MissingCSRF preserved in observations; same localhost origin login succeeded.','screenshots':['ui-result.png','ui-reloaded.png']},'after_workload':{'same_uid':True,'same_full_spec':True,'revision':current['metadata']['annotations']['deployment.kubernetes.io/revision'],'replicas':current['spec']['replicas'],'spec_sha256':digest(current['spec'])},'preservation':'No workload or RBAC mutations; no paid API, cloud deployment, commit/push. Original failed trace retained.','limits':['Service and dependency health remain unestablished.','Supplied-text semantics and R3/R4 overall/R5 remain incomplete.'],'source_hashes':{p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in ['_workspace/diagnosis-20261020/live_readonly_scoped_api.py','experiments/dogfood-diagnosis/consistency-resume/scope_selection.py']}}
(out/'review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'runs':len(runs),'tools':len(calls),'same_workload':True,'selection_schemas':len(a['tools'])}))
