#!/usr/bin/env python3
"""Exposed-template development material and cache-only outcome contract."""
import collections
import hashlib
import json

import query_determinacy_oracle_audit as oracle_audit
import query_determinacy_oracle_evaluate as evaluator
import query_determinacy_oracle_parser as answer_parser
import query_determinacy_oracle_run as oracle
import query_determinacy_paraphrase_branch_candidate as branch
import query_determinacy_world_extract_parser as extractor
import query_determinacy_world_paraphrase_material as paraphrase


def build():
    oracle_audit.audit()
    backgrounds = paraphrase.build()
    questions = oracle.inputs()
    result = []
    for bg in backgrounds:
        row = dict(bg, kind='extract', query='extract')
        result.append(row)
        group = [q for q in questions.values() if q['case'] == bg['case'] and q['condition'] == bg['condition']]
        if len(group) != 3:
            raise ValueError('question mapping mismatch')
        for q in group:
            lines = q['prompt'].splitlines()
            lines[1] = bg['prompt'].splitlines()[1]
            result.append({'id': q['id'] + '__paraphrase', 'kind': 'direct', 'case': q['case'],
                           'family': q['family'], 'condition': q['condition'], 'query': q['query'],
                           'style': bg['style'], 'background_id': bg['id'], 'expected': q['expected'],
                           'prompt': '\n'.join(lines)})
    if len(result) != 96 or len({x['id'] for x in result}) != 96 or len({x['prompt'] for x in result}) != 96:
        raise ValueError('bad planned items')
    return result


def cached_branches():
    archive = oracle.ROOT / 'docs/review/2026-11-15-query-determinacy-oracle-results-v1/source-archive.json'
    files = json.loads(archive.read_text(encoding='utf-8'))['files']
    if len(files) != 289 or len({x['path'] for x in files}) != 289:
        raise ValueError('invalid old source archive')
    for item in files:
        if hashlib.sha256(item['raw_utf8'].encode('utf-8')).hexdigest() != item['sha256']:
            raise ValueError('old source checksum mismatch')
    records = {r['id']: r for r in (json.loads(x['raw_utf8']) for x in files if '/records/' in x['path'])}
    inputs = oracle.inputs()
    if len(records) != 144 or set(records) != set(inputs):
        raise ValueError('old cache records mismatch')
    cache = {item['prompt']: records[item['id']]['output'] for item in inputs.values()
             if item['condition'] in ('single_a', 'single_b')}
    if len(cache) != 72:
        raise ValueError('old branch cache collision')
    return cache


def resolve(extract_output, direct_prompt, cache, complete=True):
    status, values = extractor.parse(extract_output, technical_complete=complete)
    if status == 'T':
        return {'code': 'T', 'reason': 'extraction_technical', 'values': None}
    if status != 'parsed':
        return {'code': 'X', 'reason': 'extraction_invalid', 'values': None}
    try:
        prompts = branch.branch_prompts(direct_prompt, values)
    except ValueError:
        return {'code': 'X', 'reason': 'branch_input_invalid', 'values': values}
    if any(prompt not in cache for prompt in prompts):
        return {'code': 'X', 'reason': 'branch_cache_miss', 'values': values}
    codes = [answer_parser.parse(cache[prompt]) for prompt in prompts]
    return {'code': answer_parser.combine(*codes), 'reason': 'cached_branches', 'values': values, 'branch_codes': codes}


def evaluate(items, records, failed):
    if set(items) != set(records) or not set(failed) <= set(items):
        raise ValueError('planned IDs and records differ')
    if any(records[key].get('id', key) != key for key in records):
        raise ValueError('record ID mismatch')
    cache = cached_branches()
    rows = []
    for item in items.values():
        if item['kind'] != 'direct':
            continue
        bg = item['background_id']
        combined = resolve(records[bg]['output'], item['prompt'], cache, complete=bg not in failed)
        direct = answer_parser.parse(records[item['id']]['output'], technical_complete=item['id'] not in failed)
        # Reference is consulted only after the pipeline output has been resolved.
        ref = item['expected']
        rows.append({'id': item['id'], 'background_id': bg, 'case': item['case'], 'family': item['family'],
                     'condition': item['condition'], 'query': item['query'], 'reference': ref,
                     'combined': combined, 'combined_class': evaluator.category(combined['code'], ref),
                     'direct': direct, 'direct_class': evaluator.category(direct, ref)})
    if len(rows) != 72:
        raise ValueError('wrong planned denominator')
    summary = {'by_condition': {}, 'by_condition_query': {}, 'extraction': {}}
    for cond in ('dual_sources', 'dual_alternatives'):
        group = [r for r in rows if r['condition'] == cond]
        summary['by_condition'][cond] = {
            'n': len(group), 'combined': dict(collections.Counter(r['combined_class'] for r in group)),
            'direct': dict(collections.Counter(r['direct_class'] for r in group)),
            'reason': dict(collections.Counter(r['combined']['reason'] for r in group)),
            'paired_direct_to_combined': dict(collections.Counter(r['direct_class'] + ' -> ' + r['combined_class'] for r in group))}
        for query in ('same_yes', 'same_no', 'split'):
            subgroup = [r for r in group if r['query'] == query]
            summary['by_condition_query'][cond + '/' + query] = {
                'n': len(subgroup), 'combined': dict(collections.Counter(r['combined_class'] for r in subgroup)),
                'direct': dict(collections.Counter(r['direct_class'] for r in subgroup))}
        extracted = [item for item in items.values() if item['kind'] == 'extract' and item['condition'] == cond]
        summary['extraction'][cond] = {'n': len(extracted), 'counts': dict(collections.Counter(
            extractor.score(records[item['id']]['output'], item['expected'], technical_complete=item['id'] not in failed)
            for item in extracted))}
    return rows, summary
