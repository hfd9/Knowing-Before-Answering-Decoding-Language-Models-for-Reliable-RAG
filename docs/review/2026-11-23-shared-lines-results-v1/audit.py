"""Reconcile the sealed line-output rerun and compute a separate numeric diagnostic."""
from collections import Counter
from datetime import datetime
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'scripts'))
import query_determinacy_shared_lines_run as live
from query_determinacy_shared_lines import merge, parse

RUN = live.RUN
ANALYSIS = RUN.with_name('qwen2.5-3b-query-determinacy-shared-lines-analysis-v1')
EXPECTED_SEAL = 'e7d2827b25f92bf9a125eb1ce62839f119d410fe904277c70e32b506c4390b83'
FENCED_JSON = re.compile(r'```json\n([^\n]+)\n```')
NUMBER = r'(0|[1-9][0-9]{0,8})'
SOURCE = re.compile(r'来源[甲乙]写：这次校准的读数是' + NUMBER + r'([一-龥]+)。')
QUESTION = re.compile(r'该次校准读数是否(超过|低于)' + NUMBER + r'([一-龥]+)？')


def diagnostic_extraction(raw, domain):
    """Remove exactly one complete JSON fence for a separate offline counterfactual."""
    match = FENCED_JSON.fullmatch(raw.replace('\r\n', '\n').removesuffix('\n'))
    return live.base.extract.parse(match[1] if match else raw, domain)


def compare_numeric(question, values, source_spans):
    """Use only public source spans, the question and actual extraction candidates."""
    query = QUESTION.fullmatch(question)
    if query is None or values is None or len(values) != 2 or len(set(values)) != 2:
        return {'status': 'unresolved', 'final': None}
    predicate, threshold, unit = query.groups()
    sources = {}
    for label, span in source_spans.items():
        match = SOURCE.fullmatch(span['text'])
        if match is None or match[2] != unit or match[1] in sources:
            return {'status': 'unresolved', 'final': None}
        sources[match[1]] = label
    if set(sources) != set(values):
        return {'status': 'unresolved', 'final': None}
    worlds = []
    for value in values:
        yes = int(value) > int(threshold) if predicate == '超过' else int(value) < int(threshold)
        worlds.append({'value': value, 'answer': 'Y' if yes else 'N', 'source_id': sources[value]})
    return {'status': 'compared', 'final': merge([w['answer'] for w in worlds]), 'worlds': worlds}


def audit():
    seal_raw = (ANALYSIS / 'seal.json').read_bytes()
    hash_bytes = live.base.sha
    if hash_bytes(seal_raw) != EXPECTED_SEAL:
        raise ValueError('seal digest mismatch')
    seal = json.loads(seal_raw)
    score_raw = (ANALYSIS / 'score.json').read_bytes()
    score = json.loads(score_raw)
    if score['seal_sha256'] != EXPECTED_SEAL:
        raise ValueError('score is not bound to seal')
    source_hashes = {}

    def match_source(path, frozen):
        contents = (RUN / path).read_bytes()
        if json.loads(contents) != frozen:
            raise ValueError(f'live journal differs from seal: {path}')
        source_hashes[path] = hash_bytes(contents)

    for key in ('manifest', 'public'):
        match_source(f'{key}.json', seal[key])
    for index, preflight in enumerate(seal['device_preflights']):
        match_source(f'preflights/{index:04}.json', preflight)

    rows, counts, candidates = [], Counter(), {}
    cases = {case['id']: case for case in seal['public']['cases']}
    eos_ids = seal['manifest']['extra']['environment']['eos_token_ids']
    for index, entry in enumerate(seal['entries']):
        attempt, record = entry['attempt'], entry['record']
        match_source(f'attempts/{index:04}.json', attempt)
        match_source(f'records/{index:04}.json', record)
        counts[record['status']] += 1
        actual_eos = bool(record.get('generated_token_ids') and record['generated_token_ids'][-1] in eos_ids)
        row = {key: attempt[key] for key in ('index', 'case', 'question', 'kind', 'branch')}
        row.update({key: record[key] for key in ('status', 'output', 'input_tokens', 'output_tokens', 'elapsed_seconds')},
                   eos=actual_eos)
        domain = cases[row['case']]['domain']

        if row['kind'] == 'extract':
            actual = live.base.extract.parse(row['output'], domain, row['status'] == 'complete')
            alternative = diagnostic_extraction(row['output'], domain)
            if actual != {k: v for k, v in score['extractions'][row['case']].items() if k != 'matches_reference'}:
                raise ValueError('extraction recheck differs')
            row.update(frozen_extraction=actual, fenced_extraction_diagnostic=alternative)
            candidates[row['case']] = actual['values'], alternative['values']
        elif row['status'] == 'complete':
            try:
                parse(row['output'], domain, single_world=row['kind'] == 'branch')
            except ValueError as error:
                row['frozen_format_error'] = str(error)
            # Collect only visible fields, without treating malformed rows as scored.
            row['visible_world_labels'] = re.findall(r'(?m)^W=([^|\n]+)\|([YN])\|', row['output'])
            final = re.findall(r'(?m)^F=([YNU])$', row['output'])
            row['visible_final'] = final[0] if len(final) == 1 else None
        rows.append(row)

    # Finish the numerical comparison before connecting any answer labels.
    baselines = []
    for cid, case in cases.items():
        if case['domain'] != 'integer':
            continue
        spans = seal['manifest']['extra']['evidence_map'][cid]
        for question in case['questions']:
            entry = {'case': cid, 'question': question['id'], 'text': question['text']}
            for key, values in zip(('as_run', 'fence_removed_counterfactual'), candidates[cid]):
                entry[key] = compare_numeric(question['text'], values, spans)
            baselines.append(entry)

    reference = {(row['case'], row['question']): row['reference'] for row in score['rows']}
    for result in baselines:
        expected = reference[result['case'], result['question']]
        result['reference'] = expected
        for variant in ('as_run', 'fence_removed_counterfactual'):
            baseline = result[variant]
            baseline['matches_author_reference'] = (baseline['final'] == expected['final']
                and [w['answer'] for w in baseline['worlds']] == expected['world_answers']
                if baseline['status'] == 'compared' else None)

    for summary in score['method_totals'].values():
        if summary['planned'] != 6 or summary['readable'] != 0 or summary['unresolved'] != 6:
            raise ValueError('unexpected frozen route totals')
    first_device = seal['device_preflights'][0]
    elapsed = (datetime.fromisoformat(seal['entries'][-1]['record']['completed_at'])
               - datetime.fromisoformat(first_device['checked_at'])).total_seconds()
    return {'seal_sha256': EXPECTED_SEAL, 'score_sha256': hash_bytes(score_raw),
            'source_sha256': source_hashes, 'slot_counts': counts,
            'actual_eos': sum(row['eos'] for row in rows),
            'actual_input_tokens': sum(row['input_tokens'] or 0 for row in rows),
            'actual_output_tokens': sum(row['output_tokens'] or 0 for row in rows),
            'actual_call_seconds': sum(row['elapsed_seconds'] for row in rows if row['status'] == 'complete'),
            'preflight_to_last_slot_seconds': elapsed,
            'device': {k: v for k, v in first_device['device'].items() if k != 'gpu_uuid'},
            'frozen_score': score, 'slots': rows, 'numeric_diagnostic': baselines}


if __name__ == '__main__':
    print(json.dumps(audit(), ensure_ascii=False, sort_keys=True, indent=2))
