"""Supplemental frozen L28 prefill for the existing48 answers; no generation or fitting."""

import argparse
from collections import Counter
from datetime import datetime, timezone
from importlib.metadata import version
import json
import math
from pathlib import Path
import time

import numpy as np

import behavior_binding_study as source
import behavior_binding_results as behavior
import controlled_evidence_pilot as pilot

ROOT = source.ROOT
DEFAULT = ROOT / 'runs/qwen2.5-3b-behavior-binding-probe-v1'
SPEC = ROOT / 'prompts/behavior_binding_probe_v1.json'
BUDGET = ROOT / 'runs/semantic-transfer-shared-one-fit-budget-v1.json'
e = pilot.e
require, read, digest, save = source.require, source.read, source.digest, source.save
META = ['id', 'original_id', 'condition', 'variant']
MODES = ['answer', 'refuse', 'conflict']


def predict(probe, states):
    result = pilot.predict_probe(probe, states)
    result.pop('probe_decision_pre_first_token')
    probabilities = result['probe_probabilities']
    require(set(probabilities) == set(MODES) and all(math.isfinite(v) and 0 <= v <= 1
        for v in probabilities.values()) and abs(sum(probabilities.values()) - 1) < 1e-8,
        'Invalid probability vector')
    return result


def validate_states(states, shape):
    require(states.shape == tuple(shape) and states.dtype == np.float16
            and np.isfinite(states).all() and not np.any(np.all(states == 0, axis=1)),
            'Invalid feature shape/dtype/values')


def prompt_identity(row, tokenizer):
    text = e.render_input(source.renderer_inputs(row), 'free_answer', 'chat', tokenizer)
    tokens = e.encode(tokenizer, text, 'chat')['input_ids']
    return dict(prompt_sha256=source.sha(text), input_tokens=len(tokens),
                input_token_ids_sha256=source.sha(json.dumps(tokens)))


def prepared_sources():
    summary, joined, _ = behavior.compute()
    require(summary['reviewed_rows'] == 48 and summary['unknown_fields'] == 48,
            'Original behavior snapshot changed')
    preservation = read(ROOT / 'docs/records/2026-10-21-behavior-binding-preparation-preserved.json')
    preservation.update(read(ROOT / (behavior.PREFIX + '-source-run-hashes.json')))
    preservation.update(read(ROOT / (behavior.PREFIX + '-seal.json'))['files'])
    for path in (ROOT / 'docs/records').glob('2026-10-21-behavior-binding-results*'):
        preservation[str(path.relative_to(ROOT))] = digest(path)
    preservation[str(BUDGET.relative_to(ROOT))] = digest(BUDGET)
    return joined, dict(sorted(preservation.items()))


