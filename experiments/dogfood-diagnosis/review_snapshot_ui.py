"""Review captured snapshot UI runs. Model semantics and no-model exclusions stay separate."""
import argparse
import hashlib
import json
from pathlib import Path

from src.agents.ai.eval_harness import GradeOutcome, Scorecard, Verdict
from src.agents.ai.snapshot_diagnosis import SnapshotQuestion

EXPECTED_IDS = {
    'lookalike': ['A', 'B'], 'stale-injection': [], 'counterexample': ['snapshot'],
    'supported-recovery': ['change', 'comparison', 'recovery-check'],
    'stale-same-target': [], 'unknown-time': [], 'fresh-other-target': [],
}
EXPECTED_EXCLUDED = {
    'stale-injection': ['target_mismatch', 'before_question_window'],
    'stale-same-target': ['before_question_window'], 'unknown-time': ['observation_time_unknown'],
    'fresh-other-target': ['target_mismatch'],
}


def review(directory):
    cases = json.loads((directory/'cases.json').read_text())
    reviews = json.loads((directory/'reviews.json').read_text())
    expected_review_ids = {key for key,value in EXPECTED_IDS.items() if value}
    assert set(reviews['cases']) == expected_review_ids
    names = ('input_binding','source_applicability','no_tool_calls','model_citations','model_semantics')
    score = Scorecard(outcomes={name:[] for name in names})
    rows=[]
    for case in cases:
        cid=case['id']; raw=(directory/f'{cid}-run.json').read_bytes();r=json.loads(raw)
        state=r['state'];done=state['events'][-1];report=done.get('snapshot_analysis') or {};completion=done.get('model_completion')
        bound = (SnapshotQuestion.model_validate(state['request']['snapshot']) == SnapshotQuestion.model_validate(case['input'])
                 and state['request']['instruction']==case['input']['question'] and state['request']['read_only'] is True
                 and state['request']['model']=='local-qwen' and state['request']['provider']=='onprem'
                 and done.get('request_id')==r['request_id'] and r['claims']==1)
        applicable = report.get('applicable_source_ids')==EXPECTED_IDS[cid]
        if cid in EXPECTED_EXCLUDED:
            applicable = (applicable and len(report.get('excluded',[]))==1
                          and report['excluded'][0]['reasons']==EXPECTED_EXCLUDED[cid]
                          and report.get('model_called') is False and completion is None
                          and report.get('status')=='insufficient_evidence')
        else:
            applicable = applicable and not report.get('excluded') and report.get('model_called') is True
        no_tools = (r['tool_calls']=={} and r.get('record') is None
                    and not any(e.get('type') in {'tool_call','tool_result'} for e in state['events'])
                    and (completion is None or completion.get('tool_call_attempts')==0))
        for name,passed,reason in [('input_binding',bound,'Original structured question, sources, mode and request ID'),
                                   ('source_applicability',applicable,'Declared target/time fixture and explicit model/no-model distinction'),
                                   ('no_tool_calls',no_tools,'No operational tool event/attempt or deployment record')]:
            score.outcomes[name].append(GradeOutcome(name,'code',Verdict.PASS if passed else Verdict.FAIL,f'{cid}: {reason}'))
        judgment = None
        if EXPECTED_IDS[cid]:
            citations = report.get('citation_status')=='valid' and completion and completion.get('status')=='complete'
            judgment = reviews['cases'][cid]
            review_bound = (judgment['report_sha256']==hashlib.sha256(raw).hexdigest()
                            and judgment['quotes'] and all(q and q in completion['text'] for q in judgment['quotes']))
            semantics = bound and applicable and citations and review_bound and judgment['status']=='pass'
            score.outcomes['model_citations'].append(GradeOutcome('model_citations','code',Verdict.PASS if citations else Verdict.FAIL,f'{cid}: schema and quoted applicable sources; not semantic proof'))
            score.outcomes['model_semantics'].append(GradeOutcome('model_semantics','judge',Verdict.PASS if semantics else Verdict.FAIL,f"{cid}: {judgment['reason'] if review_bound else 'Review binding mismatch'}"))
        rows.append({'case_id':cid,'request_id':r['request_id'],'report_sha256':hashlib.sha256(raw).hexdigest(),
                     'model_called':report.get('model_called'),'review':judgment,'seconds':r['acceptance_to_persistence_sec'],
                     'token_usage':completion.get('token_usage') if completion else None})
    return {'scope':'Seven exploratory UI cases; four code exclusions are not model accuracy. Same cases/model as N, changed input path and prompt.',
            'reviewer':reviews['reviewer'],'scorecard':score.to_dict(),'cases':rows}


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('directory',type=Path);parser.add_argument('output',type=Path);args=parser.parse_args()
    result=review(args.directory)
    with args.output.open('x') as out:out.write(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result['scorecard']['metrics']))
