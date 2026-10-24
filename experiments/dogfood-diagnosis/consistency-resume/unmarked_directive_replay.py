"""Replay preserved injection-guard-sampled candidate drafts through validate_citations with the frozen
experimental spans in place of the product spans (refusal check only; model input is unchanged, so
this does not measure how annotating unmarked directives would change the model's answers)."""
import json
from pathlib import Path

from pydantic import ValidationError

from src.agents.ai import snapshot_diagnosis as sd
from .unmarked_directive import experimental_spans

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / 'docs/evidence/diagnosis-20261020/injection-guard-sampled'
OUT = ROOT / 'docs/evidence/diagnosis-20261020/unmarked-directive-probe'
product_spans = sd.instruction_spans


def verdict(draft, prepared, spans):
    sd.instruction_spans = spans
    try:
        sd.validate_citations(draft, prepared)
        return 'pass'
    except sd.RecoveryEvidenceError:
        return 'refused'
    except ValueError:
        return 'invalid'
    finally:
        sd.instruction_spans = product_spans


rows = []
for path in sorted(SRC.glob('candidate-*-s*.json')):
    row = json.loads(path.read_text())
    raw = (row['outcome'].get('model_completion') or {}).get('text', '')
    prepared = sd.prepare(sd.SnapshotQuestion.model_validate(row['request']))
    try:
        draft = sd.Diagnosis.model_validate_json(raw)
    except ValidationError:
        continue
    product, experimental = verdict(draft, prepared, product_spans), verdict(draft, prepared, experimental_spans)
    rows.append({'file': path.name, 'case': row['case_id'], 'seed': row['seed'], 'recovery': draft.recovery,
                 'product': product, 'experimental': experimental})
(OUT / 'replay.json').write_text(json.dumps(rows, ensure_ascii=False, indent=1) + '\n')
for r in rows:
    flag = '  <- changed' if r['product'] != r['experimental'] else ''
    print(f"{r['case']:29} s{r['seed']:<6} {r['recovery']:16} product={r['product']:8} experimental={r['experimental']}{flag}")
