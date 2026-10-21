"""Post-hoc CPU replay of frozen linear decisions versus existing sigmoid calibration."""

import argparse
from collections import Counter
import csv
from importlib.metadata import version
import io
import json
from pathlib import Path
import pickle

import numpy as np
from scipy.special import expit

ROOT = Path(__file__).resolve().parents[1]
SPEC = 'prompts/probe_calibration_diagnostic_v1.json'
PRESERVED = 'docs/records/2026-10-21-probe-calibration-diagnostic-preserved.json'
PREFIX = 'docs/records/2026-10-21-probe-calibration-diagnostic'
RUN = ROOT / 'runs/qwen2.5-3b-probe-calibration-diagnostic-v1'
MODES = ['answer', 'refuse', 'conflict']
DISPOSITIONS = ['unchanged_correct', 'unchanged_wrong', 'changed_corrected', 'changed_damaged',
                'changed_both_wrong', 'changed_reference_unknown', 'unchanged_reference_unknown']
BIND_FIELDS = ['has_substantive_target_answer', 'adopts_cell_distractor_value',
               'supported_target_answer', 'acknowledges_insufficiency', 'claimed_evidence_supports_target']
TRANSFER_FIELDS = ['has_substantive_answer', 'acknowledges_insufficiency', 'acknowledges_conflict',
    'selects_single_answer', 'answer_grounded_correct', 'has_supplied_resolution', 'selection_without_resolution']


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads((ROOT / path).read_text())


def digest(path):
    import hashlib
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode()


def immutable(path, data, verify):
    if path.exists() or verify:
        require(path.exists() and path.read_bytes() == data, 'Frozen diagnostic artifact differs: ' + str(path))
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def check_sources():
    manifest = read(PRESERVED)
    for name, value in manifest.items():
        require(digest(ROOT / name) == value, 'Preserved source changed: ' + name)
    for run, record in [
        ('runs/qwen2.5-3b-behavior-binding-probe-v1',
         'docs/records/2026-10-21-behavior-binding-probe-results-source-run-hashes.json'),
        ('runs/qwen2.5-3b-semantic-transfer-exploratory-v5-v1',
         'docs/records/2026-10-21-semantic-transfer-exploratory-verified-run-hashes.json')]:
        actual = {str(p.relative_to(ROOT)) for p in (ROOT / run).rglob('*') if p.is_file() and p.name != '.run.lock'}
        expected = {p for p in read(record) if not p.endswith('/.run.lock')}
        require(actual == expected, 'Frozen source run file set changed')
    return manifest


def disposition(reference, before, after):
    require(reference in MODES + ['unknown'], 'Unexpected reference')
    require(before in MODES and after in MODES, 'Unexpected decision')
    if reference == 'unknown':
        return 'unchanged_reference_unknown' if before == after else 'changed_reference_unknown'
    if before == after:
        return 'unchanged_correct' if before == reference else 'unchanged_wrong'
    if after == reference:
        return 'changed_corrected'
    return 'changed_damaged' if before == reference else 'changed_both_wrong'


def stage_replay(probe, states):
    require(states.shape == (36, 2048) and states.dtype == np.float16
            and np.isfinite(states).all() and not np.any(np.all(states == 0, axis=1)), 'Invalid source state')
    standardized = probe['scaler'].transform(states[28][None].astype(np.float32))
    calibrated = probe['router'].calibrated_classifiers_[0]
    estimator = calibrated.estimator
    linear = estimator.decision_function(standardized)[0]
    raw_index = int(np.argmax(linear))
    require(int(estimator.predict(standardized)[0]) == raw_index, 'Raw class mapping differs')
    raw_softmax = np.exp(linear - linear.max())
    raw_softmax /= raw_softmax.sum()
    a = np.array([c.a_ for c in calibrated.calibrators])
    b = np.array([c.b_ for c in calibrated.calibrators])
    sigmoid_logit = -(a * linear + b)
    sigmoid = expit(sigmoid_logit)
    require(np.isfinite(sigmoid).all() and sigmoid.sum() > 0, 'Invalid sigmoid output')
    probability = sigmoid / sigmoid.sum()
    replayed = probe['router'].predict_proba(standardized)[0]
    error = float(np.max(np.abs(probability - replayed)))
    require(error < 1e-10, 'Sigmoid replay differs from frozen router')
    require(np.argmax(sigmoid) == np.argmax(probability),
            'Positive common normalization changed sigmoid argmax')
    return dict(raw_pred=MODES[raw_index], calibrated_pred=MODES[int(np.argmax(probability))],
        linear=linear.tolist(), raw_softmax=raw_softmax.tolist(), sigmoid_logit=sigmoid_logit.tolist(),
        sigmoid=sigmoid.tolist(), probability=probability.tolist(), replay_error=error)


