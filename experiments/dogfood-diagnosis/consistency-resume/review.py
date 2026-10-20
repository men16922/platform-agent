"""Bind explicit full-response reviews to paired inputs and existing Scorecard."""
import json
from pathlib import Path
import sys

from src.agents.ai.deployment_evidence import digest
from src.agents.ai.eval_harness import GradeOutcome, Scorecard, Verdict
import hashlib


def review(folder):
    expected=json.loads((folder/'expectations.json').read_text())
    judgments=json.loads((folder/'semantic-reviews.json').read_text())
    cards={};rows=[]
    cases={arm:{r['id']:r for r in json.loads((folder/f'replay-{arm}/cases.json').read_text())} for arm in ['before','after']}
    assert set(cases['before'])==set(cases['after'])==set(expected['cases'])
    for arm in ['before','after']:
        score=Scorecard(outcomes={n:[] for n in ['paired_raw_input','bounded_frozen_tool','completion','semantic_review']})
        assert set(judgments[arm])==set(cases[arm])
        for cid,case in cases[arm].items():
            path=folder/f'replay-{arm}'/(cid+'.json');data=path.read_bytes();r=json.loads(data)
            same=case['raw']==cases['before'][cid]['raw']==cases['after'][cid]['raw'] and r['case_sha256']==digest(case)
            completion=r.get('outcome',{}).get('model_completion') or {}
            calls=r['replay_calls'];t=case['tool_result']['evidence']['target'];steps=r.get('outcome',{}).get('steps',[])
            bounded=(len(r['http_attempts'])==2 and all(a['status']==200 for a in r['http_attempts'])
                and calls==[{'tool':'describe_deployment','deployment':t['deployment'],'namespace':t['namespace']}]
                and len(steps)==1 and steps[0]['result']==case['tool_result'])
            for attempt in r['http_attempts']:
                assert {x['function']['name'] for x in attempt['request'].get('tools',[])}=={'describe_deployment'}
                assert not any(k in attempt['request'] for k in ['expected','criteria','review'])
            j=judgments[arm][cid]
            bound=(j['report_sha256']==hashlib.sha256(data).hexdigest() and j['quotes']
                   and all(q and q in completion.get('text','') for q in j['quotes']))
            assert bound,(arm,cid,'unbound semantic review')
            complete=completion.get('status')=='complete'
            for name,ok,why in [('paired_raw_input',same,'Exact paired raw Deployment/RS/Pod input and report binding'),
                ('bounded_frozen_tool',bounded,'One frozen describe, same target, two actual HTTP attempts and exact tool result'),
                ('completion',complete,'Provider completion; not correctness'),
                ('semantic_review',same and bounded and complete and j['status']=='pass',j['reason'])]:
                score.outcomes[name].append(GradeOutcome(name,'judge' if name=='semantic_review' else 'code',Verdict.PASS if ok else Verdict.FAIL,f'{cid}: {why}'))
            rows.append({'arm':arm,'id':cid,'report_sha256':hashlib.sha256(data).hexdigest(),
                'review':j,'seconds':r['seconds'],'usage':completion.get('token_usage'),'completion':completion.get('status')})
        cards[arm]=score
    return {'scope':expected['scope'],'reviewer':judgments['reviewer'],
        'scorecards':{arm:s.to_dict() for arm,s in cards.items()},
        'delta':cards['after'].delta(cards['before'].metrics()),'cases':rows,
        'limits':['Exploratory, adaptively inspected small local sample; not a held-out accuracy estimate.',
                  'Coding-assistant semantic review, not an independent expert or calibrated critic.',
                  'Production factory/router with only frozen describe; not full catalog selection or authenticated UI/live cluster.']}


if __name__=='__main__':
    directory=Path(sys.argv[1]);report=review(directory)
    with (directory/'paired-review.json').open('x') as f:f.write(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({a:s['metrics'] for a,s in report['scorecards'].items()},ensure_ascii=False))
