"""Read saved results and create/replay a post-hoc, exposed-reference probe audit.

No model, probe deserialization, training, GPU or forward pass is used.
"""
import argparse
import collections
import csv
import hashlib
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/review/2026-11-09-probe-existing-cache-audit-v1'
FILES = {
    'contract': 'docs/probe_measurement_existing_cache_audit_20261109.md',
    'diagnostic_rows': 'docs/records/2026-10-21-probe-calibration-diagnostic-rows.csv',
    'diagnostic_pairs': 'docs/records/2026-10-21-probe-calibration-diagnostic-pairs.csv',
    'acceptance_pairs': 'docs/records/2026-10-21-semantic-transfer-v5-acceptance-pairs.csv',
    'acceptance_cells': 'runs/qwen2.5-3b-semantic-transfer-v5-acceptance-v1/cells.csv',
    'transfer_records': 'runs/qwen2.5-3b-semantic-transfer-exploratory-v5-v1/predictions.json',
    'transfer_protocol': 'runs/qwen2.5-3b-semantic-transfer-exploratory-v5-v1/protocol.json',
    'transfer_approved': 'runs/qwen2.5-3b-semantic-transfer-exploratory-v5-v1/approved_labels.json',
    'transfer_behavior': 'docs/records/2026-10-21-semantic-transfer-exploratory-behavior-cells.csv',
    'binding_records': 'runs/qwen2.5-3b-behavior-binding-probe-v1/states.json',
    'binding_protocol': 'runs/qwen2.5-3b-behavior-binding-probe-v1/protocol.json',
    'binding_generation': 'runs/qwen2.5-3b-behavior-binding-v1/predictions.json',
    'binding_behavior': 'runs/qwen2.5-3b-behavior-binding-probe-v1/source/behavior_rows.json',
    'probe': 'runs/qwen2.5-3b-free-answer-study/chat/probe/probe.pkl',
}
EXPECTED_PROBE = 'db6033b84f1fcd30e5e2e31ce4beb262a76920cc06811c57900ad14b8d40858d'
CLASSES = ('answer', 'refuse', 'conflict')