def load_dataset(name, spec):
    dataset = spec['datasets'][name]
    run = ROOT / dataset['run']
    records = read(run / dataset['records'])['records']
    if name == 'binding48':
        originals = read(run / dataset['behavior'])
        reference = {r['id']: ('answer' if r['condition'] == 'S' else 'refuse') for r in originals}
    else:
        with (ROOT / dataset['behavior']).open(newline='') as stream:
            originals = list(csv.DictReader(stream))
        author = {r['id']:r['semantic_mode'] for r in read(
            'docs/records/2026-10-21-semantic-transfer-v5-acceptance-ratings.json')['ratings']}
        reference = {r['id']: r['exposed_author_input_mode'] for r in originals}
        require(reference == author, 'Transfer author references differ')
    require(len(originals) == len(records) == len({r['id'] for r in records}) == dataset['rows'], 'Wrong source coverage')
    require(len({r['original_id'] for r in originals}) == dataset['bases'], 'Wrong base count')
    original = {r['id']:r for r in originals}
    require(set(original) == {r['id'] for r in records}, 'Behavior/state IDs differ')
    require(all(set(record['probe_probabilities']) == set(MODES) for record in records), 'Missing saved probabilities')
    return run, records, original, reference


def rate(values):
    require(all(v in ['yes', 'no', 'unknown'] for v in values), 'Unexpected original behavior value')
    n = len(values)
    counts = Counter(values)
    return dict(eligible=n, yes=counts['yes'], no=counts['no'], unknown=counts['unknown'],
        point=counts['yes']/n if n and not counts['unknown'] else None,
        lower=counts['yes']/n if n else None, upper=(counts['yes']+counts['unknown'])/n if n else None)


def summarize(rows):
    require(bool(rows), 'Empty summary slice')
    eligible = [r for r in rows if r['author_reference'] != 'unknown']
    result = dict(rows=len(rows), bases=len({r['original_id'] for r in rows}),
        known_reference=len(eligible), unknown_reference=len(rows)-len(eligible),
        class_changes=sum(r['raw_pred']!=r['calibrated_pred'] for r in rows),
        dispositions={k:sum(r['disposition']==k for r in rows) for k in DISPOSITIONS},
        transitions={a:{b:sum(r['raw_pred']==a and r['calibrated_pred']==b for r in rows) for b in MODES} for a in MODES})
    for field, stage in [('raw_pred','raw'), ('calibrated_pred','calibrated')]:
        result[stage] = dict(matches_author_reference=sum(r[field]==r['author_reference'] for r in eligible),
            distribution={k:sum(r[field]==k for r in rows) for k in MODES},
            confusion={a:{b:sum(r['author_reference']==a and r[field]==b for r in eligible) for b in MODES} for a in MODES},
            I_existing_answer_by_class={mode:rate([r['existing_has_answer'] for r in rows
                if r['author_reference']=='refuse' and r[field]==mode]) for mode in MODES})
    result['net_reference_matches'] = result['calibrated']['matches_author_reference']-result['raw']['matches_author_reference']
    require(result['net_reference_matches'] == result['dispositions']['changed_corrected']-result['dispositions']['changed_damaged'],
            'Correctness change accounting failed')
    return result


