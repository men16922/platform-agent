#!/usr/bin/env python3
"""Emit one JSON verdict for local P5-E evidence; never send remote requests."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.agents.platform.writer_evidence import judge


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate_json_key')
        result[key] = value
    return result


def reject_nonfinite(_value):
    raise ValueError('nonstandard_json_number')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence', type=Path)
    args = parser.parse_args()
    try:
        with args.evidence.open('rb') as stream:
            raw = stream.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise ValueError('oversize')
        result = judge(json.loads(raw, object_pairs_hook=unique_object,
                                  parse_constant=reject_nonfinite))
    except (OSError, ValueError, RecursionError):
        print('Cannot read a valid bounded evidence JSON document.', file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0 if result['verdict'] == 'supported' else 1


if __name__ == '__main__':
    raise SystemExit(main())
