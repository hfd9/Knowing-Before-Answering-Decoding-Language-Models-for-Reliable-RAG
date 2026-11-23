"""Exact category lookup for the explicit rule table in the two-case pilot."""
import re

QUERY = re.compile(r'按规则表，该零件是否适合([一-龥]+)？')
RULE = re.compile(r'([A-Za-z0-9][A-Za-z0-9_-]{0,63})((?:不)?适合[一-龥]+(?:，(?:不)?适合[一-龥]+)*)')
CLAUSE = re.compile(r'((?:不)?适合)([一-龥]+)')


def category_lookup(question, bound, sources, spans):
    """Return an answer only when each actual candidate has one explicit applicable rule."""
    if bound is None or len(bound) != 2 or len(set(bound)) != 2 or set(bound) != set(sources):
        return {'status': 'unresolved', 'reason': 'source_binding_failed', 'worlds': None}
    query = QUERY.fullmatch(question)
    if not query:
        return {'status': 'unresolved', 'reason': 'unsupported_question', 'worlds': None}

    rules = {}
    for evidence_id, span in spans.items():
        if not evidence_id.startswith('R'):
            continue
        row = RULE.fullmatch(span['text'])
        if not row:
            return {'status': 'unresolved', 'reason': 'unsupported_rule', 'worlds': None}
        code, clauses = row.groups()
        rules.setdefault(code, []).append((evidence_id, clauses))
    worlds = []
    for slot in bound:
        value = sources[slot]['value']
        rows = rules.get(value, ())
        if len(rows) != 1:
            return {'status': 'unresolved', 'reason': 'missing_or_ambiguous_rule_row', 'slot': slot, 'worlds': None}
        evidence_id, clauses = rows[0]
        applicable = []
        for clause in clauses.split('，'):
            predicate, attribute = CLAUSE.fullmatch(clause).groups()
            if attribute == query[1]:
                applicable.append('N' if predicate == '不适合' else 'Y')
        if len(applicable) != 1:
            return {'status': 'unresolved', 'reason': 'missing_or_ambiguous_attribute', 'slot': slot, 'worlds': None}
        worlds.append({'slot': slot, 'value': value, 'answer': applicable[0],
                       'evidence_ids': [slot, evidence_id]})
    return {'status': 'compared', 'worlds': worlds}