def make_pairs(dataset, rows):
    groups = {}
    for row in rows:
        slot = (row['variant'],row['condition']) if dataset == 'binding48' else (row['expression'],row['condition'])
        require(slot not in groups.setdefault(row['original_id'],{}), 'Duplicate paired slot')
        groups[row['original_id']][slot] = row
    pairs = []
    def add(left, right, contrast):
        require(left['question']==right['question'] and left['partition']==right['partition'], 'Mixed paired question/partition')
        pair = dict(dataset=dataset, original_id=left['original_id'], partition=left['partition'], contrast=contrast,
            left_id=left['id'],right_id=right['id'],left_reference=left['author_reference'],right_reference=right['author_reference'],
            left_existing_behavior=left['existing_behavior'],right_existing_behavior=right['existing_behavior'])
        for stage in ['raw','calibrated']:
            field = stage+'_pred'
            pair[stage+'_left_pred'],pair[stage+'_right_pred'] = left[field],right[field]
            pair[stage+'_class_changed'] = left[field] != right[field]
            pair[stage+'_both_match_reference'] = None if 'unknown' in [left['author_reference'],right['author_reference']] else (
                left[field]==left['author_reference'] and right[field]==right['author_reference'])
        for mode in MODES:
            for stage in ['linear','raw_softmax','calibrated_p']:
                pair['delta_'+stage+'_'+mode] = right[stage+'_'+mode]-left[stage+'_'+mode]
        pairs.append(pair)
    for _,group in sorted(groups.items()):
        if dataset == 'binding48':
            require(set(group)=={(v,c) for v in ['v1','v2'] for c in ['S','I']}, 'Incomplete binding base')
            for variant in ['v1','v2']:
                add(group[variant,'S'],group[variant,'I'],'S_to_I')
            for condition in ['S','I']:
                add(group['v1',condition],group['v2',condition],'distractor_'+condition)
        else:
            require(set(group)=={(v,c) for v in ['A','B'] for c in ['S','I','C','K']}, 'Incomplete transfer base')
            for expression in ['A','B']:
                for condition in ['I','C','K']:
                    add(group[expression,'S'],group[expression,condition],'S_to_'+condition)
            for condition in ['S','I','C','K']:
                add(group['A',condition],group['B',condition],'A_to_B_'+condition)
    require(len(pairs)==(48 if dataset=='binding48' else 300), 'Wrong pair coverage')
    return pairs


def slice_summaries(dataset, rows):
    slices = [('all', 'all', rows)]
    axes = ['condition','variant'] if dataset == 'binding48' else ['partition','condition','expression']
    for axis in axes:
        for key in sorted({r[axis] for r in rows}):
            slices.append((axis,key,[r for r in rows if r[axis]==key]))
    if dataset == 'transfer240':
        for partition in sorted({r['partition'] for r in rows}):
            for axis in ['condition','expression']:
                for key in sorted({r[axis] for r in rows}):
                    slices.append(('partition_by_'+axis,partition+'|'+key,
                        [r for r in rows if r['partition']==partition and r[axis]==key]))
    return [dict(dataset=dataset,axis=axis,key=key,**summarize(group)) for axis,key,group in slices]


def csv_bytes(rows):
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream,fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows([{k:json.dumps(v,ensure_ascii=False,sort_keys=True) if isinstance(v,(dict,list)) else v
        for k,v in row.items()} for row in rows])
    return stream.getvalue().encode()