def check(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(name):
    return json.loads((ROOT / FILES[name]).read_text(encoding='utf-8'))


def read_csv(name):
    with (ROOT / FILES[name]).open(encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


def index(rows, key='id'):
    result = {x[key]: x for x in rows}
    check(len(result) == len(rows), 'duplicate identifier: ' + key)
    return result


def csv_bytes(rows):
    check(bool(rows), 'empty output table')
    f = io.StringIO(newline='')
    w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator='\n')
    w.writeheader()
    w.writerows(rows)
    return f.getvalue().encode('utf-8')


def group_counts(rows, keys):
    result = []
    values = sorted({tuple(r[k] for k in keys) for r in rows})
    for value in values:
        selected = [r for r in rows if tuple(r[k] for k in keys) == value]
        counter = collections.Counter(r['reference_match_pattern'] for r in selected)
        result.append(dict(zip(keys, value), pairs=len(selected),
                           bases=len({r['original_id'] for r in selected}),
                           class_same=sum(r['calibrated_class_same'] for r in selected),
                           class_changed=sum(not r['calibrated_class_same'] for r in selected),
                           both_match=counter['both'], left_only=counter['left_only'],
                           right_only=counter['right_only'], neither_match=counter['neither'],
                           reference_unknown=counter['unknown'],
                           right_reference_p_increase=sum(r['right_reference_p_change_positive'] is True for r in selected),
                           right_reference_p_decrease_or_equal=sum(r['right_reference_p_change_positive'] is False for r in selected),
                           right_reference_p_unavailable=sum(r['right_reference_p_change_positive'] is None for r in selected),
                           token_delta_zero=sum(r['token_delta']==0 for r in selected),
                           token_delta_nonzero=sum(r['token_delta']!=0 for r in selected)))
    return result


def main_data():
    paths = {name: {'path': path, 'sha256': sha(ROOT / path)} for name, path in FILES.items()}
    check(paths['probe']['sha256'] == EXPECTED_PROBE, 'frozen probe mismatch')
    transfer_protocol = read_json('transfer_protocol')
    binding_protocol = read_json('binding_protocol')
    probe_refs = [v for k, v in transfer_protocol['sources'].items() if k.endswith('/chat/probe/probe.pkl')]
    check(probe_refs == [EXPECTED_PROBE] and binding_protocol['probe_sha256']==EXPECTED_PROBE,
          'recorded frozen probes differ')
    transfer_run = ROOT / 'runs/qwen2.5-3b-semantic-transfer-exploratory-v5-v1'
    binding_run = ROOT / 'runs/qwen2.5-3b-behavior-binding-probe-v1'
    transfer_raw = read_json('transfer_records')['records']
    binding_raw = read_json('binding_records')['records']
    generated = {'transfer240': index(transfer_raw),
                 'binding48': index(read_json('binding_generation')['records'])}
    features = {'transfer240': index(transfer_raw), 'binding48': index(binding_raw)}
    behavior = {'transfer240': index(read_csv('transfer_behavior')),
                'binding48': index(read_json('binding_behavior'))}
    acceptance = index(read_csv('acceptance_cells'))
    approved = read_json('transfer_approved')
    check(len(approved) == 240 and all(v is None for v in approved.values()), 'formal labels differ')
    rows = read_csv('diagnostic_rows')
    check(len(rows)==288 and len(acceptance)==240, 'unexpected row counts')
    check(len({(r['dataset'],r['id']) for r in rows})==288, 'duplicate diagnostic rows')
    corpus = []
    for row in sorted(rows, key=lambda r:(r['dataset'], r['id'])):
        ds, key = row['dataset'], row['id']
        check(ds in features, 'unexpected dataset')
        rec, gen, beh = features[ds][key], generated[ds][key], behavior[ds][key]
        run = transfer_run if ds == 'transfer240' else binding_run
        check(row['prompt_sha256'] == rec['prompt_sha256'] == gen['prompt_sha256'], 'prompt mismatch '+key)
        check(row['raw_output'] == gen['raw_output'] == beh['raw_output'], 'answer mismatch '+key)
        check(hashlib.sha256(gen['raw_output'].encode()).hexdigest()==gen['raw_output_sha256'], 'answer hash mismatch '+key)
        check(rec['feature_sha256'] == row['feature_sha256'] == sha(run / rec['feature_file']), 'feature mismatch '+key)
        check(rec['probe_layer_zero_based'] == 28, 'unexpected layer')
        check(row['calibrated_pred']==rec['probe_pred'], 'probe class mismatch '+key)
        for c in CLASSES:
            check(abs(float(row['calibrated_p_'+c])-rec['probe_probabilities'][c]) < 1e-14, 'probe probability mismatch '+key)
        saved_behavior = json.loads(row['existing_behavior'])
        check(all(saved_behavior[k]==beh[k] for k in saved_behavior), 'behavior mismatch '+key)
        if ds == 'transfer240':
            check(row['author_reference']==acceptance[key]['semantic_mode'], 'reference mismatch '+key)
            check(rec['probe_decision_pre_first_token'] is True, 'timing mismatch')
        else:
            check(rec['input_token_ids_sha256']==gen['input_token_ids_sha256'], 'input tokens mismatch '+key)
            check(rec['capture_phase']=='retrospectively_recomputed_input_prefill_without_generation', 'timing mismatch')
        corpus.append(dict(dataset=ds, id=key, original_id=row['original_id'],
                           partition=row['partition'], expression=row['expression'],
                           variant=row['variant'], condition=row['condition'],
                           author_reference=row['author_reference'], formal_label=None,
                           input_tokens=gen['input_tokens'], prompt_sha256=rec['prompt_sha256'],
                           feature_path=str((run / rec['feature_file']).relative_to(ROOT)),
                           feature_sha256=rec['feature_sha256'],
                           state_timing='generation_prefill' if ds=='transfer240' else 'post_answer_recomputed',
                           raw_pred=row['raw_pred'], calibrated_pred=row['calibrated_pred'],
                           p_answer=float(row['calibrated_p_answer']),
                           p_refuse=float(row['calibrated_p_refuse']),
                           p_conflict=float(row['calibrated_p_conflict']),
                           output_sha256=hashlib.sha256(row['raw_output'].encode()).hexdigest(),
                           existing_behavior=row['existing_behavior']))
    check(collections.Counter(r['dataset'] for r in corpus)=={'transfer240':240,'binding48':48}, 'dataset counts')
    corpus_index={(r['dataset'],r['id']):r for r in corpus}
    acceptance_pairs = read_csv('acceptance_pairs')
    check(len(acceptance_pairs)==300, 'acceptance pairs mismatch')
    diagnostic_pairs = read_csv('diagnostic_pairs')
    transfer_pairs={(r['left_id'],r['right_id']):r for r in diagnostic_pairs if r['dataset']=='transfer240'}
    check(len(transfer_pairs)==300, 'diagnostic pairs mismatch')
    pairs=[]
    for p in acceptance_pairs:
        left,right=p['left_id'],p['right_id']
        a=corpus_index['transfer240',left]; b=corpus_index['transfer240',right]
        d=transfer_pairs[left,right]
        check(a['original_id']==b['original_id']==p['original_id']==d['original_id'], 'base mismatch')
        check(a['partition']==b['partition']==p['partition']==d['partition'], 'partition mismatch')
        check(a['author_reference']==p['left_mode']==d['left_reference'], 'left reference mismatch')
        check(b['author_reference']==p['right_mode']==d['right_reference'], 'right reference mismatch')
        check(b['input_tokens']-a['input_tokens']==int(p['input_token_delta']), 'token mismatch')
        check(a['calibrated_pred']==d['calibrated_left_pred'] and b['calibrated_pred']==d['calibrated_right_pred'], 'pair class mismatch')
        check(a['raw_pred']==d['raw_left_pred'] and b['raw_pred']==d['raw_right_pred'], 'pair raw mismatch')
        known=a['author_reference'] in CLASSES and b['author_reference'] in CLASSES
        if known:
            am=a['calibrated_pred']==a['author_reference']; bm=b['calibrated_pred']==b['author_reference']
            pattern='both' if am and bm else 'left_only' if am else 'right_only' if bm else 'neither'
        else:
            pattern='unknown'
        kind='AB' if p['contrast'].startswith('AB_') else 'relation'
        target_p_change = (b['p_'+b['author_reference']]-a['p_'+b['author_reference']]
                           if kind=='relation' and b['author_reference'] in CLASSES else None)
        pairs.append(dict(kind=kind, contrast=p['contrast'], original_id=a['original_id'],
                          partition=a['partition'], left_id=left, right_id=right,
                          author_acceptance_status=p['status'], author_acceptance_rationale=p['rationale'],
                          left_reference=a['author_reference'], right_reference=b['author_reference'],
                          left_raw_pred=a['raw_pred'],right_raw_pred=b['raw_pred'],
                          left_calibrated_pred=a['calibrated_pred'],right_calibrated_pred=b['calibrated_pred'],
                          calibrated_class_same=a['calibrated_pred']==b['calibrated_pred'],
                          reference_match_pattern=pattern, token_delta=b['input_tokens']-a['input_tokens'],
                          right_reference_p_change_positive=(target_p_change>0 if target_p_change is not None else None),
                          delta_p_answer=b['p_answer']-a['p_answer'],
                          delta_p_refuse=b['p_refuse']-a['p_refuse'],
                          delta_p_conflict=b['p_conflict']-a['p_conflict']))
    check(len(pairs)==300 and collections.Counter(p['kind'] for p in pairs)=={'AB':120,'relation':180}, 'pair counts')
    ab=[p for p in pairs if p['kind']=='AB']
    relation=[p for p in pairs if p['kind']=='relation']
    check(collections.Counter(p['author_acceptance_status'] for p in ab)=={'no_specific_AB_difference_identified':107,'residual_detail_or_scope_caveat':13}, 'AB status counts')
    check(sum(p['reference_match_pattern']=='unknown' for p in ab)==2, 'AB unknown count')
    check(sum(p['reference_match_pattern']=='unknown' for p in relation)==6, 'relation unknown count')
    for group in (ab,relation):
        group.sort(key=lambda p:(p['contrast'],p['original_id'],p['left_id']))
    ab_summary=group_counts(ab,['author_acceptance_status'])
    relation_summary=group_counts(relation,['contrast'])
    summary={'status':'posthoc_exposed_author_reference_no_semantic_certification',
             'input_sources':paths, 'feature_file_sha256_checks':288,
             'corpus_counts':{'transfer240':240,'binding48':48},
             'formal_label_null':240, 'AB_all':group_counts(ab,[]),
             'AB_by_acceptance_status':ab_summary,
             'AB_by_condition':group_counts(ab,['contrast']),
             'AB_by_status_and_condition':group_counts(ab,['author_acceptance_status','contrast']),
             'relation_by_contrast':relation_summary,
             'relation_by_acceptance_status':group_counts(relation,['author_acceptance_status']),
             'new_gpu_calls':0,'new_forward_passes':0,'new_answers':0,'new_fits':0,
             'new_semantic_ratings':0,'new_thresholds':0,
             'E1_note':'No matched E1 probe found by the earlier bounded search; absence outside that search is not established.'}
    return {'corpus.csv':csv_bytes(corpus), 'AB_pairs.csv':csv_bytes(ab),
            'relation_pairs.csv':csv_bytes(relation),
            'summary.json':(json.dumps(summary,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', required=True, choices=['analyze','verify'])
    args=parser.parse_args()
    results=main_data()
    if args.stage=='analyze':
        OUT.mkdir(parents=True,exist_ok=True)
        for name,contents in results.items():
            with (OUT/name).open('xb') as f:
                f.write(contents)
    else:
        for name,contents in results.items():
            check((OUT/name).read_bytes()==contents, 'replay mismatch '+name)
    print(json.dumps({'stage':args.stage,'status':'ok','files':list(results),
                      'rows':288,'AB_pairs':120,'relation_pairs':180},ensure_ascii=False))


if __name__=='__main__':
    main()
