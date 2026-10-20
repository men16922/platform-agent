#!/usr/bin/env python3
"""Validate a P5-E execution config offline, or explicitly execute its reviewed flow.

Credentials come only from P5E_OPERATOR_TOKEN, P5E_APP_JWT and
P5E_INSTALLATION_TOKEN. This command never creates an App, installs it, mints a
credential, reads a PEM or creates a repository. --execute owns token revocation.
"""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.agents.platform.writer_github import GitHubChannel, GitHubWriterAdapter
from src.agents.platform.writer_attempt import _directory, inspect_attempt, run_once
from src.agents.platform.writer_capture import _decode


def read_config(path):
    with path.open('rb') as stream:raw=stream.read(65537)
    if len(raw)>65536:raise ValueError('config_too_large')
    return _decode(raw)


def revoke_owned_credential(root, installation):
    """Bootstrap failures still release the supplied token; never replay a revoke."""
    try:
        status,_,_=installation.get('/installation/repositories')
        if status==401:return 'OBSERVED_INVALID'
        if status!=200:return 'UNVERIFIED'
        directory=root/('credential-'+installation.fingerprint)
        directory.mkdir(mode=0o700,exist_ok=True)
        outcome=run_once(directory,operation='revoke_token',
                         send=lambda:installation.open('DELETE','/installation/token'))
        if outcome.get('state')=='BLOCKED':outcome=inspect_attempt(directory)
        if outcome.get('state')!='OBSERVED' or outcome.get('http_status')!=204:return 'UNVERIFIED'
        status,_,_=installation.get('/installation/repositories')
        return 'OBSERVED_INVALID' if status==401 else 'UNVERIFIED'
    except Exception:return 'UNVERIFIED'


def main(channel_factory=GitHubChannel):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--policy-root',type=Path,required=True)
    parser.add_argument('--state-root',type=Path,required=True)
    parser.add_argument('--diagnostic-prefix',type=Path)
    parser.add_argument('--error-details-dir',type=Path,
        help='Opt-in private directory for redacted untrusted PR 422 excerpts; synthetic experiments only')
    parser.add_argument('--execute',action='store_true')
    args=parser.parse_args()
    installation=None
    result={'state':'FAILED','reason':'invalid_execution_config','cleanup':'NOT_ATTEMPTED','live_verified':False}
    try:
        # A private journal must be usable before taking custody. Once accepted,
        # --execute owns this credential even if any later local validation fails.
        fd=_directory(args.state_root);os.close(fd)
        installation=channel_factory(os.environ['P5E_INSTALLATION_TOKEN'],identity='installation-token')
        config=read_config(args.config)
        if not isinstance(config,dict) or set(config)!={'expected_identity','mint_receipt'}:raise ValueError('invalid_config')
        operator=channel_factory(os.environ['P5E_OPERATOR_TOKEN'],identity='operator')
        app=channel_factory(os.environ['P5E_APP_JWT'],identity='app-jwt')
        adapter=GitHubWriterAdapter(args.state_root,config['expected_identity'],installation=installation,
            operator=operator,app=app,mint_receipt=config['mint_receipt'],policy_root=args.policy_root,
            error_detail_directory=args.error_details_dir)
        diagnostic=read_config(args.diagnostic_prefix) if args.diagnostic_prefix else None
        if not args.execute:
            # Construction checks local scope/config only. No network request here.
            result={'state':'CONFIG_VALID','execution_requested':False,'live_verified':False}
        else:
            review=adapter.prepare_review(diagnostic_prefix=diagnostic)
            result=adapter.execute(review)
    except Exception:
        pass  # Only the fixed result is emitted; exceptions may contain secret values.
    finally:
        if args.execute and installation is not None and result.get('cleanup')=='NOT_ATTEMPTED':
            result['cleanup']=revoke_owned_credential(args.state_root,installation)
    print(json.dumps(result,sort_keys=True))
    return 0 if result['state'] in ('CONFIG_VALID','CONSISTENT') else 1


if __name__=='__main__':raise SystemExit(main())