def prepare(run=DEFAULT, write=False):
    require(run.resolve() == DEFAULT.resolve(), 'Dedicated supplemental run directory required')
    spec = read(SPEC)
    require(spec['maximum_new_forwards'] == 48 and spec['new_generations'] == 0
            and spec['extra_smoke_forwards'] == 0 and spec['new_probe_fits'] == 0
            and spec['probe']['layer_zero_based'] == 28, 'Supplement scope changed')
    # The original collector verifies its immutable protocol and full model weights without loading a model.
    rows, original, tokenizer = source.prepare(write=False)
    source.validate_cache(source.DEFAULT, rows, original, tokenizer)
    require(len(read(source.DEFAULT / 'predictions.json')['records']) == 48, 'Original48 incomplete')
    require(spec['smoke_prefix_ids'] == original['smoke_prefix_ids'] == [r['id'] for r in rows[:4]],
            'Smoke must be original4 cells, included in48')
    joined, preservation = prepared_sources()
    probe, probe_hashes, old = pilot.probe_resources(original['model'])
    require(probe_hashes[spec['probe']['source']] == spec['probe']['sha256'], 'Frozen probe differs')
    require(old['model'] == original['model'] and old['feature_convention'] == e.FEATURE_CONVENTION,
            'Probe backbone/convention differs')
    require(all(original['model_files_sha256'][name] == value
        for name,value in old['reference_specs']['val']['model_files'].items()),
        'Original probe model/tokenizer metadata differs')
    require(pilot.free.feature_shape(original['model']) == [36,2048], 'Backbone dimensions differ')
    # Complete original48 renderings must agree with the actual saved generation token IDs and prompts.
    originals = {r['id']: r for r in read(source.DEFAULT / 'predictions.json')['records']}
    identities = []
    for row in rows:
        identity = prompt_identity(row, tokenizer)
        require(all(originals[row['id']][k] == v for k, v in identity.items()), 'Original prompt/token mismatch')
        identities.append(dict(id=row['id'], **identity))
    implementations = set(original['implementation_sha256']) | {
        'scripts/behavior_binding_probe.py', 'scripts/run_behavior_binding_probe.sh',
        'tests/test_behavior_binding_probe.py', 'scripts/behavior_binding_results.py',
        'scripts/controlled_evidence_pilot.py', 'scripts/controlled_evidence_materials.py',
        'scripts/free_answer_study.py', 'scripts/free_answer_review.py'}
    sources = dict(probe_hashes)
    for path in [SPEC, source.DEFAULT / 'protocol.json', source.DEFAULT / 'predictions.json',
                 source.DEFAULT / 'materials/inputs.json', source.DEFAULT / 'preflight.json', BUDGET]:
        sources[str(path.relative_to(ROOT))] = digest(path)
    preservation.update(probe_hashes)
    history_path = ROOT / 'runs/qwen2.5-3b-probe-support-expression-v1/states.json'
    sources[str(history_path.relative_to(ROOT))] = digest(history_path)
    timings = [r for r in read(history_path)['records'] if r['origin'] == 'new_forward'][1:]
    require(len(timings) == 39, 'Historical timing source changed')
    ratio = max(r['elapsed_seconds'] / r['input_tokens'] for r in timings)
    total_tokens = sum(r['input_tokens'] for r in identities)
    protocol = dict(task=spec['task'], specification_sha256=digest(SPEC), model=original['model'],
        ordered_ids=[r['id'] for r in rows], smoke_prefix_ids=spec['smoke_prefix_ids'],
        implementation_sha256={p: digest(ROOT / p) for p in sorted(implementations)},
        source_sha256=dict(sorted(sources.items())), model_files_sha256=original['model_files_sha256'],
        runtime_versions={n: version(n) for n in ['torch', 'transformers', 'numpy', 'scikit-learn']},
        feature_shape=pilot.free.feature_shape(original['model']), feature_convention=e.FEATURE_CONVENTION,
        frozen_probe_layer=28, probe_sha256=spec['probe']['sha256'], instruction=e.FREE_INSTRUCTION,
        format='chat', dtype='bfloat16', attention='sdpa', use_cache=True, batch_size=1,
        new_generations=0, new_probe_fits=0, maximum_new_forwards=48, original_fit_budget_remaining=0,
        capture_phase='retrospectively_recomputed_input_prefill_without_generation',
        original_generation_simultaneous_probe=False, no_original_binding_state_bridge=True,
        author_reference_history_exposed=True, independent_semantic_approval=False,
        original_formal_gate_changed=False, no_confirmation_access=True,
        inputs_sha256=source.sha(source.encoded(rows).decode()),
        joined_behavior_sha256=source.sha(source.encoded(joined).decode()),
        preserved_sha256=source.sha(source.encoded(dict(sorted(preservation.items()))).decode()))
    preflight = dict(status='prepared_not_started', cells=48, scenarios=12, prompts=identities,
        min_input_tokens=min(r['input_tokens'] for r in identities),
        max_input_tokens=max(r['input_tokens'] for r in identities), total_input_tokens=total_tokens,
        new_forwards=48, extra_smoke_forwards=0, new_generations=0, new_probe_fits=0,
        original_answers_reused=48, no_model_weights_loaded=True, gpu_calls=0,
        historical_forwards_excluding_first=len(timings), historical_max_seconds_per_input_token=ratio,
        planned_minutes=[math.ceil(3 + 2 * total_tokens * ratio / 60),
                         math.ceil(10 + 10 * total_tokens * ratio / 60)],
        timing_limit='Historical prefill throughput plus load/IO allowance only, not a new GPU measurement; user launches because under10min cannot be guaranteed.')
    for name, value in [('protocol.json', protocol), ('specification.json', spec),
                        ('preflight.json', preflight), ('materials/inputs.json', rows),
                        ('source/behavior_rows.json', joined),
                        ('source/preserved.json', dict(sorted(preservation.items())))]:
        save(run / name, value, immutable=True, verify=not write)
    return rows, protocol, tokenizer, probe


