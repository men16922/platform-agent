"""Offline, read-only consistency of the four-permission diagnostic observations.

Inputs are untrusted evidence, not authentication or authorization. Even consistent
records retain the original execution failure and cannot promote writer success.
"""
import base64
from datetime import datetime, timezone
import hashlib
import json
import re
from urllib.parse import quote

from src.agents.platform.writer_capture import _decode
from src.agents.platform.writer_evidence import _blob, _exact_json, _snapshot, InvalidEvidence

PERMISSIONS={'contents':'read','metadata':'read','pull_requests':'write','single_file':'write'}
TARGET='platform/tenants/acme.yaml'
SIBLING='platform/tenants/globex.yaml'
OPS=('create_ref','write_target','write_sibling','create_pr','revoke_token')


def require(condition,reason):
    if not condition:raise InvalidEvidence(reason)


def instant(value):
    require(isinstance(value,str),'invalid_observation_time')
    parsed=datetime.fromisoformat(value)
    require(parsed.tzinfo is not None,'timezone_required')
    return parsed.astimezone(timezone.utc)


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def reconcile_ref_read(review_bytes, evidence, *, expected_review_sha256, as_of, max_age_seconds):
    """Deterministic historical evaluation. as_of/age are explicit; no network/files.

    max_age_seconds bounds the latest author/readback observation, not the age of
    historical writes. Delayed reconciliation is allowed only for identical refs.
    """
    result={'scope':'offline_ref_read_reconciliation','verdict':'inconclusive',
            'reason':'invalid_or_incomplete_evidence','live_verified':False,
            'writer_success_verified':False,'retry_authorized':False}
    try:
        result.update(_reconcile(review_bytes,evidence,expected_review_sha256,as_of,max_age_seconds))
    except InvalidEvidence as error:result['reason']=str(error)
    except (ValueError,TypeError,KeyError,AttributeError,RecursionError,OverflowError):pass
    return result


