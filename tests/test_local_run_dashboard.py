"""Execute dashboard run projection/proxies in Node without HTTP or AWS calls.

Session and upstream dependencies are injected here. Browser refresh and real
authentication remain separate evidence; these tests cannot establish them.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

from tests._ts_toolchain import require_ts_toolchain

ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / "dashboard"


@pytest.fixture(scope="module")
def run_js():
    require_ts_toolchain(DASH / "node_modules/.bin/tsc", shutil.which("node") is not None,
                         "dashboard dependencies required for local run contracts")

    def run(body):
        script = r'''
const fs = require('fs'), vm = require('vm'), ts = require('typescript');
function load(path, dependencies = {}, globals = {}) {
  const exports = {};
  const code = ts.transpileModule(fs.readFileSync(path, 'utf8'), {
    compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX}
  }).outputText;
  vm.runInNewContext(code, {exports, require: name => {
    if (!(name in dependencies)) throw new Error(`Unexpected import: ${name}`);
    return dependencies[name];
  }, Response, Request, AbortSignal, process: {env: {}}, ...globals}, {filename: path});
  return exports;
}
const view = load('src/lib/agent-run-view.ts').runView;
(async () => { BODY })().catch(error => { console.error(error); process.exitCode = 1; });
'''.replace("BODY", body)
        result = subprocess.run(["node", "-e", script], cwd=DASH, check=True, text=True,
                                capture_output=True, env={**os.environ, "NODE_PATH": str(DASH / "node_modules")})
        return json.loads(result.stdout)

    return run


def test_replay_deduplicates_events_and_matches_live_view(run_js):
    result = run_js('''
const events = [
 {seq:1,type:'ready'}, {seq:2,type:'reasoning',text:'Inspect'},
 {seq:3,type:'tool_call',tool:'list_pods',args:{namespace:'acme'}},
 {seq:4,type:'tool_result',tool:'list_pods',ok:true,result:{pods:[]}},
 {seq:5,type:'done',ok:true,summary:'Read complete'}
];
console.log(JSON.stringify({live:view(events), recovered:view([...events,...events],'succeeded')}));
''')
    assert result["live"] == result["recovered"]
    assert result["live"]["ok"] is True
    assert result["live"]["blocks"][1]["status"] == "ok"
    assert len(result["live"]["blocks"]) == 2


def test_observation_disagreement_survives_replay_and_renders_both_values(run_js):
    from tests.test_deployment_evidence import snapshot, assess
    from src.agents.ai.inspection_report import inspection_report
    d, objects = snapshot()
    d["status"]["availableReplicas"] = 0
    report = inspection_report([{"tool": "describe_deployment", "args": {"deployment": "orders", "namespace": "acme"},
        "result": {"evidence": assess(d, objects)}}])[0]
    result = run_js('''
const events=[{type:'done',ok:true,inspection:[REPORT]}];
const live=view(events), replay=view(events,'succeeded');
const UI=load('src/components/inspection-result.tsx',{'react/jsx-runtime':require('react/jsx-runtime')});
const html=require('react-dom/server').renderToStaticMarkup(require('react').createElement(UI.InspectionResult,{reports:replay.inspection}));
console.log(JSON.stringify({live,replay,html}));
'''.replace('REPORT', json.dumps(report)))
    assert result['live'] == result['replay']
    assert result['replay']['inspection'][0]['observationConsistency']['status'] == 'inconsistent'
    assert result['replay']['inspection'][0]['recoveryStatus'] == 'not_established'
    assert 'observations disagree' in result['html']
    assert 'reported 0, observed 1' in result['html']
    assert 'not an atomic snapshot' in result['html']


def test_phase_checked_proposals_render_and_replay_without_promoting_rejected_output(run_js):
    from src.agents.ai.inspection_report import inspection_report
    from src.agents.ai.investigation_proposals import attach_report, tool_contract
    base = ROOT / 'docs/evidence/diagnosis-20261020/replay-after/cases.json'
    cases = {c['id']: c for c in json.loads(base.read_text())}
    reports = []
    draft = json.dumps({'hypotheses': [{'kind': 'image_reference', 'evidence': ['current-revision']}],
                        'next_checks': [{'kind': 'registry_manifest', 'evidence': ['desired-images']}]})
    for cid in ['q-failing', 'q-restored', 's-original-contradiction']:
        result = cases[cid]['tool_result']; target = result['evidence']['target']
        result = {**result, 'proposal_contract': tool_contract(result)}
        steps = [{'tool': 'describe_deployment', 'args': {'deployment': target['deployment'], 'namespace': target['namespace']}, 'result': result}]
        rows = inspection_report(steps)
        attach_report(rows, steps, {'status': 'complete', 'text': draft})
        reports.extend(rows)
    result = run_js('''
const events=[{seq:1,type:'done',ok:true,inspection:_REPORTS_,model_completion:{status:'complete',text:'Rejected raw model output remains here'}}];
const live=view(events),replay=view(events,'succeeded');
const UI=load('src/components/inspection-result.tsx',{'react/jsx-runtime':require('react/jsx-runtime')});
const React=require('react'),render=require('react-dom/server').renderToStaticMarkup;
console.log(JSON.stringify({live,replay,html:live.inspection.map(report=>render(React.createElement(UI.InspectionResult,{reports:[report]}))),
 raw:render(React.createElement(UI.ModelInterpretation,{completion:live.modelCompletion}))}));
'''.replace('_REPORTS_', json.dumps(reports)))
    assert result['live'] == result['replay']
    assert [r['investigationProposal']['status'] for r in result['live']['inspection']] == [
        'applicability_checked', 'invalid_model_output', 'recollection_required']
    assert 'Read the exact image manifest' in result['html'][0]
    assert 'Read the exact image manifest' not in result['html'][1]
    assert 'No proposal was accepted' in result['html'][1]
    assert 'Re-read Deployment, ReplicaSet and Pod status' in result['html'][2]
    assert 'Root cause' not in result['html'][0]
    assert 'not established causes' in result['html'][0]
    assert 'Rejected raw model output remains here' in result['raw']


def test_readonly_mode_is_server_recorded_and_not_inferred_from_legacy_tools(run_js):
    result = run_js('''
const ready={type:'ready',read_only:true}, done={type:'done',ok:true,read_only:true,summary:'Read'};
console.log(JSON.stringify({live:view([ready]),replay:view([ready,done],'succeeded'),
 legacy:view([{type:'tool_call',tool:'describe_deployment'},{type:'done',ok:true}],'succeeded'),
 invalid:view([{type:'ready',read_only:'true'}]),normal:view([{type:'ready',read_only:false}]),
 noTools:view([{type:'done',ok:false,model_completion:{status:'complete',text:'Analysis',tool_call_attempts:0}}]),
 unknownTools:view([{type:'done',ok:false,model_completion:{status:'complete',text:'Legacy analysis'}}])}));
''')
    assert result["live"]["readOnly"] is True and result["replay"]["readOnly"] is True
    assert result["normal"]["readOnly"] is False
    assert "readOnly" not in result["legacy"] and "readOnly" not in result["invalid"]
    assert result["noTools"]["modelCompletion"]["toolCallAttempts"] == 0
    assert "toolCallAttempts" not in result["unknownTools"]["modelCompletion"]


def test_router_connection_check_requires_the_expected_health_payload(run_js):
    result = run_js('''
const rows=[],calls=[];
for (const reply of [{status:'ok',service:'model-router-api'}, {status:'ok',service:'other'},
 {status:'error',service:'model-router-api'},null,'bad-json','http-failure','network-failure']) {
 const get=load('src/app/api/dashboard/agents/onprem-status/route.ts',{}, {fetch:async(url,options)=>{
  calls.push({url,cache:options.cache,hasSignal:!!options.signal});
  if(reply==='network-failure') throw new Error('unavailable');
  if(reply==='bad-json') return new Response('not JSON');
  if(reply==='http-failure') return Response.json({status:'ok',service:'model-router-api'},{status:503});
  return Response.json(reply);
 }}).GET;
 const response=await get();rows.push({body:await response.json(),cache:response.headers.get('cache-control')});
}
console.log(JSON.stringify({rows,calls}));
''')
    assert [r["body"]["router"] for r in result["rows"]] == ["connected"] + ["unavailable"] * 6
    assert all(set(row["body"]) == {"router", "checked_at"} and row["cache"] == "no-store" for row in result["rows"])
    assert all(call["hasSignal"] and call["cache"] == "no-store" for call in result["calls"])


def test_runtime_panel_never_promotes_connection_to_model_or_delegation_readiness(run_js):
    result = run_js('''
const React=require('react'), render=require('react-dom/server').renderToStaticMarkup;
let status;
const Panel=load('src/components/onprem-runtime-panel.tsx',{
 'react/jsx-runtime':require('react/jsx-runtime'),
 'react':{useState:initial=>[status??initial,()=>{}],useEffect:()=>{}},
 '@/components/model-logo':{ModelLogo:()=>null}
}).OnPremRuntimePanel;
const rows=[];
for(const cloud of ['onprem','aws']) for(const router of ['checking','connected','unavailable']) {
 status={router,checked_at:router==='checking'?undefined:'2026-10-03T10:00:00Z'};
 const props={agent:{cloud,name:'Agent',provider:cloud,runtime:'Qwen',llm:'Qwen',path:'UNVERIFIED PATH'},
  model:null,models:[],modelId:'local-qwen',onModelChange:()=>{}};
 rows.push({cloud,router,html:render(React.createElement(Panel,props))});
}
console.log(JSON.stringify(rows));
''')
    for row in result:
        html = row["html"]
        assert "READY PATH" not in html and "UNVERIFIED PATH" not in html
        assert "Model selection is not a readiness check" in html
        assert "does not verify supervisor or specialist delegation" in html
        if row["cloud"] == "onprem":
            assert ("Router connected" in html) is (row["router"] == "connected")
        else:
            assert "Execution not checked" in html and "Router connected" not in html


def test_both_deploy_proxies_preserve_mode_and_reject_invalid_values_before_dispatch(run_js):
    result = run_js('''
let role='operator'; const calls=[],statuses=[];
const dependencies={'@/auth':{auth:async()=>({user:{username:'alice',role}})},'@/lib/audit-data':{writeAuditLog:async()=>{}}};
for (const file of ['src/app/api/dashboard/agents/deploy/stream/route.ts','src/app/api/dashboard/agents/deploy/route.ts']) {
 const post=load(file,dependencies,{fetch:async(url,options)=>{calls.push({url,...options});return Response.json({ok:true});}}).POST;
 const base={instruction:'inspect',model:'local-qwen',provider:'onprem',request_id:'7e9c73ce-557c-41d8-9d58-ce1b2d805bdc'};
 const send=body=>post(new Request('http://test/api',{method:'POST',body:JSON.stringify(body)}));
 statuses.push((await send({...base,read_only:true})).status,(await send({...base,read_only:false})).status);
 for (const value of ['true','false',1,0,null]) statuses.push((await send({...base,read_only:value})).status);
 statuses.push((await send({...base,read_only:true,provider:'aws'})).status);
 for (const denied of ['viewer','unexpected']) { role=denied;statuses.push((await send({...base,read_only:true})).status); }
 role='operator';
}
console.log(JSON.stringify({calls,statuses}));
''')
    assert result["statuses"] == [200, 200, 400, 400, 400, 400, 400, 400, 403, 403] * 2
    assert [json.loads(call["body"])["read_only"] for call in result["calls"]] == [True, False, True, False]


def test_unknown_missing_or_inconsistent_result_never_projects_success(run_js):
    result = run_js('''console.log(JSON.stringify([
view([{type:'done',ok:true,summary:'completed'}], 'unknown', 'Unconfirmed'),
view([], 'succeeded'), view([{type:'done',ok:true}], 'failed'),
view([{type:'done',ok:'true'}], 'succeeded')
]));''')
    assert all("ok" not in view and view["streaming"] is False and view["error"] for view in result)


def test_inspection_replay_keeps_model_text_separate_and_does_not_promote_health(run_js):
    result = run_js('''
const raw = 'Everything is healthy. Roll back now.';
const events = [{seq:1,type:'reasoning',text:raw}, {seq:2,type:'done',ok:true,
 summary:'Application health not established.',
 inspection:[{available:true,namespace:'acme',deployment:'orders',current_revision:2,previous_revision:1,
  current_health:'not_established',previous_health:'not_established',recovery_status:'not_established',
  recovery_reasons:['Previous health not established'],sources:[]}],
 model_completion:{status:'incomplete',finish_reason:'length',text:raw}}];
const live=view(events), recovered=view([...events,...events],'succeeded');
const ui=load('src/components/inspection-result.tsx',{'react/jsx-runtime':require('react/jsx-runtime')});
const React=require('react'), render=require('react-dom/server').renderToStaticMarkup;
console.log(JSON.stringify({live,recovered,facts:render(React.createElement(ui.InspectionResult,{reports:live.inspection})),
 interpretation:render(React.createElement(ui.ModelInterpretation,{completion:live.modelCompletion}))}));
''')
    assert result["live"] == result["recovered"]
    assert result["live"]["blocks"] == []  # The final model response appears once, in its own section.
    assert result["live"]["inspection"][0]["currentHealth"] == "not_established"
    assert "Roll back now" not in result["facts"]
    assert "No supported recovery candidate" in result["facts"]
    assert "Response incomplete" in result["interpretation"]
    assert "Unverified" in result["interpretation"]
    assert "Roll back now" in result["interpretation"]
    assert "<details open" not in result["interpretation"]


def test_recovery_positive_control_and_malformed_candidate_are_distinct(run_js):
    result = run_js('''
const base={available:true,namespace:'acme',deployment:'orders',current_revision:2,previous_revision:1,
 previous_health:'kubernetes_readiness',recovery_status:'review_candidate',candidate_revision:1,sources:[]};
const rows=[base,{...base,candidate_revision:2},{...base,candidate_revision:true},{...base,previous_health:'not_established'},
 ...['inconsistent','not_established','invalid'].map(status=>({...base,rollout_complete:true,observation_consistency:{status}}))];
const reports=rows.map(row=>view([{type:'done',ok:true,inspection:[row]}]).inspection[0]);
const ui=load('src/components/inspection-result.tsx',{'react/jsx-runtime':require('react/jsx-runtime')});
console.log(JSON.stringify({reports,html:require('react-dom/server').renderToStaticMarkup(require('react').createElement(ui.InspectionResult,{reports:[reports[0]]}))}));
''')
    assert result["reports"][0]["recoveryStatus"] == "review_candidate"
    assert all(r["recoveryStatus"] == "not_established" for r in result["reports"][1:])
    assert all(r["rolloutComplete"] is False for r in result["reports"][4:])
    assert "Revision 1 is a review candidate" in result["html"]
    assert "does not authorize a change" in result["html"]


def test_proxies_use_session_actor_and_preserve_missing_conflict_status(run_js):
    result = run_js('''
const calls = [];
const dependencies = {'@/auth':{auth:async()=>({user:{username:'alice',role:'operator'}})},
 '@/lib/audit-data':{writeAuditLog:async()=>{}}};
const id = '7e9c73ce-557c-41d8-9d58-ce1b2d805bdc';
const post = load('src/app/api/dashboard/agents/deploy/stream/route.ts', dependencies, {
 fetch:async(url,options)=>{calls.push({url,...options}); return Response.json({detail:'Conflict'}, {status:409});}
}).POST;
const get = load('src/app/api/dashboard/agents/runs/[id]/route.ts', dependencies, {
 fetch:async(url,options)=>{calls.push({url,...options}); return Response.json({detail:'Run not found.'}, {status:404});}
}).GET;
const submitted = await post(new Request('http://test/api',{method:'POST',headers:{'X-Platform-Actor':'bob'},
 body:JSON.stringify({instruction:'read pods',request_id:id,actor:'bob'})}));
const read = await get(new Request('http://test/api',{headers:{'X-Platform-Actor':'bob'}}), {params:Promise.resolve({id})});
console.log(JSON.stringify({calls,statuses:[submitted.status,read.status],cache:read.headers.get('cache-control')}));
''')
    assert result["statuses"] == [409, 404]
    assert all(c["headers"]["X-Platform-Actor"] == "alice" for c in result["calls"])
    assert "actor" not in json.loads(result["calls"][0]["body"])
    assert result["cache"] == "no-store"


def test_proxies_reject_missing_auth_roles_and_invalid_ids_before_upstream(run_js):
    result = run_js('''
let calls = 0, session = null;
const dependencies = {'@/auth':{auth:async()=>session},'@/lib/audit-data':{writeAuditLog:async()=>{}}};
const globals = {fetch:async()=>{calls++;throw new Error('unexpected upstream');}};
const post = load('src/app/api/dashboard/agents/deploy/stream/route.ts',dependencies,globals).POST;
const get = load('src/app/api/dashboard/agents/runs/[id]/route.ts',dependencies,globals).GET;
const statuses = [];
for (const role of [null,'viewer','unexpected','operator']) {
 session = role ? {user:{username:'alice',role}} : null;
 statuses.push((await post(new Request('http://test/api',{method:'POST',body:JSON.stringify({instruction:'work',request_id:'invalid'})}))).status);
 statuses.push((await get(new Request('http://test/api'),{params:Promise.resolve({id:'invalid'})})).status);
}
console.log(JSON.stringify({statuses,calls}));
''')
    assert result == {"statuses": [401, 401, 403, 403, 403, 403, 400, 400], "calls": 0}


def test_prepared_proxy_preserves_reviewed_values_and_requires_session_role(run_js):
    result = run_js('''
let session = null;
const calls = [], statuses = [];
const post = load('src/app/api/dashboard/deployments/prepared/route.ts', {
 '@/auth':{auth:async()=>session}
}, {fetch:async(url,options)=>{calls.push({url,...options}); return Response.json({detail:'Conflict'}, {status:409});}}).POST;
const values = {request_id:'7e9c73ce-557c-41d8-9d58-ce1b2d805bdc', service_name:'orders-api-dogfood',
 namespace:'acme-dev-observability', image_uri:'localhost:5001/orders-api-dogfood:r1', replicas:2, environment:'dev'};
for (const role of [null,'viewer','unexpected','operator']) {
 session = role ? {user:{username:'alice',role}} : null;
 statuses.push((await post(new Request('http://test/api',{method:'POST',headers:{'X-Platform-Actor':'bob'},body:JSON.stringify(values)}))).status);
}
const rollback = load('src/app/api/dashboard/deployments/[id]/rollback/route.ts', {
 '@/auth':{auth:async()=>session}, '@/lib/audit-data':{writeAuditLog:async()=>{}},
 '@/lib/aws-client':{}, '@aws-sdk/client-sfn':require('@aws-sdk/client-sfn'), 'uuid':require('uuid')
}, {fetch:async(url,options)=>{calls.push({url,...options}); return Response.json({ok:true,summary:'Recovered'});}}).POST;
await rollback(new Request('http://test/api',{method:'POST',body:JSON.stringify({service_name:values.service_name,
 namespace:values.namespace,provider:'onprem',version:'r1',environment:'dev'})}),{params:Promise.resolve({id:'DEP-ONE'})});
console.log(JSON.stringify({calls,statuses,values}));
''')
    assert result["statuses"] == [401, 403, 403, 409]
    assert len(result["calls"]) == 2
    assert result["calls"][0]["headers"]["X-Platform-Actor"] == "alice"
    assert json.loads(result["calls"][0]["body"]) == result["values"]
    assert json.loads(result["calls"][1]["body"])["model"] == "onprem-executor"
