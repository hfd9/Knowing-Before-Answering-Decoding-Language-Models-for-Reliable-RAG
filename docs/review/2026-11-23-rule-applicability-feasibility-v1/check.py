"""Replay authored applicability pairs without touching model or evaluation material."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

FOLDER = Path(__file__).resolve().parent
ROOT = FOLDER.parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from query_determinacy_rule_applicability import evaluate, normalize


def load(name):
    raw = (FOLDER / name).read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def bag(text):
    return Counter(ch for ch in text if ch.isalnum())


def summarize(rows, method):
    choices = [row[method]['final'] for row in rows]
    return {'cases': len(rows), 'unresolved': choices.count(None),
            'matches_author': sum(label == row['author_final'] for label, row in zip(choices, rows)),
            'wrong_determinate_or_split': sum(label is not None and label != row['author_final']
                                               for label, row in zip(choices, rows))}


def check():
    public, inputs_sha = load('cases.json')
    autonomous, pairs = {}, []
    for pair in public['pairs']:
        pid, kind, target = pair['id'], pair['kind'], pair['condition']
        left, right = (pair['variants'][variant] for variant in ('a', 'b'))
        pairs.append({'pair': pid, 'kind': kind, 'rephrases': pair.get('rephrases'),
                      'same_bag_of_characters': bag(left) == bag(right)})
        for variant, fact in pair['variants'].items():
            literal = normalize(kind, fact)
            extended = normalize(kind, fact, include_proxy=True)
            autonomous[pid, variant] = {
                'pair': pid, 'variant': variant, 'fact': fact,
                'initial_fact': literal, 'with_proxy_fact': extended,
                'initial': evaluate(kind, target, literal), 'with_proxy': evaluate(kind, target, extended),
            }

    reference, reference_sha = load('author-reference.json')
    for pair in public['pairs']:
        pid, kind, target = pair['id'], pair['kind'], pair['condition']
        for variant in pair['variants']:
            row = autonomous[pid, variant]
            gold = reference[pid][variant]
            row['author_final'] = gold['final']
            row['author_proof'] = gold['proof']
            row['given_normalized_fact'] = evaluate(kind, target, gold['normalization'])
            if row['given_normalized_fact']['final'] != gold['final']:
                raise ValueError('typed interpretation and written proof disagree')
    rows = list(autonomous.values())
    return {'public_sha256': inputs_sha, 'author_reference_sha256': reference_sha,
            'pair_checks': pairs, 'rows': rows,
            'metrics': {name: summarize(rows, name) for name in ('initial', 'with_proxy', 'given_normalized_fact')}}


if __name__ == '__main__':
    print(json.dumps(check(), ensure_ascii=False, sort_keys=True, indent=2))
