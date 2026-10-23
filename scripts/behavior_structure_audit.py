"""Reproduce a source-bound structural comparison and draft examples; stdlib only.

No collection/model/probe entry point. build writes only new named draft artifacts;
verify compares them byte for byte and leaves all source runs unchanged.
"""
import argparse
from collections import Counter
import csv
import hashlib
import io
import itertools
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'docs/records/2026-10-23-behavior-structure-audit'
DESIGN = 'prompts/behavior_relation_attachment_design_v1.json'
MANUAL = 'prompts/behavior_relation_attachment_audit_v1.json'
OLD = 'docs/records/2026-10-21-insufficient-answer-audit.json'
BEHAVIOR = 'docs/records/2026-10-21-semantic-transfer-exploratory-behavior-cells.csv'
TRANSFER = 'runs/qwen2.5-3b-semantic-transfer-exploratory-v5-v1'
BINDING = 'runs/qwen2.5-3b-behavior-binding-v1'
PATTERN = re.compile(r'The (access code|inspection code) assigned to Unit (U-\d{3}) is (K-\d{5})\. Unit (U-\d{3}) has a ledger entry\.')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read(path):
    return json.loads((ROOT / path).read_text())


def sha(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def dump(obj):
    return json.dumps(obj, ensure_ascii=False, indent=2) + '\n'


def csv_text(rows, columns):
    buf = io.StringIO(newline='')
    writer = csv.DictWriter(buf, fieldnames=columns)
    writer.writeheader()
    writer.writerows({k: row[k] for k in columns} for row in rows)
    return buf.getvalue()


def preservation():
    paths = read('docs/records/2026-10-21-probe-calibration-diagnostic-preserved.json')
    require(len(paths) == 1132, 'Historical preservation inventory differs')
    for path, digest in read('docs/records/2026-10-21-probe-calibration-diagnostic-run-hashes.json').items():
        require(path not in paths or paths[path] == digest, 'Conflicting source inventories')
        paths[path] = digest
    seal = read('docs/records/2026-10-21-semantic-transfer-exploratory-retrain-fit-seal.json')
    require(seal['fit_attempts'] == 1 and seal['remaining_original_design_fits'] == 0,
            'Original fit budget differs')
    for path, digest in seal['files'].items():
        require(path in paths and paths[path] == digest, 'Fit file not preserved: ' + path)
    for path, digest in paths.items():
        require(sha(path) == digest, 'Historical source changed: ' + path)
    return paths


def validate_samples(samples, worlds, design):
    """Parse the displayed fact separately from metadata and check compatible worlds."""
    require(len(samples) == len({r['id'] for r in samples}) == 16, 'Missing/duplicate samples')
    specs = {s['id']: s for s in design['example_scenarios']}
    expected = {f'{sid}_{cell}_{variant}' for sid in specs for cell in design['cells']
                for variant in ('v1', 'v2')}
    require({r['id'] for r in samples} == expected, 'Sample grid differs')
    require(len(worlds) == 12, 'Wrong number of insufficient world pairs')
    wmap = {w['id']: w['worlds'] for w in worlds}
    require(len(wmap) == len(worlds), 'Duplicate world ID')
    insufficient_ids = set()
    for row in samples:
        spec = specs[row['scenario']]
        roles = design['cells'][row['cell']]
        target, other = spec['target'], spec['other']
        query = spec['queried_attribute']
        candidate = spec[row['variant']]
        require(len(row['documents']) == 5, 'Wrong document count')
        require(row['question'] == design['question_template'].format(**spec), 'Question changed')
        matches = [(i, PATTERN.fullmatch(d)) for i, d in enumerate(row['documents'])]
        matches = [(i, m) for i, m in matches if m is not None]
        require(len(matches) == 1 and matches[0][0] == spec['candidate_slot'] - 1,
                'Code assignment missing or in wrong slot')
        attr, owner, value, nonowner = matches[0][1].groups()
        require({owner, nonowner} == {target, other} and owner != nonowner,
                'Entity roles malformed')
        require(owner == (target if roles['owner'] == 'target' else other)
                and attr == (query if roles['attribute'] == 'queried' else spec['alternative_attribute'])
                and value == candidate, 'Displayed fact/role mismatch')
        displayed = '\n'.join([row['question']] + row['documents'])
        require(re.findall(r'K-\d{5}', displayed) == [candidate], 'Extra code/witness leakage')
        for other_code in (spec['v1'], spec['v2'], spec['witness_alternative']):
            if other_code != candidate:
                require(other_code not in displayed, 'Non-displayed value leaked')
        question_supported = owner == target and attr == query
        require(question_supported == (row['cell'] == 'TQ'), 'Unexpected supported cell')
        if question_supported:
            require(row['id'] not in wmap, 'Sufficient row incorrectly has I worlds')
        else:
            insufficient_ids.add(row['id'])
            pair_worlds = wmap.get(row['id'], [])
            require(len(pair_worlds) == 2, 'Insufficient row lacks two worlds')
            expected_keys = set(itertools.product((target, other),
                                  (query, spec['alternative_attribute'])))
            parsed_worlds = []
            for assignments in pair_worlds:
                actual = {(a['entity'], a['attribute']): a['value'] for a in assignments}
                require(len(assignments) == len(actual) == 4 and set(actual) == expected_keys,
                        'World not a complete function on four pairs')
                require(actual[(owner, attr)] == candidate, 'World contradicts displayed fact')
                require(all(re.fullmatch(r'K-\d{5}', v) for v in actual.values()), 'Invalid code')
                parsed_worlds.append(actual)
            left, right = parsed_worlds
            changed = {key for key in left if left[key] != right[key]}
            require(changed == {(target, query)}, 'Worlds must differ only on queried target')
            require({left[(target, query)], right[(target, query)]}
                    == {candidate, spec['witness_alternative']}, 'Wrong two target assignments')
    require(set(wmap) == insufficient_ids, 'Orphan or missing worlds')
    return dict(exact_inputs=16, sufficient=4, insufficient=12,
                world_pairs=12, complete_worlds=24, declared_fact_slots=80)


def examples(design):
    rows, worlds = [], []
    for spec in design['example_scenarios']:
        target, other = spec['target'], spec['other']
        for cell, roles in design['cells'].items():
            for variant in ('v1', 'v2'):
                attr = spec['queried_attribute'] if roles['attribute'] == 'queried' else spec['alternative_attribute']
                owner = target if roles['owner'] == 'target' else other
                nonowner = other if owner == target else target
                value = spec[variant]
                docs = [s.format(**spec) for s in design['background_templates_in_order']]
                docs.insert(spec['candidate_slot'] - 1, design['candidate_document_template'].format(
                    attribute=attr, owner=owner, nonowner=nonowner, candidate=value))
                key = f"{spec['id']}_{cell}_{variant}"
                rows.append(dict(id=key, scenario=spec['id'], cell=cell, variant=variant,
                    question=design['question_template'].format(**spec), documents=docs))
                if cell != 'TQ':
                    complete = []
                    for answer in (value, spec['witness_alternative']):
                        assignments = {pair: spec['witness_alternative'] for pair in
                            itertools.product((target, other),
                                (spec['queried_attribute'], spec['alternative_attribute']))}
                        assignments[(owner, attr)] = value
                        assignments[(target, spec['queried_attribute'])] = answer
                        complete.append([dict(entity=e, attribute=a, value=v)
                                         for (e, a), v in sorted(assignments.items())])
                    worlds.append(dict(id=key, worlds=complete,
                        role='Compatible completions, not hidden ground-truth answers'))
    checks = validate_samples(rows, worlds, design)
    by_id = {r['id']: r for r in rows}
    pairs = []
    for sid in (s['id'] for s in design['example_scenarios']):
        comparisons = []
        for variant in ('v1', 'v2'):
            comparisons += [('primary_entity_other_attribute', f'TA_{variant}', f'OA_{variant}'),
                            ('entity_queried_attribute', f'TQ_{variant}', f'OQ_{variant}'),
                            ('attribute_target', f'TQ_{variant}', f'TA_{variant}'),
                            ('attribute_other', f'OQ_{variant}', f'OA_{variant}')]
        comparisons += [('candidate_value', f'{c}_v1', f'{c}_v2') for c in design['cells']]
        for kind, lhs, rhs in comparisons:
            a, b = by_id[f'{sid}_{lhs}'], by_id[f'{sid}_{rhs}']
            changed = [i + 1 for i, (da, db) in enumerate(zip(a['documents'], b['documents'])) if da != db]
            require(a['question'] == b['question'] and len(changed) == 1, 'Uncontrolled slot edit')
            if kind.startswith('primary_entity') or kind == 'entity_queried_attribute':
                words = lambda r: Counter(re.findall(r'[A-Za-z]+|\d+', '\n'.join(r['documents'])))
                require(words(a) == words(b), 'Entity edit changes word/number multiset')
            pairs.append(dict(kind=kind, left=a['id'], right=b['id'], changed_slot=changed[0],
                left_document_chars=sum(map(len, a['documents'])),
                right_document_chars=sum(map(len, b['documents']))))
    checks.update(pairs=len(pairs), primary_pairs=sum(p['kind'].startswith('primary_entity') for p in pairs),
                  entity_pair_word_number_multisets_equal=True)
    return rows, worlds, pairs, checks


def compute():
    preserved = preservation()
    design, manual, old = read(DESIGN), read(MANUAL), read(OLD)
    require(not design['collection_allowed_by_this_file'] and not design['independent_semantic_approval'],
            'Draft scope changed')
    require(manual['new_behavior_judgments'] == 0 and not manual['independent_gold'], 'Audit identity changed')
    with (ROOT / BEHAVIOR).open(newline='') as f:
        source_rows = list(csv.DictReader(f))
    insufficient = [r for r in source_rows if r['exposed_author_input_mode'] == 'refuse']
    selected = {r['id']: r for r in insufficient if r['has_substantive_answer'] == 'yes'}
    require(len(source_rows) == 240 and len(insufficient) == 60 and len(selected) == 23,
            'Old complete denominator differs')
    cases = old['cases']
    require(len(cases) == len({c['id'] for c in cases}) == 23
            and {c['id'] for c in cases} == set(selected), 'Case selection mismatch')
    bases = {r['base']: r for r in manual['bases']}
    require(len(bases) == len(manual['bases']) == 13, 'Base table not one-to-one')
    packet = {r['item_id']: r for r in read(TRANSFER + '/behavior_review/packet.json')['items']}
    mapping = read(TRANSFER + '/coordinator/behavior_mapping.json')
    pred = {r['id']: r for r in read(TRANSFER + '/predictions.json')['records']}
    binputs = read(BINDING + '/materials/inputs.json')
    bpred = {r['id']: r for r in read(BINDING + '/predictions.json')['records']}
    binding_result = read('docs/records/2026-10-21-behavior-binding-results.json')
    case_rows = []
    quoted_documents = set()
    for c in cases:
        key = c['id']
        source = packet[mapping[key]]
        require(c['question'] == source['question'] and c['output'] == source['answer']
                == selected[key]['raw_output'] == pred[key]['raw_output'], 'Case join differs: ' + key)
        for quote in c['input_citations']:
            source_id = key if quote['endpoint'] == 'I' else c['s_id']
            doc = packet[mapping[source_id]]['documents'][quote['document_index'] - 1]
            require(doc[quote['start']:quote['end']] == quote['quote']
                    and hashlib.sha256(doc.encode()).hexdigest() == quote['text_sha256'],
                    'Old citation differs')
            if quote['endpoint'] == 'I':
                quoted_documents.add(quote['text_sha256'])
        base = key.split('_')[0]
        require(base in bases, 'Unmapped base')
        case_rows.append(dict(id=key, base=base, question=c['question'],
            old_pattern=c['primary_pattern'], old_boundary=c['boundary'],
            structural_difference=bases[base]['structural_difference'],
            proposed_design_connection=bases[base]['design_connection'], coverage=bases[base]['coverage'],
            old_output=c['output'], audit_json_pointer='/cases/' + str(cases.index(c))))
    require(Counter(r['base'] for r in case_rows) == Counter({b:r['outputs'] for b,r in bases.items()}),
            'Base counts differ')
    patterns = dict(Counter(c['primary_pattern'] for c in cases))
    require(patterns == old['primary_pattern_counts'], 'Existing audit taxonomy differs')
    stats = []
    def add_stats(name, inputs, predictions, docs_key, id_key='id'):
        tokens = [predictions[r[id_key]]['input_tokens'] for r in inputs]
        chars = [sum(len(d) for d in r[docs_key]) for r in inputs]
        unique = {hashlib.sha256(d.encode()).hexdigest() for r in inputs for d in r[docs_key]}
        stats.append(dict(group=name, rows=len(inputs), document_slots=sum(len(r[docs_key]) for r in inputs),
            unique_document_texts=len(unique), input_tokens_min=min(tokens), input_tokens_max=max(tokens),
            input_tokens_sum=sum(tokens), input_tokens_mean=sum(tokens)/len(tokens),
            document_chars_min=min(chars), document_chars_max=max(chars),
            document_chars_mean=sum(chars)/len(chars)))
    def transfer_inputs(ids):
        return [dict(id=k, documents=packet[mapping[k]]['documents']) for k in ids]
    add_stats('transfer_all_I60', transfer_inputs([r['id'] for r in insufficient]), pred, 'documents')
    add_stats('transfer_selected_answering_I23', transfer_inputs(list(selected)), pred, 'documents')
    add_stats('transfer_matched_S23_unfiltered_for_S_behavior',
              transfer_inputs([k[:-1]+'S' for k in selected]), pred, 'documents')
    add_stats('binding_all48', binputs, bpred, 'docs')
    add_stats('binding_I24', [r for r in binputs if r['condition']=='I'], bpred, 'docs')
    require(len(binputs) == 48 and len(bpred) == 48, 'Binding source size differs')
    sample_rows, worlds, pairs, sample_checks = examples(design)
    source_paths = [DESIGN, MANUAL, OLD, BEHAVIOR,
        TRANSFER+'/behavior_review/packet.json', TRANSFER+'/coordinator/behavior_mapping.json',
        TRANSFER+'/predictions.json', BINDING+'/materials/inputs.json', BINDING+'/predictions.json',
        'docs/records/2026-10-21-behavior-binding-results.json',
        'prompts/behavior_binding_materials_v1.json', 'scripts/evidence_experiment.py',
        'scripts/behavior_structure_audit.py']
    report = dict(status='source_bound_posthoc_comparison_and_draft_examples', history_exposed=True,
        independent_gold=False, original_behavior_rescored=False, new_behavior_judgments=0,
        old_insufficient_denominator=len(insufficient), old_insufficient_answering=len(selected),
        old_insufficient_behavior_counts=dict(Counter(r['has_substantive_answer'] for r in insufficient)),
        selected_error_bases=len(bases), old_patterns=patterns,
        old_boundary_counts=dict(Counter(c['boundary'] for c in cases)),
        structural_connection_counts=dict(Counter(r['coverage'] for r in case_rows)),
        binding_insufficient=binding_result['by_condition']['I'],
        statistics=stats, sample_checks=sample_checks,
        example_scope='Two authored example scenarios/16 exact inputs; not full48 materials or execution protocol',
        exact_tokens_for_new_examples=None, new_gpu_calls=0, new_forward_passes=0, new_answers=0,
        new_fits=0, original_remaining_fits=0, independent_semantic_approvals=0,
        original_formal_gate=False, held_out380_accessed=False,
        prior_paths_preserved=len(preserved), source_sha256={p:sha(p) for p in source_paths},
        review_basis='Existing sealed23 case codings and their input/output citations; no claim of a new full121-document reread or independent semantic review',
        interpretation='Cross-study differences are descriptive and jointly confounded; selected23/23 is not a rate for comparison. Novel contrast TA-OA changes candidate entity attachment within alternative-attribute inputs, with lexical mention counts balanced; not an internal causal mechanism or explanation of old error gap.')
    outputs = {
        PREFIX+'.json':dump(report), PREFIX+'-preserved.json':dump(preserved),
        PREFIX+'-cases.csv':csv_text(case_rows, list(case_rows[0])),
        PREFIX+'-bases.csv':csv_text(manual['bases'], list(manual['bases'][0])),
        PREFIX+'-statistics.csv':csv_text(stats, list(stats[0])),
        PREFIX+'-dimensions.csv':csv_text(manual['cross_study_dimensions'], list(manual['cross_study_dimensions'][0])),
        PREFIX+'-samples.json':dump(dict(status='examples_only_no_outputs', items=sample_rows)),
        PREFIX+'-worlds.json':dump(dict(role='coordinator_only_never_render', items=worlds)),
        PREFIX+'-pairs.csv':csv_text(pairs, list(pairs[0]))}
    md = ['# 关系附着新对照：两场景16条完整样例', '',
          '设计阶段样例；无模型输出，不是完整48条执行材料。作者有项目历史暴露。协调条件/见证不交给模型；实际renderer和tokenizer尚未准备。', '']
    for row in sample_rows:
        md += [f"## {row['id']}", '', row['question'], '']
        for i, doc in enumerate(row['documents'],1):
            md += [f'D{i}: {doc}', '']
        md += ['作者关系判断：'+('直接给出所问关系，候选值有据。' if row['cell']=='TQ' else
                '未给出所问目标属性；候选值在一种兼容世界中可相同，在另一种世界中可不同，不能据记录确定。'), '']
    outputs[PREFIX+'-samples.md'] = '\n'.join(md)
    return outputs, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', required=True, choices=('build','verify'))
    args = parser.parse_args()
    outputs, report = compute()
    for name, content in outputs.items():
        path, data = ROOT/name, content.encode()
        if args.stage == 'build':
            require(not path.exists() or path.read_bytes() == data, 'Refuse changed artifact: '+name)
            path.write_bytes(data)
        else:
            require(path.is_file() and path.read_bytes() == data, 'Artifact mismatch: '+name)
    # Include newly generated draft files and the frozen inputs in the re-read before completion.
    require(all(sha(p) == h for p,h in report['source_sha256'].items()), 'Source changed during audit')
    preservation()
    print(dump(dict(stage=args.stage, preserved=report['prior_paths_preserved'],
        old_I=report['old_insufficient_denominator'], old_answering=report['old_insufficient_answering'],
        sample_checks=report['sample_checks'], new_generations=0, new_fits=0)).strip())


if __name__ == '__main__':
    main()
