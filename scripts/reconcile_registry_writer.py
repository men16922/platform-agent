#!/usr/bin/env python3
"""Offline diagnostic reconciliation. Exit 0 means consistent partial evidence only."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.agents.platform.writer_capture import _decode
from src.agents.platform.writer_reconciliation import reconcile_ref_read


def bounded_read(path,limit):
    with Path(path).open('rb') as stream:data=stream.read(limit+1)
    if len(data)>limit:raise ValueError('input_too_large')
    return data


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence');parser.add_argument('--review',required=True)
    parser.add_argument('--review-sha256',required=True);parser.add_argument('--as-of',required=True)
    parser.add_argument('--max-age-seconds',type=int,required=True)
    args=parser.parse_args(argv)
    try:
        evidence=_decode(bounded_read(args.evidence,262144))
        review=bounded_read(args.review,16384)
        result=reconcile_ref_read(review,evidence,expected_review_sha256=args.review_sha256,
            as_of=args.as_of,max_age_seconds=args.max_age_seconds)
    except (OSError,ValueError,TypeError,RecursionError):
        result={'scope':'offline_ref_read_reconciliation','verdict':'inconclusive','reason':'input_unavailable_or_invalid',
                'live_verified':False,'writer_success_verified':False,'retry_authorized':False}
    print(json.dumps(result,sort_keys=True))
    return 0 if result['verdict']=='consistent_partial' else 2


if __name__=='__main__':sys.exit(main())
