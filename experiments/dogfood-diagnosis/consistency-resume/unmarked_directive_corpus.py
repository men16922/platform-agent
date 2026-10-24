"""Score the frozen experimental detector on the predeclared corpus. usage: python -m ... dev|heldout"""
import json
import sys
from pathlib import Path

from .unmarked_directive import experimental_spans  # noqa: F401  (module path has a hyphen; run with -m)

ROOT = Path(__file__).resolve().parents[3]
D = ROOT / 'docs/evidence/diagnosis-20261020/unmarked-directive-probe'
split = sys.argv[1]
corpus = json.loads((D / 'corpus.json').read_text())[split]
rows = [{'class': cls, 'text': t, 'spans': [t[a:b] for a, b in experimental_spans(t)]}
        for cls, texts in corpus.items() for t in texts]
summary = {cls: f"{sum(bool(r['spans']) for r in rows if r['class'] == cls)}/{len(texts)} flagged"
           for cls, texts in corpus.items()}
(D / f'corpus-{split}.json').write_text(json.dumps({'split': split, 'summary': summary, 'rows': rows},
                                                   ensure_ascii=False, indent=1) + '\n')
print(summary)
for r in rows:
    if (r['class'] == 'P') != bool(r['spans']):
        print('MISS' if r['class'] == 'P' else 'FLAG', r['class'], r['text'], r['spans'])