def validate_cache(run, rows, protocol, probe):
    records = []
    ph = digest(run / 'protocol.json')
    if (run / 'states.json').exists():
        stored = read(run / 'states.json')
        require(stored['protocol_sha256'] == ph, 'Cache protocol mismatch')
        records = stored['records']
    require(len(records) <= len(rows) == 48, 'Forward budget exceeded')
    attempts = sorted((run / 'forward_attempts').glob('*.json'))
    require(len(attempts) == len(records), 'Uncommitted forward attempt; inspect without retry')
    expected_files = {f'features/{i:04d}.npy' for i in range(len(records))}
    actual_files = {str(p.relative_to(run)) for p in (run / 'features').rglob('*') if p.is_file()}
    require(actual_files == expected_files, 'Orphan or missing feature; inspect without retry')
    identities = {r['id']: r for r in read(run / 'preflight.json')['prompts']}
    for i, (row, record) in enumerate(zip(rows, records)):
        require(all(record[k] == row[k] for k in META), 'Cache identity/order mismatch')
        attempt = read(attempts[i])
        require(attempts[i].name == f'{i:04d}.json' and attempt == dict(index=i, id=row['id'],
            protocol_sha256=ph, phase=protocol['capture_phase']), 'Forward attempt mismatch')
        require(record['capture_phase'] == protocol['capture_phase']
                and record['probe_layer_zero_based'] == 28, 'Capture phase/layer mismatch')
        require(all(record[k] == identities[row['id']][k] for k in
            ['prompt_sha256', 'input_tokens', 'input_token_ids_sha256']), 'Cached prompt/token mismatch')
        require(record['feature_file'] == f'features/{i:04d}.npy', 'Feature path mismatch')
        path = run / record['feature_file']
        require(digest(path) == record['feature_sha256'], 'Feature hash mismatch')
        states = np.load(path, allow_pickle=False)
        validate_states(states, protocol['feature_shape'])
        expected = predict(probe, states)
        require(record['probe_pred'] == expected['probe_pred'], 'Cached probe class mismatch')
        probabilities = record['probe_probabilities']
        require(set(probabilities) == set(MODES) and all(math.isfinite(v) and 0 <= v <= 1
            for v in probabilities.values()) and abs(sum(probabilities.values()) - 1) < 1e-8,
            'Invalid probability vector')
        require(all(abs(probabilities[k] - expected['probe_probabilities'][k]) < 1e-9 for k in MODES),
                'Cached probability replay mismatch')
        require(math.isfinite(record['elapsed_seconds']) and record['elapsed_seconds'] >= 0,
                'Invalid timing')
        datetime.fromisoformat(record['completed_at'])
    return records


def smoke_gate(run, records, verify=False):
    require(len(records) >= 4, 'Technical smoke incomplete')
    value = dict(status='technical_smoke_passed', ids=[r['id'] for r in records[:4]],
        cells_in_total48=4, semantic_accuracy_gate=False, protocol_sha256=digest(run / 'protocol.json'))
    save(run / 'smoke_gate.json', value, immutable=True, verify=verify)


def capture_prefill(model, tokenizer, row):
    import torch
    prompt = e.render_input(source.renderer_inputs(row), 'free_answer', 'chat', tokenizer)
    inputs = e.encode(tokenizer, prompt, 'chat', return_tensors='pt').to(model.device)
    torch.cuda.synchronize()
    started = time.monotonic()
    with e.LastPromptCapture(model) as capture, torch.inference_mode():
        # First input pass only. No language-model head, generation, answer tokens or probe feedback.
        output = model.model(**inputs, use_cache=True, output_hidden_states=False)
    states = capture.array()
    del output, inputs
    torch.cuda.synchronize()
    return states, time.monotonic() - started


def collect(run, rows, protocol, tokenizer, probe):
    records = validate_cache(run, rows, protocol, probe)
    if len(records) >= 4:
        smoke_gate(run, records)
    model = None
    identities = {r['id']:r for r in read(run / 'preflight.json')['prompts']}
    try:
        for row in rows[len(records):]:
            if model is None:
                pilot.s.assert_gpu_idle()
                model = e.load_model(protocol['model'])
            i = len(records)
            save(run / f'forward_attempts/{i:04d}.json', dict(index=i, id=row['id'],
                 protocol_sha256=digest(run / 'protocol.json'), phase=protocol['capture_phase']), immutable=True)
            states, elapsed = capture_prefill(model, tokenizer, row)
            validate_states(states, protocol['feature_shape'])
            feature = f'features/{i:04d}.npy'
            e.save_array(run / feature, states)
            record = dict(**{k:row[k] for k in META},
                **{k:v for k,v in identities[row['id']].items() if k != 'id'},
                feature_file=feature, feature_sha256=digest(run / feature),
                capture_phase=protocol['capture_phase'], elapsed_seconds=elapsed,
                completed_at=datetime.now(timezone.utc).isoformat(), **predict(probe, states))
            records.append(record)
            save(run / 'states.json', dict(protocol_sha256=digest(run / 'protocol.json'), records=records))
            save(run / 'progress.json', dict(status='running', saved=len(records), target=48, last_id=row['id']))
            print(f'prefill [{len(records)}/48] {row["id"]} {record["probe_pred"]}', flush=True)
            if len(records) == 4:
                validate_cache(run, rows, protocol, probe)
                smoke_gate(run, records)
    except Exception as error:
        save(run / 'last_failure.json', dict(stage='prefill', error=str(error),
            committed=len(records), id=row['id']))
        raise
    finally:
        if model is not None:
            del model
    return records


