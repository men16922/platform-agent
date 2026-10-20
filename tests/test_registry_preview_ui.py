"""Execute the TS request/Invoke contract; local HTTP/session evidence is separate."""
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

from tests._ts_toolchain import require_ts_toolchain

ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / 'dashboard'
REQUEST = dict(tenant='acme', env='prod', capability='logging', version='7.1.0')
PLAN = dict(contract_version='registry-attachment/v1', request_id='request-1', base_commit='a'*40,
            catalog_blob='b'*40, tenant_blob='c'*40, values_path='infra/onprem/addons/values/loki.yaml',
            values_blob='d'*40, path='platform/tenants/acme.yaml',
            diff='--- a/platform/tenants/acme.yaml\n+++ b/platform/tenants/acme.yaml\n+ logging: loki 7.1.0\n',
            output_sha256='e'*64, digest='f'*64, expires_at='2099-01-01T00:00:00+00:00')


@pytest.fixture(scope='module')
def run_ts(tmp_path_factory):
    compiler = DASH / 'node_modules/.bin/tsc'
    require_ts_toolchain(compiler, shutil.which('node') is not None,
                         'dashboard npm dependencies required for TS contract execution')
    out = tmp_path_factory.mktemp('preview-ts')
    subprocess.run([str(compiler), 'src/lib/registry-preview-contract.ts', 'src/lib/user-role-update.ts',
                    'src/lib/registry-planner-connection.ts', 'src/lib/registry-preview.ts',
                    '--outDir', str(out), '--target', 'es2020', '--module', 'commonjs',
                    '--skipLibCheck'], cwd=DASH, check=True, capture_output=True, text=True)
    def run(code):
        script = '''const c=require('./registry-preview-contract');
const {userRoleUpdate}=require('./user-role-update');
const connection=require('./registry-planner-connection');
const transport=require('./registry-preview');
(async()=>{try {const value=await (async()=>{CODE})();
console.log(JSON.stringify({value}));} catch(e){console.log(JSON.stringify({error:e.code||e.message,status:e.status}));}})();'''.replace('CODE',code)
        result = subprocess.run(['node','-e',script], cwd=out, text=True, capture_output=True, check=True,
            env={**os.environ,'NODE_PATH':str(DASH/'node_modules')})
        return json.loads(result.stdout)
    return run


@pytest.mark.parametrize('extra', ['username','subject','role','path','repository','registry_write_tenants'])
def test_request_does_not_accept_authority_fields(run_ts, extra):
    result = run_ts('return c.attachmentRequest('+json.dumps({**REQUEST,extra:'admin'})+');')
    assert result['status'] == 422


@pytest.mark.parametrize('value', ['acme\n','acme\r','../globex','',None])
def test_invalid_names_rejected_before_invocation(run_ts,value):
    assert run_ts('return c.attachmentRequest('+json.dumps({**REQUEST,'tenant':value})+');')['status'] == 422


@pytest.mark.parametrize('origin,custom,site,status', [
    ('https://dashboard.example','1','same-origin',None),
    ('https://dashboard.example.evil.test','1','same-origin',403),
    ('null','1','same-origin',403),('https://dashboard.example',None,'same-origin',403),
    ('https://dashboard.example','1','cross-site',403),
])
def test_origin_custom_header_and_fetch_metadata(run_ts,origin,custom,site,status):
    headers={'Origin':origin,'Content-Type':'application/json','Sec-Fetch-Site':site}
    if custom:headers['X-Registry-Preview']=custom
    result=run_ts("c.checkPreviewOrigin(new Request('https://dashboard.example/api',{headers:"+
                  json.dumps(headers)+"}),'https://dashboard.example');return true;")
    assert result.get('status') == status


@pytest.mark.parametrize('function_error,http_status,body,status', [
    ('Unhandled',200,dict(ok=True,status=200,plan=PLAN),503),
    (None,202,dict(ok=True,status=200,plan=PLAN),503),
    (None,200,dict(ok=False,status=403,error='registry_write_forbidden'),403),
    (None,200,dict(ok=False,status=409,error='already_attached'),409),
    (None,200,dict(ok=True,status=200,plan=PLAN),None),
    (None,200,dict(ok=True,status=200,plan={**PLAN,'path':'platform/tenants/globex.yaml'}),503),
    (None,200,dict(ok=True,status=200,plan={**PLAN,'expires_at':'2000-01-01T00:00:00Z'}),409),
    (None,200,dict(ok=True,status=200,plan={**PLAN,'host_path':'/tmp/private'}),503),
])
def test_invoke_200_does_not_override_errors_or_wrong_output(run_ts,function_error,http_status,body,status):
    result=run_ts('return c.decodePreview(new TextEncoder().encode('+json.dumps(json.dumps(body))+'),'+
                  json.dumps(function_error)+','+str(http_status)+','+json.dumps(REQUEST)+');')
    assert result.get('status') == status
    if status is None: assert result['value'] == PLAN


