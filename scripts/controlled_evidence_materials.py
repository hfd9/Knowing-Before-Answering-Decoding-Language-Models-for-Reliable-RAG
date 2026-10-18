"""Assemble explicitly authored evidence variants, with exact edit provenance."""

from collections import Counter
import difflib
import hashlib
import html
import json
from pathlib import Path
import random

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT/'prompts/controlled_evidence_pilot_v1.json'
SOURCE = ROOT/'runs/qwen2.5-3b-small/data/instances_val.jsonl'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def json_text(value):
    return json.dumps(value, ensure_ascii=False, indent=2)+'\n'


def write_new(path, content):
    path = Path(path)
    encoded = content.encode('utf-8')
    if path.exists():
        require(path.read_bytes() == encoded, f'Refuse to overwrite: {path}')
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(encoded)


def replace_once(text, old, new):
    require(old and text.count(old) == 1 and old != new, 'Edit must match exactly once and change text')
    return text.replace(old, new, 1)


def edits(before, after, slot):
    """Full Unicode offsets for every non-equal span, replayable without a model."""
    return [dict(doc_id=slot, before_start=i, before_end=j, after_start=k, after_end=l,
                 before=before[i:j], after=after[k:l])
            for tag, i, j, k, l in difflib.SequenceMatcher(None, before, after, autojunk=False).get_opcodes()
            if tag != 'equal']


