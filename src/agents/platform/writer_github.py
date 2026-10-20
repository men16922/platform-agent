"""Bounded GitHub request/observation adapters for the reviewed P5-E experiment.

No credential discovery, token minting, App creation or infrastructure mutation.
Callers supply three separately provisioned identities and the checked mint receipt.
Only the installation identity can be used by send(); operator reads are separate.
"""
from datetime import datetime, timezone
import hashlib
import ipaddress
import os
from pathlib import Path
import re
from urllib.error import HTTPError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from src.agents.platform.writer_capture import MAX_BODY, _decode
from src.agents.platform.writer_attempt import _directory, _read, _write_new
from src.agents.platform.writer_diagnostics import ErrorDetailJournal
from src.agents.platform.writer_evidence import LAB, TARGET, SIBLING, validate_stage
from src.agents.platform.writer_workflow import (
    CALL_KEYS, STAGES, RequestSpec, _copy, _digest, _policy_digest, _request, execute_workflow,
)


class GitHubObservationError(ValueError):
    """Fixed diagnostics only; never include exception text, credentials or bodies."""


def require(condition, reason='invalid_github_observation'):
    if not condition:raise GitHubObservationError(reason)


def oid(value):
    require(isinstance(value,str) and re.fullmatch(r'[0-9a-f]{40}',value) is not None)
    return value


def positive(value):
    require(type(value) is int and value > 0)
    return value


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


class GitHubChannel:
    """Production origin is fixed. The explicit local test constructor uses dummy tokens."""
    def __init__(self, token, *, identity):
        require(identity in ('operator','installation-token','app-jwt'),'invalid_identity')
        require(isinstance(token,str) and 0 < len(token) <= 8192
                and re.fullmatch(r'[A-Za-z0-9_.-]+',token) is not None,'invalid_credential')
        self._token=token;self.identity=identity;self._origin='https://api.github.com'
        self._opener=build_opener(ProxyHandler({}),_NoRedirect())

    @classmethod
    def local(cls, endpoint, *, identity):
        url=urlsplit(endpoint)
        try:loopback=ipaddress.ip_address(url.hostname).is_loopback
        except ValueError:loopback=False
        require(url.scheme=='http' and loopback and url.username is None and url.password is None
                and url.path in ('','/') and not url.query and not url.fragment,'invalid_local_endpoint')
        client=cls('local-'+identity,identity=identity);client._origin=endpoint.rstrip('/')
        return client

    @property
    def fingerprint(self):return hashlib.sha256(self._token.encode()).hexdigest()

    def open(self, method, path, body=None):
        parsed=urlsplit(path)
        require(method in ('GET','POST','PUT','DELETE') and path.startswith('/') and not path.startswith('//')
                and not parsed.scheme and not parsed.netloc and not parsed.fragment
                and '\\' not in path and '..' not in parsed.path
                and all(32 < ord(c) < 127 for c in path),'invalid_request_path')
        request=Request(self._origin+path,method=method,
            data=body.encode() if body is not None else None,
            headers={'Authorization':'Bearer '+self._token,'Accept':'application/vnd.github+json',
                     'Content-Type':'application/json','Accept-Encoding':'identity',
                     'X-GitHub-Api-Version':'2026-03-10','User-Agent':'platform-agent-p5e'})
        try:return self._opener.open(request,timeout=5)
        except HTTPError as error:return error  # captured as an HTTP observation; no retries
        except OSError:raise GitHubObservationError('github_transport_unavailable') from None

    def get(self,path):
        response=self.open('GET',path)
        try:
            status=response.status;headers=response.headers
            require(headers.get('Content-Encoding','identity')=='identity','encoded_response_refused')
            raw=response.read(MAX_BODY+1)
            require(len(raw)<=MAX_BODY,'github_response_too_large')
            data=_decode(raw) if raw else None
            return status,headers,data
        except (OSError,ValueError,TypeError,RecursionError):
            raise GitHubObservationError('unusable_github_response') from None
        finally:response.close()

    def object(self,path):
        status,headers,data=self.get(path)
        require(status==200 and isinstance(data,dict) and not headers.get('Link'),'incomplete_github_object')
        return data


