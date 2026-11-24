"""Evaluate date-dependent thresholds after rule and scope facts are structured."""

from dataclasses import dataclass
from datetime import date
from operator import gt, le


COMPARISONS = {'>': gt, '<=': le}


@dataclass(frozen=True)
class ThresholdVersion:
    valid_from: date
    valid_through: date
    threshold: int
    evidence_id: str

    def __post_init__(self):
        if self.valid_from > self.valid_through or type(self.threshold) is not int or self.threshold < 0 or not self.evidence_id:
            raise ValueError('invalid threshold version')


@dataclass(frozen=True)
class ThresholdRule:
    comparison: str
    operative_event: str
    evidence_id: str
    versions: tuple[ThresholdVersion, ...]

    def __post_init__(self):
        evidence_ids = {self.evidence_id, *(version.evidence_id for version in self.versions)}
        if (self.comparison not in COMPARISONS or not self.operative_event or not self.evidence_id
                or not self.versions or len(evidence_ids) != len(self.versions) + 1):
            raise ValueError('invalid threshold rule')


def unresolved(reason):
    return {'action': 'unresolved', 'answer': None, 'evidence': [], 'branches': [], 'reason': reason}


def evaluate(rule, amount, first, last, *, scope_established, event_date=None):
    """Require full, unique coverage of the admitted dates before deciding."""
    if scope_established is not True:
        return unresolved('rule_outside_scope' if scope_established is False else 'scope_not_established')
    if type(amount) is not int or amount < 0:
        return unresolved('invalid_amount')
    if first > last:
        return unresolved('invalid_date_range')
    if event_date is not None:
        if not first <= event_date <= last:
            return unresolved('event_date_outside_range')
        first = last = event_date

    spans = [(max(first, version.valid_from), min(last, version.valid_through), version)
             for version in rule.versions if version.valid_from <= last and version.valid_through >= first]
    spans.sort(key=lambda item: item[0])
    next_day = first.toordinal()
    branches = []
    for start, end, version in spans:
        if start.toordinal() != next_day:
            return unresolved('overlapping_versions' if start.toordinal() < next_day else 'coverage_gap')
        branches.append({'from': start.isoformat(), 'through': end.isoformat(), 'amount': amount,
                         'threshold': version.threshold, 'comparison': rule.comparison,
                         'answer': COMPARISONS[rule.comparison](amount, version.threshold),
                         'evidence': [rule.evidence_id, version.evidence_id]})
        next_day = end.toordinal() + 1
    if next_day != last.toordinal() + 1:
        return unresolved('coverage_gap')

    evidence = sorted({label for branch in branches for label in branch['evidence']})
    answers = {branch['answer'] for branch in branches}
    if len(answers) == 1:
        return {'action': 'answer', 'answer': branches[0]['answer'], 'evidence': evidence, 'branches': branches}
    return {'action': 'ask_date', 'answer': None, 'evidence': evidence, 'branches': branches,
            'ask_event': rule.operative_event}