def test_request_limit_applies_without_content_length(run_ts):
    result=run_ts("return await c.readPreviewRequest(new Request('http://localhost',{method:'POST',body:' '.repeat(4097)}));")
    assert result['status']==413


@pytest.mark.parametrize('tenants', [None,[],['acme']])
def test_role_update_never_writes_or_removes_write_grants(run_ts,tenants):
    arg='undefined' if tenants is None else json.dumps(tenants)
    update=run_ts("return userRoleUpdate('operator','viewer','timestamp',undefined,undefined,"+arg+");")['value']
    assert 'registry_write_tenants' not in update['ExpressionAttributeNames'].values()
    assert 'role' in update['ExpressionAttributeNames'].values()
    if tenants is None: assert 'tenants' not in update['ExpressionAttributeNames'].values()


def test_live_store_consumes_partial_update_before_demo_path():
    source=(DASH/'src/lib/user-data.ts').read_text()
    assert 'new UpdateCommand({' in source and '...userRoleUpdate(' in source
    assert 'new PutCommand' not in source
    assert source.index('return result.Attributes as UserRecord') < source.index('const existing = await getUserRecord')


def test_route_uses_session_identity_and_checks_request_before_planning():
    source=(DASH/'src/app/api/dashboard/platform/attach/preview/route.ts').read_text()
    assert 'previewAttachment(session.user.username, input)' in source
    assert source.index('checkPreviewOrigin(request, origin)') < source.index('await readPreviewRequest(request)')
    assert source.index('await readPreviewRequest(request)') < source.index('await previewAttachment(')


@pytest.mark.parametrize('field', ['base_commit', 'request_id', 'values_path'])
def test_output_identifiers_reject_trailing_newline(run_ts, field):
    body = dict(ok=True, status=200, plan={**PLAN, field: PLAN[field] + '\n'})
    result = run_ts('return c.decodePreview(new TextEncoder().encode(' + json.dumps(json.dumps(body)) +
                    '),undefined,200,' + json.dumps(REQUEST) + ');')
    assert result['status'] == 503


def _read_stream(run_ts, chunks, *, content_length=None, cancel='resolve', read_error=False):
    return run_ts('''
const chunks = CHUNKS.map(bytes => Uint8Array.from(bytes));
let pulls = 0, cancelled = 0, timer;
const stream = new ReadableStream({
  pull(controller) {
    pulls++;
    if (chunks.length) controller.enqueue(chunks.shift());
    else if (READ_ERROR) controller.error(new Error('transport detail must not escape'));
    else controller.close();
  },
  cancel() {
    cancelled++;
    if (CANCEL === 'reject') return Promise.reject(new Error('cancel failed'));
    if (CANCEL === 'pending') return new Promise(() => {});
  }
}, {highWaterMark: 0});
const request = new Request('http://localhost', {
  method:'POST', body:stream, duplex:'half', headers:HEADERS,
});
try {
  const outcome = await Promise.race([
    c.readPreviewRequest(request).then(value => ({value}),
      error => ({error:error.code || error.message, status:error.status})),
    new Promise(resolve => {timer=setTimeout(() => resolve({timeout:true}), 150);}),
  ]);
  return {...outcome, cancelled, pulls, locked:request.body.locked};
} finally { clearTimeout(timer); }
'''.replace('CHUNKS', json.dumps([list(chunk) for chunk in chunks]))
       .replace('READ_ERROR', json.dumps(read_error))
       .replace('CANCEL', json.dumps(cancel))
       .replace('HEADERS', json.dumps({} if content_length is None else {'Content-Length': content_length})))['value']