class _RememberResponse:
    """M73 reads once; retain only normalized success/denial fields in memory."""
    def __init__(self,response,remember,diagnose=None):
        self.response=response;self.status=response.status;self.headers=response.headers;self.remember=remember
        self.diagnose=diagnose
    def getheaders(self):return list(self.headers.items())
    def read(self,size):
        if self.headers.get('Content-Encoding','identity')!='identity':raise OSError('encoded_response_refused')
        raw=self.response.read(min(size,MAX_BODY+1))
        if len(raw)<=MAX_BODY:
            try:data=_decode(raw) if raw else None
            except (KeyError,TypeError,ValueError,RecursionError):return raw
            if self.diagnose is not None:
                try:self.diagnose(self.status,self.headers,data)
                except Exception:raise OSError('diagnostic_capture_failed') from None
            try:self.remember(self.status,self.headers,data)
            except (KeyError,TypeError,ValueError,RecursionError):pass
        return raw
    def close(self):self.response.close()


class GitHubRepositoryReader:
    """Operator-only immutable Git observation, independently usable without an App."""
    def __init__(self, operator, repository):
        require(operator.identity=='operator' and isinstance(repository,str)
                and re.fullmatch(r'[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+',repository),'invalid_repository_reader')
        self.operator=operator;self.base='/repos/'+repository

    def _ref(self,branch):
        path=self.base+'/git/ref/heads/'+quote(branch,safe='')
        status,_,data=self.operator.get(path)
        if status==404:return None
        require(status==200 and isinstance(data,dict) and data.get('ref')=='refs/heads/'+branch
                and data.get('object',{}).get('type')=='commit','invalid_ref')
        return oid(data['object']['sha'])

    def snapshot(self,branch):
        main=self._ref('main');head=self._ref(branch)
        require(main is not None and head is not None,'snapshot_missing')
        commit=self.operator.object(self.base+'/git/commits/'+head)
        require(commit.get('sha')==head)
        parents=commit.get('parents');require(isinstance(parents,list) and len(parents)<=8)
        tree_sha=oid(commit['tree']['sha'])
        tree=self.operator.object(self.base+'/git/trees/'+tree_sha+'?recursive=1')
        require(tree.get('sha')==tree_sha and tree.get('truncated') is False
                and isinstance(tree.get('tree'),list) and len(tree['tree'])<=1000,'incomplete_tree')
        files={};seen=set()
        for entry in tree['tree']:
            path=entry.get('path')
            require(isinstance(path,str) and re.fullmatch(r'[A-Za-z0-9_.\-/]{1,256}',path)
                    and path not in seen and not path.startswith('/') and '..' not in path,'invalid_tree_path')
            seen.add(path)
            if entry.get('type')=='tree':
                require(entry.get('mode')=='040000');oid(entry['sha']);continue
            require(entry.get('type') in ('blob','commit') and entry.get('mode') in ('100644','100755','120000','160000'))
            files[path]={'sha':oid(entry['sha']),'mode':entry['mode']}
        require(self._ref(branch)==head and self._ref('main')==main,'snapshot_changed_during_read')
        return {'observer':'operator','complete':True,'ref':branch,'commit':head,'main':main,
                'parents':[oid(p['sha']) for p in parents],'files':files}

