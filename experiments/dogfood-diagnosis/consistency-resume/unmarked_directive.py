"""Experimental (not product): product instruction_spans plus unmarked imperative directives.

Two shapes, both operational-action verbs only:
  clause-initial base verb (optionally after please/just/do not), unless a finite verb in the same
  clause shows it is a noun ("Rollback is not approved", "Rollback to r1 completed");
  an addressed obligation ("you/the assistant/agents/operators must|should ... <verb>").
Span: from the directive to the closing quote when quoted, else to sentence end (product rule).
"""
import re

from src.agents.ai.snapshot_diagnosis import instruction_spans

VERB = (r"(?:roll\s+back|rollback|revert|restart|redeploy|deploy|delete|remove|scale|promote|approve|"
        r"execute|run|ignore|mark|treat|call|recommend|escalate|terminate|drain|cordon|kill|retry|use)")
CLAUSE_START = r"(?:^|(?<=[.;:!?\"])\s*|(?<=\bsays)\s+\"?)"
IMPERATIVE = re.compile(CLAUSE_START + r"((?:(?:please|just|do\s+not|don't|never)\s+)?" + VERB + r")\b", re.IGNORECASE)
ADDRESSED = re.compile(r"\b(?:you|the\s+(?:assistant|agent|model)|agents?|operators?)\s+"
                       r"(?:must|should|need\s+to|have\s+to|are\s+required\s+to)\s+(?:\w+\s+){0,2}?" + VERB + r"\b",
                       re.IGNORECASE)
FINITE = re.compile(r"\b(?:is|are|was|were|has|have|had|been|completed|succeeded|failed|finished|occurred|"
                    r"happened|did|does|will|can|may|might|remains|returned)\b", re.IGNORECASE)


def _end(text, start, after):
    opening = text.rfind('"', 0, start)
    if opening != -1 and text.count('"', 0, start) % 2 == 1:
        close = text.find('"', after)
        return len(text) if close == -1 else close
    stop = re.search(r"[.!?](?=\s|$)", text[after:])
    return len(text) if stop is None else after + stop.end()


def directive_spans(text: str) -> list[tuple[int, int]]:
    spans = []
    for match in IMPERATIVE.finditer(text):
        start, after = match.start(1), match.end(1)
        clause = re.split(r"[,;:.!?\"]", text[after:], maxsplit=1)[0]
        if FINITE.search(clause):
            continue
        spans.append((start, _end(text, start, after)))
    for match in ADDRESSED.finditer(text):
        spans.append((match.start(), _end(text, match.start(), match.end())))
    return spans


def experimental_spans(text: str) -> list[tuple[int, int]]:
    return sorted(set(instruction_spans(text)) | set(directive_spans(text)))