@pytest.mark.parametrize('size', [4095, 4096, 4097])
def test_preview_stream_exact_byte_boundary(run_ts, size):
    payload = json.dumps(REQUEST).encode().ljust(size, b' ')
    result = _read_stream(run_ts, [payload[:31], payload[31:]])
    if size <= 4096:
        assert result.get('value') == REQUEST
        assert result['cancelled'] == 0
    else:
        assert (result.get('error'), result.get('status')) == ('request_too_large', 413)
        assert result['cancelled'] == 1
    assert result['locked'] is False


@pytest.mark.parametrize('content_length', [None, '1', '999999'])
def test_preview_stream_counts_chunks_and_stops_before_unread_tail(run_ts, content_length):
    result = _read_stream(run_ts, [b' '*2048, b' '*2048, b' ', b'unread'],
                          content_length=content_length)
    assert (result.get('error'), result.get('status')) == ('request_too_large', 413)
    assert (result['pulls'], result['cancelled'], result['locked']) == (3, 1, False)


@pytest.mark.parametrize('cancel', ['reject', 'pending'])
def test_preview_stream_cancel_cannot_override_or_delay_413(run_ts, cancel):
    result = _read_stream(run_ts, [b' '*4097, b'unread'], cancel=cancel)
    assert (result.get('error'), result.get('status')) == ('request_too_large', 413), result
    assert (result['pulls'], result['cancelled'], result['locked']) == (1, 1, False)


@pytest.mark.parametrize('chunks,read_error', [
    ([], False), ([b'{'], False), ([b'\xff'], False), ([b'{'], True),
])
def test_preview_stream_bad_body_is_422_and_releases_reader(run_ts, chunks, read_error):
    result = _read_stream(run_ts, chunks, read_error=read_error)
    assert (result.get('error'), result.get('status')) == ('invalid_request', 422), result
    assert result['locked'] is False


def test_preview_stream_absent_body_is_422(run_ts):
    result = run_ts("return await c.readPreviewRequest(new Request('http://localhost',{method:'POST'}));")
    assert (result['error'], result['status']) == ('invalid_request', 422)


@pytest.mark.parametrize('body,status', [
    ({'request_id':'saved-1'}, None), ({'request_id':'id','subject':'admin'}, 422),
    ({'request_id':'id','diff':'forged'}, 422), ({'request_id':'id','tenant':'globex'}, 422),
    ({'request_id':'id\n'}, 422), ({'request_id':'../id'}, 422), ({}, 422), (None, 422),
])
def test_prepare_request_accepts_only_saved_request_id(run_ts, body, status):
    result = run_ts("return c.readPreparationRequest(new Request('http://localhost',{method:'POST',body:"
                    + json.dumps(json.dumps(body)) + '}));')
    assert result.get('status') == status
    if status is None: assert result['value'] == body


@pytest.mark.parametrize('receipt,status', [
    ({'request_id':'saved-1','state':'CLAIMED','published':False}, None),
    ({'request_id':'saved-1','state':'SUCCEEDED','published':True}, 503),
    ({'request_id':'saved-1','state':'CLAIMED','published':False,'output':'private'}, 503),
    ({'request_id':'other','state':'CLAIMED','published':False}, 503),
])
def test_prepare_receipt_never_claims_publication_or_exposes_payload(run_ts, receipt, status):
    body = json.dumps(dict(ok=True, status=200, preparation=receipt))
    result = run_ts('return c.decodePreparation('+json.dumps(body)+',"saved-1");')
    assert result.get('status') == status
    if status is None: assert result['value'] == receipt


def test_prepare_unknown_subject_plan_stays_404(run_ts):
    result = run_ts('return c.decodePreparation(\'{"ok":false,"status":404,"error":"stored_plan_not_found"}\',"saved-1");')
    assert (result['error'],result['status']) == ('stored_plan_not_found',404)


def test_prepare_body_has_same_stream_limit(run_ts):
    result = run_ts("return c.readPreparationRequest(new Request('http://localhost',{method:'POST',body:' '.repeat(4097)}));")
    assert result['status'] == 413

STATUS = dict(request_id='saved-1',state='PREVIEW',published=False,
              expires_at='2099-01-01T00:00:00+00:00',expired=False)