class GitHubWriterAdapter:
    def __init__(self, root, expected_identity, *, installation, operator, app,
                 mint_receipt, policy_root=None, error_detail_directory=None):
        self.root=Path(root);self.policy_root=LAB if policy_root is None else Path(policy_root)
        self.policy=_decode((self.policy_root/'review.json').read_bytes())
        require(self.policy.get('permissions')=={'single_file':'write','pull_requests':'write','metadata':'read'}
                and self.policy.get('single_file_paths')==[TARGET],'unsafe_writer_policy')
        self.ids=_copy(expected_identity)
        require(set(self.ids)=={'app_id','installation_id','repository_id'})
        for value in self.ids.values():positive(value)
        require((installation.identity,operator.identity,app.identity)==('installation-token','operator','app-jwt'))
        require(len({installation.fingerprint,operator.fingerprint,app.fingerprint})==3,'identities_not_separate')
        require(len({installation._origin,operator._origin,app._origin})==1,'mixed_api_origins')
        self.installation,self.operator,self.app=installation,operator,app
        self.repo=self.policy['repository'];self.base='/repos/'+self.repo
        self.reader=GitHubRepositoryReader(operator,self.repo)
        self.mint=_copy(mint_receipt);self.review=None;self.replies={};self.before={}
        # Receipt deliberately excludes token/JWT; it must come from the same mint operation.
        require(set(self.mint)=={'permissions','repository_ids','expires_at','credential_fingerprint'})
        require(self.mint['permissions']==self.policy['permissions']
                and _digest(self.mint['repository_ids'])==_digest([self.ids['repository_id']])
                and self.mint['credential_fingerprint']==installation.fingerprint,'mint_binding_mismatch')
        _policy_digest(self.policy_root)  # Offline validation includes every required fixture.
        self._check_expiry()
        self.error_details = None if error_detail_directory is None else ErrorDetailJournal(
            error_detail_directory, secrets=(installation._token, operator._token, app._token))

    def _check_expiry(self):
        try:expires=datetime.fromisoformat(self.mint['expires_at'])
        except (ValueError,TypeError):raise GitHubObservationError('invalid_mint_expiry') from None
        require(expires.utcoffset() is not None and expires>datetime.now(timezone.utc),'token_expired')

    def control(self):
        self._check_expiry()
        app=self.app.object('/app')
        require(type(app.get('id')) is int and app['id']==self.ids['app_id']
                and app.get('permissions')==self.policy['permissions']
                and app.get('owner',{}).get('login')==self.repo.split('/')[0],'app_identity_mismatch')
        installation=self.app.object('/app/installations/'+str(self.ids['installation_id']))
        paths=installation.get('single_file_paths')
        if paths is None:paths=[installation.get('single_file_name')]
        require(type(installation.get('id')) is int and installation['id']==self.ids['installation_id']
                and type(installation.get('app_id')) is int and installation['app_id']==self.ids['app_id']
                and installation.get('permissions')==self.policy['permissions']
                and paths==self.policy['single_file_paths'] and installation.get('suspended_at') is None
                and installation.get('repository_selection')=='selected'
                and installation.get('account',{}).get('login')==self.repo.split('/')[0],'installation_scope_mismatch')
        status,headers,data=self.installation.get('/installation/repositories?per_page=100')
        require(status==200 and not headers.get('Link') and isinstance(data,dict)
                and type(data.get('total_count')) is int and data['total_count']==1,'repository_selection_incomplete')
        repositories=data.get('repositories')
        require(isinstance(repositories,list) and len(repositories)==1)
        self._repository(repositories[0])
        return {'identity':'installation-token','status':200,'repository':self.repo,**self.ids,
                'permissions':self.mint['permissions'],'single_file_paths':paths,
                'repository_selection':[self.ids['repository_id']],
                'credential_fingerprint':self.installation.fingerprint}

    def _repository(self,data):
        require(type(data.get('id')) is int and data['id']==self.ids['repository_id']
                and data.get('full_name')==self.repo and data.get('private') is True,'repository_identity_mismatch')

    def _ref(self,branch):return self.reader._ref(branch)

    def snapshot(self,branch):return self.reader.snapshot(branch)

    def prepare_review(self, *, diagnostic_prefix=None):
        self._repository(self.operator.object(self.base))
        require(self.operator.object(self.base+'/actions/permissions').get('enabled') is False,'actions_not_disabled')
        control=self.control();seed=self.snapshot('main')
        result={'schema_version':1,'repository':self.repo,'expected_identity':self.ids,
                'credential_control':control,'seed':seed,'branch_origin':'app','selected_branch':self.policy['branch']}
        if diagnostic_prefix is not None:
            require(_digest(diagnostic_prefix.get('expected_identity'))==_digest(self.ids)
                    and diagnostic_prefix.get('repository')==self.repo
                    and diagnostic_prefix.get('seed_commit')==seed['commit'],'diagnostic_identity_mismatch')
            result.update(branch_origin='operator',selected_branch=self.policy['diagnostic_branch'],
                branch=_copy(diagnostic_prefix['branch']),branch_snapshot=self.snapshot(self.policy['diagnostic_branch']))
        stage='create_ref' if diagnostic_prefix is not None else 'preflight'
        require(validate_stage(result,stage,policy_root=self.policy_root)['verdict']=='stage_verified','unverified_review')
        self.review=_copy(result)
        return _copy(result)

    def _directory(self):
        r=self.review
        key=_digest({'repository':r['repository'],'identity':r['expected_identity'],
                     'base_commit':r['seed']['commit'],'branch':r['selected_branch'],'branch_origin':r['branch_origin']})
        return self.root/key

    def _history(self,stage):
        result=_copy(self.review)
        fd=_directory(self._directory())
        try:
            for operation in STAGES:
                if operation=='create_ref' and self.review['branch_origin']=='operator':continue
                if STAGES.index(operation)>STAGES.index(stage):break
                piece=_read(fd,operation+'.observation.json')
                result.update(piece)
        finally:
            os.close(fd)
        return result

    def send(self,spec):
        require(self.review is not None and isinstance(spec,RequestSpec))
        require(spec.operation in (*STAGES,'revoke_token')
                and spec==_request(self.review,spec.operation,self.policy_root),'unreviewed_request')
        def remember(status,headers,data):
            clean={}
            if status in (200,201) and isinstance(data,dict):
                if spec.operation=='create_ref':clean={'ref':data['ref'],'object':{'sha':oid(data['object']['sha'])}}
                elif spec.operation in ('write_target','write_sibling'):
                    clean={'commit_sha':oid(data['commit']['sha']),'blob_sha':oid(data['content']['sha'])}
                elif spec.operation=='create_pr':clean={'number':positive(data['number']),'url':data['html_url']}
            remaining=headers.get('X-RateLimit-Remaining','')
            denied=(status in (403,404) and isinstance(data,dict)
                    and data.get('message') in ('Resource not accessible by integration','Not Found')
                    and isinstance(remaining,str) and remaining.isdigit() and int(remaining)>0
                    and not headers.get('Retry-After'))
            self.replies[spec.operation]={'status':status,'response':clean,'denial_message_verified':denied}
        diagnose = None if self.error_details is None else lambda status,headers,data: self.error_details.record(
            operation=spec.operation,status=status,headers=headers,data=data)
        return _RememberResponse(self.installation.open(spec.method,spec.path,spec.body),remember,diagnose)

    def _pr(self,number):
        path=self.base+'/pulls/'+str(number)
        data=self.operator.object(path)
        issue=self.operator.object(self.base+'/issues/'+str(number))
        expected_url='https://github.com/'+self.repo+'/pull/'+str(number)
        require(positive(data.get('number'))==number and data.get('html_url')==expected_url
                and positive(issue.get('number'))==number and issue.get('pull_request',{}).get('url')=='https://api.github.com'+path
                and positive(issue.get('user',{}).get('id'))==positive(data.get('user',{}).get('id'))
                and issue.get('user',{}).get('type')=='Bot','pr_identity_mismatch')
        performed=issue.get('performed_via_github_app')
        require(isinstance(performed,dict) and type(performed.get('id')) is int
                and performed['id']>0,'pr_author_app_unavailable')
        author=performed['id']
        sides={}
        for key in ('head','base'):
            side=data[key];self._repository(side['repo'])
            sides[key]={'ref':side['ref'],'sha':oid(side['sha']),'repo':side['repo']['full_name']}
        response={'number':number,'url':expected_url,'author_app_id':author,**sides,
                  'draft':data['draft'],'merged':data['merged']}
        files_path=path+'/files?per_page=100'
        status,headers,items=self.installation.get(files_path)
        require(status==200 and not headers.get('Link') and isinstance(items,list)
                and type(data.get('changed_files')) is int and len(items)==data['changed_files']<=100,'incomplete_pr_files')
        files={'identity':'installation-token','method':'GET','path':files_path,'status':status,'complete':True,
               'items':[{key:item[key] for key in ('filename','status','additions','deletions','sha')} for item in items]}
        return response,files

    def observe(self,phase,stage):
        require(self.review is not None)
        if stage=='revoke_token':
            status,_,_=self.installation.get('/installation/repositories')
            return {'expected_identity':self.ids,'identity':'installation-token','method':'GET',
                    'path':'/installation/repositories','status':status}
        index=STAGES.index(stage);prior='preflight' if index==0 else STAGES[index-1]
        if phase=='before':
            evidence=_copy(self.review) if prior=='preflight' else self._history(prior)
            evidence['credential_control']=self.control()
            current=self.snapshot('main' if stage=='create_ref' else self.review['selected_branch'])
            if stage=='create_ref':require(self._ref(self.review['selected_branch']) is None,'branch_already_exists')
            if stage=='create_pr':
                query='?state=all&head='+quote(self.repo.split('/')[0]+':'+self.review['selected_branch'],safe='')+'&base=main&per_page=100'
                status,headers,pulls=self.operator.get(self.base+'/pulls'+query)
                require(status==200 and not headers.get('Link') and pulls==[],'pull_request_already_exists_or_unknown')
            self.before[stage]=_copy(current)
            return {'evidence':evidence,'current_snapshot':current}
        require(phase=='after')
        # A repeated final read (or a resumed run) uses the sanitized persisted history.
        if stage not in self.replies:
            result=self._history(stage)
            require(self.snapshot(self.review['selected_branch'])==result[CALL_KEYS[stage]]['after'],'final_snapshot_changed')
            if stage=='create_pr':
                response,files=self._pr(result['pull_request']['response']['number'])
                require(_digest(response)==_digest(result['pull_request']['response']) and _digest(files)==_digest(result['pull_request']['files']),'final_pr_changed')
            return result
        reply=self.replies[stage]
        evidence=_copy(self.review) if prior=='preflight' else self._history(prior)
        spec=_request(self.review,stage,self.policy_root);body=_decode(spec.body.encode())
        body.pop('message',None);body.pop('title',None)
        call={'identity':'installation-token','method':spec.method,'path':spec.path,'body':body,'status':reply['status']}
        if stage=='create_ref':
            exists=self._ref(self.review['selected_branch']) is not None
            call.update(response=reply['response'],observed_absent=not exists,main_sha=self._ref('main'))
            if not exists:
                call['denial_controls']={'token_valid':self.control()['status']==200,'target_exists':True,
                    'sha_matches':self.snapshot('main')==self.review['seed'],'rate_limit_excluded':reply['denial_message_verified']}
            piece={'branch':call,'branch_snapshot':self.snapshot(self.review['selected_branch']) if exists else None}
        else:
            call['before']=self.before[stage] if stage!='create_pr' else None
            if stage=='create_pr':call.pop('before')
            call['after']=self.snapshot(self.review['selected_branch'])
            if stage in ('write_target','write_sibling'):
                if reply['response']:call['response']=reply['response']
                if reply['status'] in (403,404):
                    target=TARGET if stage=='write_target' else SIBLING
                    call['denial_controls']={'token_valid':self.control()['status']==200,
                        'target_exists':target in call['before']['files'],
                        'sha_matches':call['before']['files'].get(target,{}).get('sha')==body['sha'],
                        'rate_limit_excluded':reply['denial_message_verified']}
            elif reply['status']==201:
                number=reply['response']['number']
                require(reply['response']['url']=='https://github.com/'+self.repo+'/pull/'+str(number))
                call['response'],call['files']=self._pr(number)
            piece={CALL_KEYS[stage]:call}
        evidence.update(piece)
        verdict=validate_stage(evidence,stage,policy_root=self.policy_root)
        if stage=='create_ref' and verdict['verdict']=='unsupported' and verdict['reason']=='app_branch_creation_denied':
            fd=_directory(self._directory())
            try:_write_new(fd,'branch-denial.json',{'expected_identity':self.ids,'repository':self.repo,
                'seed_commit':self.review['seed']['commit'],'branch':call})
            finally:os.close(fd)
        if verdict['verdict'] in ('stage_verified','supported','diagnostic_only'):
            fd=_directory(self._directory())
            try:_write_new(fd,stage+'.observation.json',piece)
            finally:
                    os.close(fd)
            self.replies.pop(stage)
        return evidence

    def execute(self, review):
        self.review=_copy(review)
        return execute_workflow(self.root,self.review,send=self.send,observe=self.observe,policy_root=self.policy_root)
