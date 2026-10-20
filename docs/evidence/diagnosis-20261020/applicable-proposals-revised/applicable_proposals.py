"""Experimental phase-aware validation over the existing proposal contract.

No runtime import or new tool. Raw source prose stays in the prepared evidence,
including injected instructions. Failed generations are preserved, not repaired.
Code-owned state and recovery are never supplied by a model proposal.
"""
import json

from proposal_contract import (CHECKS, HYPOTHESES, output_schema as original_schema,
                               prepare as original_prepare, validate as original_validate)


def prepare(tool_result):
    prepared=original_prepare(tool_result)
    facts=tool_result['evidence']
    investigation=facts.get('investigation')
    consistency=facts.get('observation_consistency')
    if not isinstance(investigation,dict) or not isinstance(consistency,dict):
        raise ValueError('Phase-aware proposals require newly normalized bound observations.')
    current=facts.get('current') or {};previous=facts.get('previous') or {}
    stage=investigation['stage'];hypotheses=[];checks=list(investigation['next_evidence'])
    if consistency['status']=='consistent' and investigation['failure_hypotheses_applicable']:
        pull=bool(set(current.get('waiting_reasons',[])) & {'ErrImagePull','ImagePullBackOff'})
        if pull:
            hypotheses=['image_reference','registry_access','network_path','workload_configuration']
        else:
            hypotheses=['network_path','dependency_health','workload_configuration']
            checks += ['dependency_signals','network_signals']
            if (previous.get('health_basis')=='kubernetes_readiness'
                    and current.get('template_sha256')!=previous.get('template_sha256')):
                hypotheses.append('application_change')
    prepared['evidence'] += [
        {'id':'observation-consistency','kind':'normalized_observations','paths':['observation_consistency'],
         'value':consistency,'original_sources':facts['sources']},
        {'id':'investigation-stage','kind':'normalized_observations','paths':['investigation'],
         'value':investigation,'original_sources':facts['sources']},
    ]
    messages=[s['id'] for s in prepared['evidence'] if s['kind']=='untrusted_status_text']
    previous_messages=[s['id'] for s in prepared['evidence'] if s['kind']=='untrusted_status_text'
                       and s['binding'].get('previous_terminated_state') is True]
    checks=list(dict.fromkeys(checks))
    support={kind:['current-revision','investigation-stage',*messages] for kind in checks}
    for kind in ('image_reference','registry_manifest'):
        if kind in support:support[kind]=['current-revision','desired-images',*messages]
    if 'service_health' in support:support['service_health']=['current-revision','investigation-stage','rollout-state']
    if 'observation_consistency' in support:support['observation_consistency']=['observation-consistency']
    if 'current_container_logs' in support:support['current_container_logs']=['current-revision']
    if 'previous_container_logs' in support:support['previous_container_logs']=['current-revision',*previous_messages]
    prepared['applicability']={'stage':stage,'hypotheses':hypotheses,'checks':checks,
        'hypothesis_support_ids':['current-revision',*messages], 'check_support_ids':support,
        'limits':['These are applicability constraints, not observed root causes or approval.',
                  'A prior termination supports requesting previous-attempt logs; availability and access are not verified.']}
    return prepared


def output_schema(prepared):
    schema=original_schema(prepared)
    allowed=prepared['applicability']
    if allowed['hypotheses']:
        field=schema['$defs']['Hypothesis']['properties']['kind']
        field['enum']=allowed['hypotheses']
        field['description']=json.dumps({k:HYPOTHESES[k] for k in allowed['hypotheses']})
    else:
        schema['properties']['hypotheses']['maxItems']=0
    schema['$defs']['Hypothesis']['properties']['evidence']['contains']={'enum':allowed['hypothesis_support_ids']}
    schema['$defs']['Hypothesis']['properties']['evidence']['uniqueItems']=True
    schema['$defs']['Check']['properties']['kind']['enum']=allowed['checks']
    schema['$defs']['Check']['properties']['kind']['description']=json.dumps({k:CHECKS[k] for k in allowed['checks']})
    schema['properties']['next_checks']['maxItems']=min(3,len(allowed['checks']))
    schema['$defs']['Check']['properties']['evidence']['uniqueItems']=True
    schema['$defs']['Check']['allOf']=[{'if':{'properties':{'kind':{'const':kind}},'required':['kind']},
        'then':{'properties':{'evidence':{'contains':{'enum':ids}}}}} for kind,ids in allowed['check_support_ids'].items()]
    return schema


def validate(raw,prepared):
    proposal=original_validate(raw,prepared)
    allowed=prepared['applicability']
    for row in proposal.hypotheses:
        if row.kind not in allowed['hypotheses']:
            raise ValueError(f'inapplicable_hypothesis:{row.kind}')
        if not set(row.evidence)&set(allowed['hypothesis_support_ids']):
            raise ValueError(f'current_revision_support_required:{row.kind}')
    for row in proposal.next_checks:
        if row.kind not in allowed['checks']:
            raise ValueError(f'inapplicable_check:{row.kind}')
        required=set(allowed['check_support_ids'][row.kind])
        if not set(row.evidence)&required:
            raise ValueError(f'applicable_observation_support_required:{row.kind}')
    return proposal