def build(spec_path=SPEC, source_path=SOURCE):
    spec = read(spec_path)
    require(digest(source_path) == spec['source_val_sha256'], 'Source validation data hash differs')
    source = [json.loads(line) for line in Path(source_path).read_text().splitlines()]
    lookup = {r['id']: r for r in source}
    require(len(source) == 285 and len(lookup) == 285, 'Expected fixed val285')
    require(len(spec['units']) == 10 and len({u['base_id'] for u in spec['units']}) == 10, 'Expected10 unique bases')
    require(spec['conditions'] == dict(S='answer', I='refuse', C='conflict', D='answer'), 'Condition modes changed')
    require(sorted(Counter(s for pair in spec['target_slots_zero_based'] for s in pair).values()) == [4]*5,
            'Target slots must be balanced across ten bases')
    rows, judgments, provenance = [], [], []
    for number, unit in enumerate(spec['units'], 1):
        source_row = lookup[unit['base_id']+'_refuse']
        require(source_row['split'] == 'val', 'Only validation source allowed')
        slots = sorted(sorted(range(5), key=lambda i: (len(source_row['docs'][i]), i))[:3])
        distractors = [source_row['docs'][i] for i in slots]
        target_slots = spec['target_slots_zero_based'][number-1]
        require(len(set(target_slots)) == 2 and all(0 <= i < 5 for i in target_slots), 'Bad target slots')
        a, b = unit['target_a'], unit['target_b']
        require(unit['remove'] in a and unit['remove'] in b, 'Both supported clauses are required')
        variants = dict(S=(a, b),
                        I=(replace_once(a, unit['remove'], unit['replacement_a']),
                           replace_once(b, unit['remove'], unit['replacement_b'])),
                        C=(a, replace_once(b, unit['remove'], unit['opposing'])),
                        D=(replace_once(a, unit['control_old'], unit['control_new']), b))
        assembled = {}
        for condition, targets in variants.items():
            docs, iterator = [], iter(distractors)
            for slot in range(5):
                docs.append(targets[target_slots.index(slot)] if slot in target_slots else next(iterator))
            key = f'ce{number:02d}_{condition}'
            mode = spec['conditions'][condition]
            row = dict(id=key, original_id=unit['base_id'], source_split='val', split='val_development',
                       condition=condition, true_mode=mode, label=['answer','refuse','conflict'].index(mode),
                       question=unit['question'], docs=docs)
            rows.append(row)
            assembled[condition] = row
            citations = []
            if condition in ('S', 'D', 'C'):
                for slot, quote, role in [(target_slots[0], unit['remove'], 'support_or_conflict_side_1'),
                                          (target_slots[1], unit['opposing'] if condition == 'C' else unit['remove'],
                                           'conflict_side_2' if condition == 'C' else 'matching_support')]:
                    start = docs[slot].find(quote)
                    require(start >= 0, f'Quote absent: {key}')
                    citations.append(dict(doc_id=slot+1, quote=quote, start=start, end=start+len(quote), role=role))
            judgments.append(dict(id=key, semantic_mode=mode, required_facts=unit['required_facts'],
                                  missing_facts=[unit['missing_fact']] if condition == 'I' else [],
                                  conflicting_claims=[unit['remove'], unit['opposing']] if condition == 'C' else [],
                                  answer_if_supported=unit['supported_answer'] if condition in ('S','D') else None,
                                  reason=unit['review_'+condition.lower()], citations=citations,
                                  reviewer='current_coordinating_assistant_author_history_exposed',
                                  provenance=spec['authorship'], status='authored_development_judgment_not_independent_gold'))
        unit_edits = {}
        for condition in ('I','C','D'):
            changes = []
            for slot, (old, new) in enumerate(zip(assembled['S']['docs'], assembled[condition]['docs']), 1):
                changes += edits(old, new, slot)
            unit_edits[condition] = changes
        require({e['doc_id'] for e in unit_edits['I']} == {s+1 for s in target_slots}, 'I must change both target docs')
        require({e['doc_id'] for e in unit_edits['C']} == {target_slots[1]+1}, 'C must change only target B')
        require({e['doc_id'] for e in unit_edits['D']} == {target_slots[0]+1}, 'D must change only target A')
        provenance.append(dict(original_id=unit['base_id'], original_question=source_row['question'],
                               adapted_question=unit['question'], question_change=unit['question_change'],
                               distractor_source_id=source_row['id'], source_doc_slots=[i+1 for i in slots],
                               distractor_sha256=[hashlib.sha256(d.encode()).hexdigest() for d in distractors],
                               target_slots=[s+1 for s in target_slots], edits_from_S=unit_edits,
                               limitation='Two authored target passages + three complete shortest original refuse distractors. New scope/wording and lengths differ from original distribution; no world-truth certification.'))
    random.Random(spec['order_seed']).shuffle(rows)
    require(len(rows) == len({r['id'] for r in rows}) == 40, 'Expected40 unique inputs')
    require(Counter(r['condition'] for r in rows) == dict.fromkeys('SICD',10), 'Unbalanced conditions')
    return spec, rows, judgments, provenance


def review_html(rows, judgments):
    ratings = {r['id']: r for r in judgments}
    parts = ['<!doctype html><meta charset="utf-8"><title>同题证据开发材料</title>',
             '<style>body{max-width:1100px;margin:30px auto;font:16px/1.7 sans-serif}pre{white-space:pre-wrap}article{border-top:1px solid #bbb;padding:20px 0}</style>',
             '<h1>40条开发材料与显式判断</h1><p>合成目标证据，原验证干扰文档完整保留；有历史暴露的作者判断，不是独立金标准。</p>']
    for row in sorted(rows, key=lambda r: r['id']):
        rating = ratings[row['id']]
        parts += [f'<article><h2>{html.escape(row["id"])} / {rating["semantic_mode"]}</h2>',
                  '<p>'+html.escape(row['question'])+'</p>', '<p>'+html.escape(rating['reason'])+'</p>']
        for i, doc in enumerate(row['docs'],1):
            parts += [f'<h3>文档{i}</h3><pre>{html.escape(doc)}</pre>']
        parts.append('</article>')
    return '\n'.join(parts)+'\n'


def material_artifacts(rows, judgments, provenance):
    return {'inputs.json': json_text(rows), 'input_judgments.json': json_text(judgments),
            'edit_provenance.json': json_text(provenance), 'input_review.html': review_html(rows,judgments)}