def summarize_joint(joined, records):
    require(len(joined) == len({r['id'] for r in joined}) == len(records) == 48,
            'All48 unique cells required')
    predictions = {r['id']:r for r in records}
    require(len(predictions) == 48 and set(predictions) == {r['id'] for r in joined}, 'Joint IDs mismatch')
    cells = []
    for original in joined:
        record = predictions[original['id']]
        require(all(record[k] == original[k] for k in META), 'Joint condition/base mismatch')
        expected = 'answer' if original['condition'] == 'S' else 'refuse'
        cells.append(dict(**original, author_reference=expected, probe_pred=record['probe_pred'],
            **{'p_'+k:record['probe_probabilities'][k] for k in MODES},
            probe_matches_author_reference=record['probe_pred'] == expected,
            feature_sha256=record['feature_sha256'], prompt_sha256=record['prompt_sha256'],
            probe_capture_phase=record['capture_phase']))
    groups = {}
    for row in cells:
        group = groups.setdefault(row['original_id'], {})
        require((row['condition'], row['variant']) not in group, 'Duplicate four-cell slot')
        group[row['condition'],row['variant']] = row
    require(len(groups) == 12 and all(set(g) == {(s,v) for s in ['S','I'] for v in ['v1','v2']}
        for g in groups.values()), 'Incomplete12 four-cell scenarios')
    si, distractor, bases = [], [], []
    for base, group in sorted(groups.items()):
        bases.append(dict(original_id=base, all_four_match_author_reference=all(
            r['probe_matches_author_reference'] for r in group.values()),
            **{s+'_'+v+'_probe':group[s,v]['probe_pred'] for s,v in group}))
        for variant in ['v1','v2']:
            a,b = group['S',variant],group['I',variant]
            si.append(dict(original_id=base, variant=variant, S_id=a['id'], I_id=b['id'],
                S_probe=a['probe_pred'], I_probe=b['probe_pred'],
                both_match_author_reference=a['probe_matches_author_reference'] and b['probe_matches_author_reference'],
                category_changed=a['probe_pred'] != b['probe_pred'],
                **{'delta_'+k:b['p_'+k]-a['p_'+k] for k in MODES},
                S_supported=a['supported_target_answer'], I_substantive=b['has_substantive_target_answer'],
                S_citation=a['claimed_evidence_supports_target'], I_citation=b['claimed_evidence_supports_target']))
        for condition in ['S','I']:
            a,b = group[condition,'v1'],group[condition,'v2']
            distractor.append(dict(original_id=base, condition=condition, v1_id=a['id'], v2_id=b['id'],
                v1_probe=a['probe_pred'], v2_probe=b['probe_pred'],
                category_changed=a['probe_pred'] != b['probe_pred'],
                **{'delta_'+k:b['p_'+k]-a['p_'+k] for k in MODES},
                v1_adopts_distractor=a['adopts_cell_distractor_value'],
                v2_adopts_distractor=b['adopts_cell_distractor_value']))
    def counts(rows):
        return dict(cells=len(rows), matches_author_reference=sum(r['probe_matches_author_reference'] for r in rows),
                    probe_distribution={k:sum(r['probe_pred']==k for r in rows) for k in MODES})
    summary = dict(status='retrospective_exposed_frozen_probe_diagnostic_complete',
        independent_gold=False, formal_labels_added=0, new_generations=0, new_probe_fits=0,
        author_reference_confusion={s:{k:sum(r['condition']==s and r['probe_pred']==k for r in cells)
            for k in MODES} for s in ['S','I']},
        all=counts(cells), by_condition={s:counts([r for r in cells if r['condition']==s]) for s in ['S','I']},
        by_condition_variant={s+'_'+v:counts([r for r in cells if r['condition']==s and r['variant']==v])
            for s in ['S','I'] for v in ['v1','v2']},
        behavior_by_condition={s:{f:behavior.rate([r for r in cells if r['condition']==s],f)
            for f in behavior.FIELDS} for s in ['S','I']},
        citation_field=behavior.rate(cells,'claimed_evidence_supports_target'),
        S_to_I=dict(pairs=24, both_match=sum(r['both_match_author_reference'] for r in si),
            category_changes=sum(r['category_changed'] for r in si),
            mean_delta={k:sum(r['delta_'+k] for r in si)/24 for k in MODES},
            refuse_probability_increases=sum(r['delta_refuse']>0 for r in si)),
        distractor_change=dict(pairs=24, category_changes=sum(r['category_changed'] for r in distractor),
            by_condition={s:dict(pairs=12, category_changes=sum(r['category_changed'] for r in distractor if r['condition']==s),
                mean_delta={k:sum(r['delta_'+k] for r in distractor if r['condition']==s)/12 for k in MODES}) for s in ['S','I']}),
        all_four_match_bases=sum(r['all_four_match_author_reference'] for r in bases),
        I_behavior_by_probe={}, intervals_computed=False,
        limitation='Post-answer state recomputation; exposed construction reference; only12 scenarios/one sentence family; not independent semantic accuracy, calibration, natural-document or causal evidence. Correct primary behavior was already observed. No inappropriate-behavior case is created by this readout.')
    for mode in MODES:
        rows = [r for r in cells if r['condition']=='I' and r['probe_pred']==mode]
        summary['I_behavior_by_probe'][mode] = behavior.rate(rows, 'has_substantive_target_answer') if rows else dict(
            eligible=0, yes=0, no=0, unknown=0, point=None, identification_lower=None, identification_upper=None)
    return summary, cells, si, distractor, bases


