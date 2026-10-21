"""Independent CPU audit of the fixed48 retrospective L28 results; never generate or fit."""

import csv
from datetime import datetime, timedelta
import hashlib
import io
import json
from pathlib import Path
import pickle
import re

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / 'runs/qwen2.5-3b-behavior-binding-probe-v1'
OLD = ROOT / 'runs/qwen2.5-3b-behavior-binding-v1'
PREFIX = ROOT / 'docs/records/2026-10-21-behavior-binding-probe-results'
MODES = ['answer', 'refuse', 'conflict']
FIELDS = ['has_substantive_target_answer', 'adopts_cell_distractor_value',
          'supported_target_answer', 'acknowledges_insufficiency', 'claimed_evidence_supports_target']


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_manifest(manifest):
    for path, value in manifest.items():
        assert digest(ROOT / path) == value, path


def csv_bytes(rows):
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def main():
    source_manifest = read(Path(str(PREFIX) + '-source-run-hashes.json'))
    actual = {str(p.relative_to(ROOT)) for p in RUN.rglob('*') if p.is_file() and p.name != '.run.lock'}
    assert actual == set(source_manifest)
    check_manifest(source_manifest)
    preservation = read(RUN / 'source/preserved.json')
    check_manifest(preservation)
    protocol = read(RUN / 'protocol.json')
    check_manifest(protocol['implementation_sha256'])
    check_manifest(protocol['source_sha256'])
    prepared = read(ROOT / 'docs/records/2026-10-21-behavior-binding-probe-preparation-verification.json')
    check_manifest(prepared['prepared_artifact_sha256'])
    assert protocol['frozen_probe_layer'] == 28
    assert protocol['capture_phase'] == 'retrospectively_recomputed_input_prefill_without_generation'
    assert protocol['new_generations'] == protocol['new_probe_fits'] == 0
    records = read(RUN / 'states.json')['records']
    rows = read(RUN / 'materials/inputs.json')
    assert len(records) == len(rows) == len({r['id'] for r in records}) == 48
    assert [r['id'] for r in records] == [r['id'] for r in rows] == protocol['ordered_ids']
    assert read(RUN / 'states.json')['protocol_sha256'] == digest(RUN / 'protocol.json')
    attempts = sorted((RUN / 'forward_attempts').glob('*.json'))
    assert len(attempts) == len(list((RUN / 'features').glob('*.npy'))) == 48
    assert not (RUN / 'last_failure.json').exists()
    progress = read(RUN / 'progress.json')
    assert progress['saved'] == progress['target'] == 48
    smoke = read(RUN / 'smoke_gate.json')
    assert smoke['status'] == 'technical_smoke_passed' and smoke['semantic_accuracy_gate'] is False
    assert smoke['ids'] == protocol['smoke_prefix_ids'] == [r['id'] for r in rows[:4]]

    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(protocol['model'], local_files_only=True)
    old_protocol = read(OLD / 'protocol.json')
    old_predictions = read(OLD / 'predictions.json')['records']
    assert [r['id'] for r in old_predictions] == protocol['ordered_ids']
    old_materials = {r['id']:r for r in read(OLD / 'materials/inputs.json')}
    assert rows == [old_materials[r['id']] for r in records]
    template = read(ROOT / 'prompts/prompt_robustness_P0_P5.json')['P0']
    lengths = []
    vocab_size = len(tokenizer)  # Once, rather than per old output token; identical fixed vocabulary.
    preflight = read(RUN / 'preflight.json')['prompts']
    for row, record, old, identity in zip(rows, records, old_predictions, preflight):
        body = ''.join(template['doc_prefix'].format(i=i, doc=doc) for i,doc in enumerate(row['docs'],1))
        body += template['suffix'].format(question=row['question'])
        prompt = tokenizer.apply_chat_template([{'role':'system','content':old_protocol['instruction']},
            {'role':'user','content':body}], tokenize=False, add_generation_prompt=True)
        tokens = tokenizer(prompt, add_special_tokens=False, truncation=False)['input_ids']
        values = dict(prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(),input_tokens=len(tokens),
            input_token_ids_sha256=hashlib.sha256(json.dumps(tokens).encode()).hexdigest())
        assert all(record[k] == old[k] == identity[k] == v for k,v in values.items())
        assert all(type(t) is int and 0 <= t < vocab_size for t in old['generated_token_ids'])
        assert tokenizer.decode(old['generated_token_ids'], skip_special_tokens=True) == old['raw_output']
        lengths.append(len(tokens))
    assert sum(lengths) == 11688

    pickle_path = ROOT / 'runs/qwen2.5-3b-free-answer-study/chat/probe/probe.pkl'
    assert digest(pickle_path) == protocol['probe_sha256'] == 'db6033b84f1fcd30e5e2e31ce4beb262a76920cc06811c57900ad14b8d40858d'
    probe = pickle.loads(pickle_path.read_bytes())
    assert probe['layer'] == 28 and list(probe['router'].classes_) == [0,1,2]
    calibrated = probe['router'].calibrated_classifiers_
    assert len(calibrated) == 1 and list(calibrated[0].classes) == [0,1,2]
    estimator = calibrated[0].estimator
    assert estimator.coef_.shape == (3,2048)
    class_errors, manual_error = [], 0.0
    for i,(row,record,path) in enumerate(zip(rows, records, attempts)):
        assert path.name == f'{i:04d}.json'
        assert read(path) == dict(index=i,id=row['id'],protocol_sha256=digest(RUN/'protocol.json'),
                                  phase=protocol['capture_phase'])
        assert all(record[k] == row[k] for k in ['id','original_id','condition','variant'])
        assert record['feature_file'] == f'features/{i:04d}.npy'
        array_path = RUN / record['feature_file']
        assert digest(array_path) == record['feature_sha256']
        states = np.load(array_path, allow_pickle=False)
        assert states.shape == (36,2048) and states.dtype == np.float16
        assert np.isfinite(states).all() and not np.any(np.all(states==0, axis=1))
        # Independently reconstruct StandardScaler, three linear scores and sigmoid calibration.
        # In-place float32 arithmetic matches the frozen scaler's transform precision.
        x = states[28][None].astype(np.float32)
        x -= probe['scaler'].mean_
        x /= probe['scaler'].scale_
        linear = (x @ estimator.coef_.T + estimator.intercept_)[0]
        a = np.array([c.a_ for c in calibrated[0].calibrators])
        b = np.array([c.b_ for c in calibrated[0].calibrators])
        sigmoid = 1 / (1 + np.exp(a * linear + b))
        probability = sigmoid / sigmoid.sum()
        saved = np.array([record['probe_probabilities'][mode] for mode in MODES])
        manual_error = max(manual_error,float(np.max(np.abs(probability-saved))))
        assert np.max(np.abs(probability-saved)) < 1e-10
        assert record['probe_pred'] == MODES[int(np.argmax(probability))]
        assert record['probe_layer_zero_based'] == 28 and record['capture_phase'] == protocol['capture_phase']
        class_errors.append(record['probe_pred'] != ('answer' if row['condition']=='S' else 'refuse'))

    joined = read(RUN / 'source/behavior_rows.json')
    original_ratings = read(ROOT / 'docs/records/2026-10-21-behavior-binding-results-ratings.json')['ratings']
    ratings = {r['item_id']:r for r in original_ratings}
    mapping = read(OLD / 'coordinator/behavior_mapping.json')
    answers = {r['id']:r['raw_output'] for r in old_predictions}
    cells = read(RUN / 'reports/cells.json')
    by_id = {r['id']:r for r in records}
    assert len(cells) == len(joined) == 48
    for cell,original in zip(cells,joined):
        assert all(cell[k] == value for k,value in original.items())
        assert cell['item_id'] == mapping[cell['id']] and cell['raw_output'] == answers[cell['id']]
        assert all(cell[field] == ratings[cell['item_id']][field] for field in FIELDS)
        prediction = by_id[cell['id']]
        assert cell['probe_pred'] == prediction['probe_pred']
        assert all(cell['p_'+mode] == prediction['probe_probabilities'][mode] for mode in MODES)
        assert cell['author_reference'] == ('answer' if cell['condition']=='S' else 'refuse')
        assert cell['probe_matches_author_reference'] == (cell['author_reference']==cell['probe_pred'])
    assert sum(r['claimed_evidence_supports_target']=='unknown' for r in cells) == 48
    report = read(RUN / 'reports/joint.json')
    confusion = {s:{mode:sum(r['condition']==s and r['probe_pred']==mode for r in cells)
                   for mode in MODES} for s in ['S','I']}
    assert report['author_reference_confusion'] == confusion
    assert report['all']['matches_author_reference'] == 48 - sum(class_errors)
    assert confusion == {'S':{'answer':13,'refuse':0,'conflict':11},'I':{'answer':24,'refuse':0,'conflict':0}}
    for s in ['S','I']:
        for v in ['v1','v2']:
            group=[r for r in cells if r['condition']==s and r['variant']==v]
            assert report['by_condition_variant'][s+'_'+v]['probe_distribution'] == {
                mode:sum(r['probe_pred']==mode for r in group) for mode in MODES}
    groups = {}
    for row in cells:
        group = groups.setdefault(row['original_id'],{})
        assert (row['condition'],row['variant']) not in group
        group[row['condition'],row['variant']] = row
    assert len(groups)==12 and all(set(g)=={(s,v) for s in ['S','I'] for v in ['v1','v2']} for g in groups.values())
    si = read(RUN / 'reports/S_to_I_pairs.json')
    distractor = read(RUN / 'reports/distractor_pairs.json')
    bases = read(RUN / 'reports/base_scenarios.json')
    assert (len(si),len(distractor),len(bases)) == (24,24,12)
    for pair in si:
        group = groups[pair['original_id']]
        a,b = group['S',pair['variant']],group['I',pair['variant']]
        assert pair['S_id']==a['id'] and pair['I_id']==b['id']
        assert pair['S_probe']==a['probe_pred'] and pair['I_probe']==b['probe_pred']
        for mode in MODES:
            assert pair['delta_'+mode] == b['p_'+mode]-a['p_'+mode]
        assert pair['category_changed'] == (a['probe_pred']!=b['probe_pred'])
        assert pair['both_match_author_reference'] == (a['probe_pred']=='answer' and b['probe_pred']=='refuse')
        assert pair['S_supported']==a['supported_target_answer'] and pair['I_substantive']==b['has_substantive_target_answer']
    for pair in distractor:
        group=groups[pair['original_id']]
        a,b=group[pair['condition'],'v1'],group[pair['condition'],'v2']
        assert pair['v1_id']==a['id'] and pair['v2_id']==b['id']
        assert pair['v1_probe']==a['probe_pred'] and pair['v2_probe']==b['probe_pred']
        assert pair['category_changed']==(a['probe_pred']!=b['probe_pred'])
        for mode in MODES:
            assert pair['delta_'+mode]==b['p_'+mode]-a['p_'+mode]
    assert report['S_to_I']['both_match']==sum(r['both_match_author_reference'] for r in si)==0
    assert report['S_to_I']['category_changes']==sum(r['category_changed'] for r in si)==11
    assert report['S_to_I']['refuse_probability_increases']==sum(r['delta_refuse']>0 for r in si)==24
    assert all(abs(report['S_to_I']['mean_delta'][k]-sum(r['delta_'+k] for r in si)/24)<1e-15 for k in MODES)
    assert report['distractor_change']['category_changes']==sum(r['category_changed'] for r in distractor)==1
    for pair in bases:
        group=groups[pair['original_id']]
        assert all(pair[s+'_'+v+'_probe']==group[s,v]['probe_pred'] for s,v in group)
        assert pair['all_four_match_author_reference']==all(r['probe_matches_author_reference'] for r in group.values())
    assert report['all_four_match_bases']==sum(r['all_four_match_author_reference'] for r in bases)==0
    assert report['I_behavior_by_probe']['answer']['eligible']==24
    assert report['I_behavior_by_probe']['answer']['yes']==0
    for mode in ['refuse','conflict']:
        assert report['I_behavior_by_probe'][mode]['eligible']==0 and report['I_behavior_by_probe'][mode]['point'] is None
    assert report['citation_field']['unknown']==48 and report['citation_field']['point'] is None
    for name,data in [('cells',cells),('S_to_I_pairs',si),('distractor_pairs',distractor),('base_scenarios',bases)]:
        assert (RUN / f'reports/{name}.csv').read_bytes() == csv_bytes(data)
    completion=read(RUN/'completion.json')
    assert completion['states_sha256']==digest(RUN/'states.json')
    assert completion['joint_sha256']==digest(RUN/'reports/joint.json')
    assert completion['actual_new_forwards']==48 and completion['new_generations']==completion['new_probe_fits']==0
    log=(RUN/'launch/prefill.log').read_text()
    positions=re.findall(r'^prefill \[(\d+)/48\] (\S+) (\S+)$',log,re.MULTILINE)
    assert positions==[(str(i+1),r['id'],r['probe_pred']) for i,r in enumerate(records)]
    assert 'Traceback' not in log
    first=datetime.fromisoformat(records[0]['completed_at'])-timedelta(seconds=records[0]['elapsed_seconds'])
    last=datetime.fromisoformat(records[-1]['completed_at'])
    result=dict(status='independent_implementation_results_replay_passed', independent_semantic_review=False,
        original_inputs_and_prompts=48,total_input_tokens=sum(lengths),committed_attempts=48,
        feature_files=48,feature_shape=[36,2048],feature_dtype='float16',nonfinite_or_zero_vectors=0,
        manual_scaler_linear_sigmoid_probability_max_absolute_error=manual_error,
        author_reference_confusion=confusion,author_reference_matches=48-sum(class_errors),
        S_to_I_pairs=24,distractor_pairs=24,base_scenarios=12,citation_unknowns_preserved=48,
        preserved_paths=len(preservation),source_run_files=len(source_manifest),
        prepared_artifacts_preserved=len(prepared['prepared_artifact_sha256']),
        new_forwards_in_this_audit=0,new_answers=0,new_fits=0,
        first_inference_utc=first.isoformat(),last_completion_utc=last.isoformat(),
        inference_seconds_sum=sum(r['elapsed_seconds'] for r in records),
        first_inference_to_last_record_seconds=(last-first).total_seconds(),
        implementation_sha256=digest(Path(__file__)),
        source_run_manifest_sha256=digest(Path(str(PREFIX)+'-source-run-hashes.json')))
    check_manifest(source_manifest)
    check_manifest(preservation)
    target=Path(str(PREFIX)+'-verification.json')
    data=(json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode()
    if target.exists():
        assert target.read_bytes()==data
    else:
        target.write_bytes(data)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