@pytest.mark.parametrize('change,accepted',[
    ({},True),({'state':'CLAIMED'},True),
    ({'state':'CLAIMED','expires_at':'2000-01-01T00:00:00Z','expired':True},True),
    ({'request_id':'another'},False),({'state':'SUCCEEDED'},False),({'published':True},False),
    ({'expired':1},False),({'expired':'false'},False),({'claim_id':'private'},False),
    ({'output':'private'},False),({'expires_at':'2099-01-01'},False),
    ({'expires_at':'2099-01-01T00:00:00Z\n'},False),({'expires_at':None},False),
])
def test_status_decoder_rejects_forged_publication_and_private_fields(run_ts,change,accepted):
    observation={**STATUS,**change}
    body=json.dumps(dict(ok=True,status=200,observation=observation))
    result=run_ts('return c.decodeAttachmentStatus('+json.dumps(body)+',"saved-1");')
    if accepted:assert result['value']==observation
    else:assert result['error']=='invalid_planner_response'


@pytest.mark.parametrize('status,error',[(401,'session_required'),(403,'registry_write_forbidden'),
    (404,'stored_plan_not_found'),(409,'plan_changed_during_read'),(503,'plan_store_unavailable')])
def test_status_failures_preserve_http_meaning_without_returning_a_state(run_ts,status,error):
    body=json.dumps(dict(ok=False,status=status,error=error))
    result=run_ts('return c.decodeAttachmentStatus('+json.dumps(body)+',"saved-1");')
    assert result=={'error':error,'status':status}


@pytest.mark.parametrize('output',['{','x'*4097,'null'])
def test_status_decoder_rejects_unusable_responses(run_ts,output):
    result=run_ts('return c.decodeAttachmentStatus('+json.dumps(output)+',"saved-1");')
    assert result['error']=='invalid_planner_response'

AWS_CONNECTION = dict(REGISTRY_PLANNER_MODE='aws',
    REGISTRY_PLANNER_FUNCTION_ARN='arn:aws:lambda:ap-northeast-2:111111111111:function:planner',
    REGISTRY_PLANNER_ROLE_ARN='arn:aws:iam::111111111111:role/planner',
    REGISTRY_PLANNER_STORED_REQUESTS='1')


@pytest.mark.parametrize('override,enabled',[
    ({},True),({'REGISTRY_PLANNER_STORED_REQUESTS':None},False),
    ({'REGISTRY_PLANNER_STORED_REQUESTS':'true'},False),
    ({'REGISTRY_PLANNER_STORED_REQUESTS':'1\n'},False),
    ({'VERCEL':'1','VERCEL_ENV':'production'},True),
    ({'VERCEL':'1','VERCEL_ENV':'preview'},False),
    ({'VERCEL':'1'},False),({'REGISTRY_PLANNER_MODE':'unknown'},False),
    ({'REGISTRY_PLANNER_FUNCTION_ARN':'arn:aws:lambda:ap-northeast-2:111111111111:function:planner\n'},False),
    ({'REGISTRY_PLANNER_FUNCTION_ARN':'*'},False),
    ({'REGISTRY_PLANNER_ROLE_ARN':'arn:aws:iam::222222222222:role/planner'},False),
    ({'REGISTRY_PLANNER_ROLE_ARN':'arn:aws:iam::111111111111:role/planner\n'},False),
])
def test_preparation_ui_requires_exact_config_and_explicit_stored_lambda_opt_in(run_ts,override,enabled):
    env={k:v for k,v in {**AWS_CONNECTION,**override}.items() if v is not None}
    assert run_ts('return connection.preparationAvailable('+json.dumps(env)+');')['value'] is enabled


@pytest.mark.parametrize('missing',['REGISTRY_PLANNER_PYTHON','REGISTRY_PLANNER_LOCAL_REPO',
    'REGISTRY_PLANNER_LOCAL_USERS','REGISTRY_PLANNER_LOCAL_PLAN_ENDPOINT','REGISTRY_PLANNER_LOCAL_PLAN_TABLE',None])
def test_local_preparation_ui_requires_the_same_configuration_as_execution(run_ts,missing):
    env=dict(REGISTRY_PLANNER_MODE='local',REGISTRY_PLANNER_PYTHON='/python',
        REGISTRY_PLANNER_LOCAL_REPO='/repo',REGISTRY_PLANNER_LOCAL_USERS='/users',
        REGISTRY_PLANNER_LOCAL_PLAN_ENDPOINT='http://127.0.0.1:8000',REGISTRY_PLANNER_LOCAL_PLAN_TABLE='plans')
    if missing:env.pop(missing)
    assert run_ts('return connection.preparationAvailable('+json.dumps(env)+');')['value'] is (missing is None)
    env['VERCEL']='1'
    assert run_ts('return connection.preparationAvailable('+json.dumps(env)+');')['value'] is False