def finish(run, rows, protocol, probe, verify=False):
    records = validate_cache(run, rows, protocol, probe)
    require(len(records) == 48, 'All48 states required before joint analysis')
    smoke_gate(run, records, verify=verify)
    joined = read(run / 'source/behavior_rows.json')
    report, cells, si, distractor, bases = summarize_joint(joined, records)
    report.update(protocol_sha256=digest(run / 'protocol.json'), states_sha256=digest(run / 'states.json'),
        actual_new_forwards=48, inference_seconds_sum=sum(r['elapsed_seconds'] for r in records),
        first_completed_at=records[0]['completed_at'], last_completed_at=records[-1]['completed_at'],
        preserved_paths=len(read(run / 'source/preserved.json')))
    for name,value in [('reports/joint.json',report), ('reports/cells.json',cells),
            ('reports/S_to_I_pairs.json',si), ('reports/distractor_pairs.json',distractor),
            ('reports/base_scenarios.json',bases)]:
        save(run / name,value,immutable=True,verify=verify)
    for name,value in [('cells',cells),('S_to_I_pairs',si),('distractor_pairs',distractor),('base_scenarios',bases)]:
        path = run / f'reports/{name}.csv'
        data = behavior.csv_text(value).encode()
        if path.exists() or verify:
            require(path.exists() and path.read_bytes()==data,'Frozen CSV mismatch')
        else:
            path.write_bytes(data)
    save(run / 'completion.json',dict(status=report['status'],protocol_sha256=report['protocol_sha256'],
        states_sha256=report['states_sha256'],joint_sha256=digest(run / 'reports/joint.json'),
        actual_new_forwards=48,new_generations=0,new_probe_fits=0),immutable=True,verify=verify)
    if not verify:
        save(run / 'progress.json',dict(status=report['status'],saved=48,target=48))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',choices=['prepare','verify','run','analyze','verify-results','all'],default='verify')
    args = parser.parse_args()
    from contextlib import nullcontext
    readonly = args.stage in ['verify','verify-results']
    with nullcontext() if readonly else e.legacy.run_lock(DEFAULT):
        rows, protocol, tokenizer, probe = prepare(write=args.stage=='prepare')
        if args.stage in ['run','all']:
            collect(DEFAULT,rows,protocol,tokenizer,probe)
        if args.stage in ['analyze','verify-results','all']:
            report = finish(DEFAULT,rows,protocol,probe,verify=args.stage=='verify-results')
            print(json.dumps(report,ensure_ascii=False))
        else:
            records = validate_cache(DEFAULT,rows,protocol,probe)
            print(json.dumps(dict(stage=args.stage,prepared_cells=48,committed_new_forwards=len(records),
                                  new_answers=0,new_fits=0)))


if __name__ == '__main__':
    main()