def compute():
    manifest = check_sources()
    spec = read(SPEC)
    require(spec['budget']==dict(new_fits=0,new_gpu_calls=0,new_generations=0,new_labels=0,
        threshold_or_layer_searches=0,bootstrap_or_significance_tests=0,original_fit_budget_remaining=0), 'Budget changed')
    path = ROOT / spec['probe_source']
    require(digest(path) == spec['probe_sha256'], 'Frozen probe differs')
    probe = pickle.loads(path.read_bytes())
    require(probe['layer']==28 and list(probe['router'].classes_)==[0,1,2]
        and len(probe['router'].calibrated_classifiers_)==1 and probe['router'].method=='sigmoid'
        and probe['router'].cv=='prefit', 'Expected frozen prefit sigmoid L28 router')
    calibrated = probe['router'].calibrated_classifiers_[0]
    require(list(calibrated.classes)==[0,1,2] and list(calibrated.estimator.classes_)==[0,1,2], 'Unexpected class order')
    metadata = read('runs/qwen2.5-3b-free-answer-study/chat/probe/probe.json')
    require(metadata['pickle_sha256']==spec['probe_sha256'] and metadata['spec']==probe['spec'], 'Probe metadata differs')
    for split,sha in metadata['spec']['source_states_sha256'].items():
        require(digest(ROOT / f'runs/qwen2.5-3b-free-answer-study/chat/{split}/states.json')==sha, 'Old training/calibration source differs')
    all_rows, all_pairs, summaries, base_summaries = [],[],[],[]
    source_error, api_error = 0.,0.
    for dataset in ['binding48','transfer240']:
        run,records,originals,references = load_dataset(dataset,spec)
        output = []
        for record in sorted(records,key=lambda r:r['id']):
            original = originals[record['id']]
            fields = BIND_FIELDS if dataset=='binding48' else TRANSFER_FIELDS
            require(all(record[k]==original[k] for k in ['id','original_id','condition']), 'Original identity mismatch')
            if dataset=='transfer240':
                require(all(record[k]==original[k] for k in ['partition','expression','raw_output']), 'Transfer provenance mismatch')
                require(json.loads(original['probe_probabilities'])==record['probe_probabilities'], 'Original calibrated fields differ')
            path = run / record['feature_file']
            require(path.parent==run/'features' and digest(path)==record['feature_sha256'], 'Feature path/hash differs')
            stages = stage_replay(probe,np.load(path,allow_pickle=False))
            require(stages['calibrated_pred']==record['probe_pred'] and record['probe_layer_zero_based']==28, 'Saved calibrated class differs')
            error=max(abs(stages['probability'][i]-record['probe_probabilities'][m]) for i,m in enumerate(MODES))
            require(error<1e-10, 'Saved probability differs')
            source_error,api_error=max(source_error,error),max(api_error,stages['replay_error'])
            ref = references[record['id']]
            row=dict(dataset=dataset,id=record['id'],item_id=original['item_id'],original_id=record['original_id'],
                partition=original['partition'] if dataset=='transfer240' else 'fictional_diagnostic',
                expression=original['expression'] if dataset=='transfer240' else '',
                variant=original['variant'] if dataset=='binding48' else '',condition=record['condition'],
                author_reference=ref,question=original['question'],raw_output=original['raw_output'],
                existing_behavior={f:original[f] for f in fields},
                existing_has_answer=original['has_substantive_target_answer' if dataset=='binding48' else 'has_substantive_answer'],
                raw_pred=stages['raw_pred'],calibrated_pred=stages['calibrated_pred'],
                raw_matches_reference=None if ref=='unknown' else stages['raw_pred']==ref,
                calibrated_matches_reference=None if ref=='unknown' else stages['calibrated_pred']==ref,
                disposition=disposition(ref,stages['raw_pred'],stages['calibrated_pred']),
                feature_sha256=record['feature_sha256'],prompt_sha256=record['prompt_sha256'],
                state_timing=spec['datasets'][dataset]['timing'])
            for i,mode in enumerate(MODES):
                for name,key in [('linear','linear'),('raw_softmax','raw_softmax'),('sigmoid_logit','sigmoid_logit'),
                                 ('sigmoid_unnormalized','sigmoid'),('calibrated_p','probability')]:
                    row[name+'_'+mode]=stages[key][i]
            output.append(row)
        all_rows.extend(output)
        all_pairs.extend(make_pairs(dataset,output))
        summaries.extend(slice_summaries(dataset,output))
        for oid in sorted({r['original_id'] for r in output}):
            base_summaries.append(dict(dataset=dataset,original_id=oid,**summarize([r for r in output if r['original_id']==oid])))
    require(len(all_rows)==288 and len(all_pairs)==348 and len(base_summaries)==42, 'Total coverage differs')
    require(sum(r['author_reference']=='unknown' for r in all_rows)==4, 'Unknown reference count changed')
    report=dict(status='posthoc_frozen_linear_vs_sigmoid_diagnostic_complete',independent_gold=False,
        rows=288,datasets={name:summarize([r for r in all_rows if r['dataset']==name]) for name in spec['datasets']},
        pairs=len(all_pairs),pair_counts=dict(Counter(r['dataset'] for r in all_pairs)),
        slices=len(summaries),base_summaries=42,preserved_paths=len(manifest),
        saved_probability_max_absolute_error=source_error,api_probability_max_absolute_error=api_error,
        original_fit_budget_remaining=0,new_fits=0,new_gpu_calls=0,new_answers=0,new_behavior_ratings=0,
        thresholds_added=0,formal_labels_added=0,bootstrap_or_significance_tests_added=False,
        class_specific_sigmoid_parameters=[dict(mode=m,a=float(c.a_),b=float(c.b_)) for m,c in zip(MODES,calibrated.calibrators)],
        calibration_normalization_cannot_change_argmax=True,
        limitations=spec['inference'],state_timings={k:v['timing'] for k,v in spec['datasets'].items()})
    implementations=['scripts/probe_calibration_diagnostic.py','tests/test_probe_calibration_diagnostic.py']
    protocol=dict(task=spec['task'],specification_sha256=digest(ROOT/SPEC),preserved_manifest_sha256=digest(ROOT/PRESERVED),
        implementation_sha256={p:digest(ROOT/p) for p in implementations},probe_sha256=spec['probe_sha256'],
        runtime_versions={p:version(p) for p in ['numpy','scipy','scikit-learn']},budget=spec['budget'],
        source_rows=dict(binding48=48,transfer240=240),formal_gate_changed=False,confirmation380_accessed=False)
    return protocol,report,all_rows,summaries,all_pairs,base_summaries


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',choices=['analyze','verify'],required=True)
    args=parser.parse_args()
    protocol,report,rows,slices,pairs,bases=compute()
    outputs={'protocol.json':json_bytes(protocol),'report.json':json_bytes(report),'rows.json':json_bytes(rows),
        'slices.json':json_bytes(slices),'pairs.json':json_bytes(pairs),'base_summaries.json':json_bytes(bases),
        'rows.csv':csv_bytes(rows),'slices.csv':csv_bytes(slices),'pairs.csv':csv_bytes(pairs),'base_summaries.csv':csv_bytes(bases)}
    for name,data in outputs.items():
        immutable(RUN/name,data,args.stage=='verify')
    for suffix,name in [('.json','report.json'),('-rows.csv','rows.csv'),('-slices.csv','slices.csv'),
                        ('-pairs.csv','pairs.csv'),('-base_summaries.csv','base_summaries.csv')]:
        immutable(ROOT/(PREFIX+suffix),outputs[name],args.stage=='verify')
    check_sources()
    print(json.dumps(dict(stage=args.stage,rows=288,pairs=348,preserved_paths=report['preserved_paths'],
        saved_probability_max_absolute_error=report['saved_probability_max_absolute_error'],
        datasets={k:dict(before=v['raw']['matches_author_reference'],after=v['calibrated']['matches_author_reference'],
            known=v['known_reference'],unknown=v['unknown_reference'],changes=v['class_changes'],dispositions=v['dispositions'])
            for k,v in report['datasets'].items()},new_fits=0,new_gpu_calls=0),ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
