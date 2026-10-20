"""Read-only App/bot author reconciliation, separate from writer success evidence.

An Issue's nullable performed_via_github_app is never filled from expectations.
The alternative proves an author account binding through independent GitHub GETs;
it does not prove the credential used for a particular request or PR file access.
"""
import re
from urllib.parse import quote

from src.agents.platform.writer_github import positive, require


def observe_pr_author(*, operator, app, repository, repository_id, app_id, number):
    """Observe one PR using the operator and existing App JWT; mint/write nothing."""
    require(operator.identity=='operator' and app.identity=='app-jwt','author_observer_identity_mismatch')
    require(isinstance(repository,str) and re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repository)
            and '..' not in repository,'invalid_author_repository')
    positive(repository_id);positive(app_id);positive(number)
    base='/repos/'+repository

    def app_identity():
        data=app.object('/app')
        owner=data.get('owner');slug=data.get('slug')
        require(type(data.get('id')) is int and data['id']==app_id
                and isinstance(owner,dict) and owner.get('login')==repository.split('/')[0]
                and isinstance(slug,str) and re.fullmatch(r'[A-Za-z0-9-]+',slug),'author_app_binding_mismatch')
        return {'id':data['id'],'slug':slug,'owner':owner['login']}

    observed_app=app_identity()
    repo=operator.object(base)
    require(type(repo.get('id')) is int and repo['id']==repository_id
            and repo.get('full_name')==repository and repo.get('private') is True,'author_repository_mismatch')
    path=base+'/pulls/'+str(number)
    pr=operator.object(path);issue=operator.object(base+'/issues/'+str(number))
    url='https://github.com/'+repository+'/pull/'+str(number)
    require(type(pr.get('number')) is int and pr['number']==number and pr.get('html_url')==url
            and type(issue.get('number')) is int and issue['number']==number
            and isinstance(issue.get('pull_request'),dict)
            and issue['pull_request'].get('url')=='https://api.github.com'+path,'author_pr_binding_mismatch')
    login=observed_app['slug']+'[bot]'
    bot_path='/users/'+quote(login,safe='')
    bot=operator.object(bot_path)
    require(type(bot.get('id')) is int and bot['id']>0 and bot.get('type')=='Bot'
            and bot.get('login')==login,'author_bot_lookup_mismatch')
    for data in (pr,issue):
        actor=data.get('user')
        require(isinstance(actor,dict) and type(actor.get('id')) is int and actor['id']==bot['id']
                and actor.get('type')=='Bot' and actor.get('login')==bot['login'],'author_account_mismatch')
    performed=issue.get('performed_via_github_app')
    if performed is not None:
        require(isinstance(performed,dict) and type(performed.get('id')) is int
                and performed['id']==observed_app['id'],'author_issue_app_conflict')
    require(app_identity()==observed_app,'author_app_changed_during_observation')
    return {'schema_version':1,'basis':'app_bot_user_lookup','app':observed_app,
            'repository':{'id':repo['id'],'full_name':repo['full_name']},
            'pull_request':{'number':pr['number'],'url':pr['html_url']},
            'bot':{'id':bot['id'],'login':bot['login'],'type':bot['type']},
            'issue_app_field':('missing' if 'performed_via_github_app' not in issue
                               else 'null' if performed is None else 'matching'),
            'sources':{'app':{'identity':'app-jwt','method':'GET','path':'/app','reads':2},
                       'repository':{'identity':'operator','method':'GET','path':base},
                       'pr':{'identity':'operator','method':'GET','path':path},
                       'issue':{'identity':'operator','method':'GET','path':base+'/issues/'+str(number)},
                       'bot':{'identity':'operator','method':'GET','path':bot_path}},
            'author_account_verified':True,'writer_success_verified':False}