@pytest.mark.parametrize('operation',['preview','prepare','status'])
def test_invoke_payload_fixes_operation_subject_target_and_response_mode(run_ts,operation):
    payload=REQUEST if operation=='preview' else {'request_id':'saved-1'}
    result=run_ts('const cfg=connection.plannerConnection('+json.dumps(AWS_CONNECTION)+');'
        'const input=connection.registryInvokeInput(cfg,'+json.dumps(operation)+',"operator",'+json.dumps(payload)+');'
        'return {...input,Payload:JSON.parse(new TextDecoder().decode(input.Payload))};')['value']
    assert result==dict(FunctionName=AWS_CONNECTION['REGISTRY_PLANNER_FUNCTION_ARN'],InvocationType='RequestResponse',
        Payload=dict(operation=operation,subject='operator',request=payload))


@pytest.mark.parametrize('operation',['prepare','status'])
def test_stored_operation_cannot_bypass_ui_opt_in_by_direct_http_call(run_ts,operation):
    env={**AWS_CONNECTION,'REGISTRY_PLANNER_STORED_REQUESTS':'0'}
    result=run_ts('return connection.registryInvokeInput(connection.plannerConnection('+json.dumps(env)+'),'
        +json.dumps(operation)+',"operator",{request_id:"saved-1"});')
    assert result==dict(error='planner_not_configured',status=503)


@pytest.mark.parametrize('operation,payload',[
    ('prepare',{'request_id':'saved-1','subject':'admin'}),
    ('status',{'request_id':'saved-1','operation':'publish'}),
    ('preview',{**REQUEST,'path':'globex'}),('publish',{'request_id':'saved-1'}),
])
def test_invoke_construction_rejects_forged_fields_and_operations(run_ts,operation,payload):
    result=run_ts('return connection.registryInvokeInput(connection.plannerConnection('+json.dumps(AWS_CONNECTION)+'),'
        +json.dumps(operation)+',"operator",'+json.dumps(payload)+');')
    assert result==dict(error='invalid_request',status=422)


@pytest.mark.parametrize('function_error,http_status,payload,expected',[
    ('Unhandled',200,'{"ok":true,"status":200}', 'planner_invoke_failed'),
    (None,202,'{"ok":true,"status":200}', 'planner_invoke_failed'),
    (None,None,'{}','planner_invoke_failed'),(None,200,None,'invalid_planner_response'),
    (None,200,'x'*4097,'invalid_planner_response'),(None,200,[255],'invalid_planner_response'),
    (None,200,'{"ok":false,"status":403,"error":"registry_write_forbidden"}',None),
])
def test_saved_invoke_checks_envelope_utf8_and_bytes_before_decoding(run_ts,function_error,http_status,payload,expected):
    wire=('undefined' if payload is None else 'Uint8Array.from('+json.dumps(payload)+')' if isinstance(payload,list)
          else 'new TextEncoder().encode('+json.dumps(payload)+')')
    result=run_ts('return c.readStoredInvocation('+wire+','+json.dumps(function_error)+','+json.dumps(http_status)+');')
    if expected:assert result==dict(error=expected,status=503)
    else:assert result['value']==payload


@pytest.mark.parametrize('operation,key,observation',[
    ('prepare','preparation',dict(request_id='saved-1',state='CLAIMED',published=False)),
    ('status','observation',STATUS),
])
def test_saved_invoke_decodes_actual_lambda_business_envelope(run_ts,operation,key,observation):
    body=json.dumps(dict(ok=True,status=200,**{key:observation}))
    decoder='decodePreparation' if operation=='prepare' else 'decodeAttachmentStatus'
    result=run_ts('return c.'+decoder+'(c.readStoredInvocation(new TextEncoder().encode('+json.dumps(body)+'),undefined,200),"saved-1");')
    assert result['value']==observation


def test_real_lambda_client_has_single_attempt_and_configured_region(run_ts):
    result=run_ts('const client=transport.createPlannerClient(connection.plannerConnection('+json.dumps(AWS_CONNECTION)+'));'
        'try {return {attempts:await client.config.maxAttempts(),region:await client.config.region()};}'
        'finally {client.destroy();}')
    assert result['value']==dict(attempts=1,region='ap-northeast-2')