def _reconcile(raw,e,pinned,as_of,max_age):
    require(isinstance(raw,bytes) and len(raw)<=16384 and isinstance(pinned,str)
            and re.fullmatch(r'[a-f0-9]{64}',pinned) and hashlib.sha256(raw).hexdigest()==pinned,'review_digest_mismatch')
    r=_decode(raw);x=e['execution'];ops=e['operations'];m=e['mint'];o=e['operator_pr'];a=e['author'];ae=a['author_evidence']
    require(type(e['schema_version']) is int and e['schema_version']==1,'invalid_bundle_version')
    now=instant(as_of)
    require(type(max_age) is int and 0<max_age<=86400,'invalid_freshness_policy')
    start=instant(x['observed_at']);read_time=instant(o['observed_at']);author_time=instant(a['observed_at'])
    require(start<=read_time<=author_time<=now and (now-author_time).total_seconds()<=max_age,'observation_time_mismatch')
    ids=r['expected_identity'];repo=r['repository'];base='/repos/'+repo;branch=r['branch'];B=r['base_sha']
    require(set(ids)=={'app_id','installation_id','repository_id'} and all(type(v) is int and v>0 for v in ids.values()),'invalid_expected_identity')
    require(isinstance(repo,str) and re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repo),'invalid_repository')
    require(x['scope']==r['scope'] and x['repository']==repo and x['review_sha256']==pinned
            and _exact_json({k:x[k] for k in ids},ids),'execution_binding_mismatch')
    require(x['state']=='STOPPED' and x['failure']=={'stage':'create_pr','reason':'TypeError'},'original_execution_mismatch')
    control={'app_id':ids['app_id'],'installation_id':ids['installation_id'],'permissions':PERMISSIONS,
             'repository_selection':[ids['repository_id']],'single_file_paths':[TARGET]}
    require(_exact_json(r['permissions_after'],PERMISSIONS) and _exact_json(x['permissions'],PERMISSIONS)
            and _exact_json(x['credential_control'],control) and _exact_json(m['permissions'],PERMISSIONS)
            and _exact_json(m['repository_ids'],[ids['repository_id']]),'credential_scope_mismatch')
    require(isinstance(m['credential_fingerprint'],str) and re.fullmatch(r'[a-f0-9]{64}',m['credential_fingerprint']),'missing_credential_fingerprint')
    require(set(ops)==set(OPS) and set(x['attempts'])==set(OPS[:-1]),'operation_set_mismatch')
    require(len(r['requests'])==4,'review_requests_mismatch')
    last=start;attempt_ids=set();event_ids=set();statuses={}
    for index,op in enumerate(OPS):
        record=ops[op];intent=record['intent'];receipt=record['receipt'];event=record['event']
        attempt=x['revoke'] if op=='revoke_token' else x['attempts'][op]
        require(all(v['operation']==op for v in (intent,receipt,event,attempt)),'operation_binding_mismatch')
        aid=intent['attempt_id'];eid=event['event_id']
        require(isinstance(aid,str) and re.fullmatch(r'[a-f0-9]{32}',aid) and aid not in attempt_ids
                and isinstance(eid,str) and re.fullmatch(r'[a-f0-9]{32}',eid) and eid not in event_ids,'duplicate_or_invalid_attempt')
        attempt_ids.add(aid);event_ids.add(eid)
        require(receipt['attempt_id']==attempt['attempt_id']==aid
                and receipt['capture_event_id']==attempt['capture_event_id']==eid
                and attempt['state']=='OBSERVED' and event['transport']=='response'
                and type(event['http_status']) is int and _exact_json(attempt['http_status'],event['http_status']),'receipt_event_mismatch')
        issued=instant(intent['created_at']);observed=instant(event['observed_at'])
        require(last<=issued<=observed<=read_time and observed<instant(m['expires_at']),'attempt_time_mismatch')
        last=observed;statuses[op]=event['http_status']
        if op!='revoke_token':
            capture=record['capture']
            require(_exact_json(capture['attempt'],attempt) and _exact_json(capture['request'],r['requests'][index])
                    and _exact_json(capture['reply']['status'],event['http_status']),'capture_binding_mismatch')
    require(statuses['create_ref']==201 and statuses['write_target']==200 and statuses['create_pr']==201,'writes_not_observed')
    require(x['cleanup']=='OBSERVED_INVALID' and statuses['revoke_token']==204
            and type(x['revoked_token_get_status']) is int and x['revoked_token_get_status']==401,'cleanup_unverified')
    seed=_snapshot(x['before']['main'],'main')
    expected_seed={TARGET:{'mode':'100644','sha':r['requests'][1]['body']['sha']},SIBLING:{'mode':'100644','sha':r['requests'][2]['body']['sha']}}
    require(seed['commit']==seed['main']==B and seed['parents']==[] and seed['files']==expected_seed,'seed_mismatch')
    require(x['before']==x['protected_after'],'protected_refs_changed')
    require(_snapshot(x['branch_seed'],branch)=={**seed,'ref':branch},'branch_seed_mismatch')
    for key,ref in [('token_main_ref','main'),('token_new_ref',branch)]:
        require(_exact_json(x[key],{'identity':'installation-token','ref':ref,'sha':B,'status':200}),'installation_ref_read_mismatch')
    content=base64.b64decode(r['requests'][1]['body']['content'],validate=True)
    target_blob=_blob(content)
    require(target_blob==r['requests'][1]['expected_blob_sha'] and hashlib.sha256(content).hexdigest()==r['requests'][1]['content_sha256'],'target_content_mismatch')
    after=_snapshot(x['target_snapshot'],branch);head=after['commit']
    require(head!=B and after['parents']==[B] and after['main']==B
            and after['files']=={**expected_seed,TARGET:{'mode':'100644','sha':target_blob}},'target_tree_mismatch')
    require(ops['create_ref']['capture']['reply']['response']=={'ref':'refs/heads/'+branch,'sha':B}
            and ops['write_target']['capture']['reply']['response']=={'blob_sha':target_blob,'commit_sha':head},'write_response_mismatch')
    if 200<=statuses['write_sibling']<300 or x['sibling_snapshot']!=after:
        return {'verdict':'boundary_failure','reason':'sibling_write_or_tree_change'}
    require(statuses['write_sibling'] in (403,404)
            and ops['write_sibling']['capture']['reply']['permission_denial_verified'] is True
            and ops['write_sibling']['event']['message_class'] in ('integration_access_error','not_found'),'sibling_denial_unverified')
    require(x['final_snapshot']==x['branch_after']==after,'final_tree_changed')
    number=o['number'];require(type(number) is int and number>0,'invalid_pr_number')
    url='https://github.com/'+repo+'/pull/'+str(number)
    require(ops['create_pr']['capture']['reply']['response']=={'number':number,'url':url}
            and _exact_json(x['final_pr_numbers'],[number]) and _exact_json(x['pr_numbers'],[number]),'pr_response_mismatch')
    files=[{'filename':TARGET,'status':'modified','additions':1,'deletions':0,'sha':target_blob}]
    require(o['identity']=='operator' and o['url']==url and o['head_sha']==head and o['base_sha']==B
            and o['draft'] is True and o['merged'] is False and o['state']=='open'
            and type(o['pr_count']) is int and o['pr_count']==1 and _exact_json(o['files'],files),'operator_pr_mismatch')
    require(ae['basis']=='app_bot_user_lookup' and type(ae['schema_version']) is int and ae['schema_version']==1
            and type(ae['app']['id']) is int and ae['app']['id']==ids['app_id']
            and ae['app']['owner']==repo.split('/')[0]
            and _exact_json(ae['repository'],{'id':ids['repository_id'],'full_name':repo})
            and _exact_json(ae['pull_request'],{'number':number,'url':url})
            and ae['author_account_verified'] is True and ae['writer_success_verified'] is False,'author_scope_mismatch')
    bot=ae['bot'];slug=ae['app']['slug']
    require(isinstance(slug,str) and re.fullmatch(r'[A-Za-z0-9-]+',slug)
            and type(bot['id']) is int and bot['id']>0 and bot['login']==slug+'[bot]' and bot['type']=='Bot'
            and _exact_json(o['author'],bot) and _exact_json(o['issue_author'],bot),'author_account_mismatch')
    require(ae['issue_app_field']=='null' and o['performed_via_github_app_id'] is None,'issue_field_mismatch')
    sources={'app':{'identity':'app-jwt','method':'GET','path':'/app','reads':2},
             'repository':{'identity':'operator','method':'GET','path':base},
             'pr':{'identity':'operator','method':'GET','path':base+'/pulls/'+str(number)},
             'issue':{'identity':'operator','method':'GET','path':base+'/issues/'+str(number)},
             'bot':{'identity':'operator','method':'GET','path':'/users/'+quote(bot['login'],safe='')}}
    require(_exact_json(ae['sources'],sources),'author_source_mismatch')
    expected_refs={'main':B,x['before']['existing_diagnostic']['ref']:x['before']['existing_diagnostic']['commit'],branch:head}
    require(a['pr_unchanged'] is True and a['refs']==expected_refs and _exact_json(a['files'],files),'later_observation_changed')
    calls=[{k:src[k] for k in ('identity','method','path')} for src in sources.values()]+[{'identity':'app-jwt','method':'GET','path':'/app'}]
    calls += [sources['pr'],{'identity':'operator','method':'GET','path':base+'/pulls/'+str(number)+'/files?per_page=100'}]
    calls += [{'identity':'operator','method':'GET','path':base+'/git/ref/heads/'+quote(ref,safe='')} for ref in expected_refs]
    require(_exact_json(a['calls'],[{**c,'status':200} for c in calls])
            and type(a['write_requests']) is int and a['write_requests']==0
            and type(a['installation_token_mints']) is int and a['installation_token_mints']==0,'later_call_provenance_mismatch')
    return {'verdict':'consistent_partial','reason':'diagnostic_reconciled_with_evidence_gaps',
            'original_execution_state':x['state'],'original_failure':dict(x['failure']),
            'as_of':now.isoformat(),'author_observed_at':author_time.isoformat(),
            'execution_started_at':start.isoformat(),'last_attempt_observed_at':last.isoformat(),
            'review_sha256':pinned,'evidence_sha256':digest(e),'pr_number':number,
            'author_account':'consistent','operator_pr_files':'consistent','recorded_cleanup':'consistent',
            'gaps':['issue_app_field_null','installation_identity_pr_files_unobserved',
                    'historical_request_credential_not_independently_proven','offline_records_not_authenticated'],
            'automatic_branch_creation_verified':False,'tenant_read_isolation_verified':False}
