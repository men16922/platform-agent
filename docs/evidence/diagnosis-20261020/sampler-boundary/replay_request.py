"""Replay a recorded HTTP request body byte-for-byte to a proxy; print content hash + server cache stats."""
import hashlib
import json
import sys
import urllib.request
rec = json.load(open(sys.argv[1])); url = sys.argv[2]; label = sys.argv[3]
body = rec['http_attempts'][0]['request']
raw = urllib.request.urlopen(urllib.request.Request(url + '/v1/chat/completions', json.dumps(body).encode(),
                             {'Content-Type': 'application/json'}), timeout=600).read()
r = json.loads(raw); msg = r['choices'][0]['message']; text = msg.get('content') or ''
recorded = rec['outcome']['model_completion']['text']
print(json.dumps({'label': label, 'record': sys.argv[1].split('/')[-2] + '/' + sys.argv[1].split('/')[-1],
                  'content_sha256': hashlib.sha256(text.encode()).hexdigest()[:16],
                  'matches_record_text': text == recorded,
                  'cached_tokens': (r.get('usage') or {}).get('prompt_tokens_details', {}).get('cached_tokens'),
                  'prompt_tokens': (r.get('usage') or {}).get('prompt_tokens')}))
