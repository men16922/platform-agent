#!/usr/bin/env python3
"""Sanitize a supplied HTTP observation from stdin into a private local journal."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.agents.platform.writer_capture import ResponseJournal, _decode, OPERATIONS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', required=True, type=Path)
    parser.add_argument('--operation', required=True, choices=sorted(OPERATIONS))
    args = parser.parse_args()
    try:
        raw = sys.stdin.buffer.read(128 * 1024 + 1)
        if len(raw) > 128 * 1024:
            raise ValueError('oversize')
        data = _decode(raw)
        if (not isinstance(data, dict) or set(data) != {'status', 'headers', 'body', 'transport'}
                or not isinstance(data['body'], (str, type(None)))):
            raise ValueError('invalid_input')
        body = data['body'].encode('utf-8') if isinstance(data['body'], str) else None
        record = ResponseJournal(args.directory).record(operation=args.operation, status=data['status'],
                    headers=data['headers'], body=body, transport=data['transport'])
    except (OSError, ValueError, TypeError, RecursionError):
        print('Cannot capture a valid bounded observation in a private journal.', file=sys.stderr)
        return 2
    print(json.dumps(record, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
