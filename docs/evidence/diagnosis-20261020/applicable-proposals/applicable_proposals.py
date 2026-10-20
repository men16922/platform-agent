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
    prepared['applicability']={'stage':stage,'hypotheses':hypotheses,'checks':list(dict.fromkeys(checks)),
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
    schema['$defs']['Check']['properties']['kind']['enum']=allowed['checks']
    schema['$defs']['Check']['properties']['kind']['description']=json.dumps({k:CHECKS[k] for k in allowed['checks']})
    return schema


def validate(raw,prepared):
    proposal=original_validate(raw,prepared)
    allowed=prepared['applicability']
    for row in proposal.hypotheses:
        if row.kind not in allowed['hypotheses']:
            raise ValueError(f'inapplicable_hypothesis:{row.kind}')
        if 'current-revision' not in row.evidence:
            raise ValueError(f'current_revision_support_required:{row.kind}')
    for row in proposal.next_checks:
        if row.kind not in allowed['checks']:
            raise ValueError(f'inapplicable_check:{row.kind}')
        if row.kind=='observation_consistency':
            required={'observation-consistency'}
        elif row.kind in {'current_container_logs','previous_container_logs'}:
            required={'current-revision'}
        else:
            required={'current-revision','rollout-state','desired-images','investigation-stage'}
        if not set(row.evidence)&required:
            raise ValueError(f'applicable_observation_support_required:{row.kind}')
    return proposal
