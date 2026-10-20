"""Frozen-probe input-shift diagnostic; prepare/verify on CPU, user launches GPU."""

import argparse
from collections import Counter
from contextlib import nullcontext
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import time

import numpy as np

import controlled_evidence_pilot as p

ROOT, e, m = p.ROOT, p.e, p.m
SPEC = ROOT / 'prompts/probe_input_shift_v1.json'
DEFAULT = ROOT / 'runs/qwen2.5-3b-probe-input-shift-v1'
SMOKE = ROOT / 'runs/qwen2.5-3b-probe-input-shift-smoke-v1'
require = p.require


def build():
    spec = e.read_json(SPEC)
    pilot_spec, pilot, _, provenance = m.build()
    require(spec['base_order'] == [u['base_id'] for u in pilot_spec['units']], 'Base order differs')
    originals = {r['id']: r for r in map(json.loads, m.SOURCE.read_text().splitlines())}
    supports = {r['original_id']: r for r in pilot if r['condition'] == 'S'}
    slots = {r['original_id']: r['target_slots'] for r in provenance}
    old_records = {r['id']: r for r in e.read_json(p.PROBE_SOURCE / 'chat/val/states.json')['records']}
    pilot_records = {r['id']: r for r in e.read_json(p.DEFAULT / 'free_answer/predictions.json')['records']}
    rows, edits = [], []
    for number, oid in enumerate(spec['base_order'], 1):
        original, authored = originals[oid + '_answer'], supports[oid]
        variants = {'O': original['docs'], 'P': authored['docs']}
        if oid in spec['neutral_edits']:
            edit = spec['neutral_edits'][oid]
            targets = slots[oid]
            changed = list(authored['docs'])
            for slot in targets:
                before = changed[slot - 1]
                changed[slot - 1] = m.replace_once(before, edit['old'], edit['new'])
                require(edit['retained_positive'] in before and edit['retained_positive'] in changed[slot - 1],
                        'Explicit positive premise must survive deletion')
                start = before.index(edit['old'])
                edits.append(dict(original_id=oid, doc_slot=slot, start=start, end=start + len(edit['old']),
                                  before=edit['old'], after=edit['new'], reason=edit['reason'],
                                  positive_quote=edit['retained_positive'],
                                  positive_start_after=changed[slot - 1].index(edit['retained_positive'])))
            require([i + 1 for i, (a, b) in enumerate(zip(authored['docs'], changed)) if a != b] == sorted(targets),
                    'Neutral edit must touch only two target slots')
            variants['N'] = changed
        for q, d in spec['cell_order']:
            if d not in variants:
                continue
            source = None
            if (q, d) == ('O', 'O'):
                source = dict(base=str((p.PROBE_SOURCE / 'chat/val').relative_to(ROOT)), record=old_records[original['id']])
            if (q, d) == ('A', 'P'):
                source = dict(base=str((p.DEFAULT / 'free_answer').relative_to(ROOT)), record=pilot_records[authored['id']])
            rows.append(dict(id=f'shift{number:02d}_q{q}_d{d}', original_id=oid,
                             question_level=q, document_level=d,
                             question=original['question'] if q == 'O' else authored['question'],
                             docs=list(variants[d]), source=source))
    require(len(rows) == 52 and sum(r['source'] is not None for r in rows) == 20, 'Expected 52 cells / 20 cached endpoints')
    require(len(edits) == 12, 'Expected six pre-specified paired deletions')
    return spec, rows, edits


def prompt(row, tokenizer):
    return e.render_input(row, 'free_answer', 'chat', tokenizer)


def validate_states(states, shape):
    require(states.shape == tuple(shape) and states.dtype == np.float16 and np.isfinite(states).all()
            and not np.any(np.all(states == 0, axis=1)), 'Invalid feature shape/dtype/values')


def source_state(row, tokenizer, model):
    source = row['source']
    require(source is not None, 'No reusable source')
    record = source['record']
    text = prompt(row, tokenizer)
    require(record['prompt_sha256'] == e.text_hash(text) and
            record['input_tokens'] == len(e.encode(tokenizer, text, 'chat')['input_ids']), 'Cached endpoint prompt differs')
    path = ROOT / source['base'] / record['feature_file']
    require(m.digest(path) == record['feature_sha256'], 'Cached endpoint feature hash differs')
    states = np.load(path, allow_pickle=False)
    validate_states(states, p.free.feature_shape(model))
    return states


def prepare(args, write=True):
    spec, all_rows, edits = build()
    rows = [r for r in all_rows if r['original_id'] == spec['smoke_base']] if args.smoke else all_rows
    probe, hashes, old = p.probe_resources(args.model)
    # Verify the pilot backbone, not just the path to the weights.
    signature = e.repro.feature_spec(argparse.Namespace(model=args.model, template='P0'),
                                     [dict(r, label=-1) for r in all_rows], m.SOURCE)
    for key in ['model', 'model_files', 'weights', 'template_sha256', 'renderer_sha256', 'render_policy']:
        require(signature[key] == old['reference_specs']['val'][key], f'Backbone differs: {key}')
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(args.model, local_files_only=True)
    for row in all_rows:
        if row['source']:
            source_state(row, tokenizer, args.model)
    pilot_fingerprints = e.read_json(p.DEFAULT / 'protocol.json')['implementation_sha256']
    for name, expected in pilot_fingerprints.items():
        require(m.digest(ROOT / name) == expected, f'Pilot frozen dependency differs: {name}')
    files = set(pilot_fingerprints)
    files.update(['scripts/probe_input_shift.py', 'scripts/run_probe_input_shift.sh',
                  'scripts/run_probe_input_shift_review.sh', 'prompts/probe_input_shift_v1.json'])
    source_files = dict(hashes)
    for path in [m.SOURCE, p.DEFAULT / 'protocol.json', p.DEFAULT / 'materials/inputs.json', p.DEFAULT / 'free_answer/predictions.json']:
        source_files[str(path.relative_to(ROOT))] = m.digest(path)
    protocol = dict(schema_version=1, task='probe_input_shift_development', model=args.model, smoke=args.smoke,
                    specification=spec, backbone_signature=signature,
                    implementation_sha256={f: m.digest(ROOT / f) for f in sorted(files)},
                    source_sha256=source_files, inputs_sha256=e.text_hash(m.json_text(rows)),
                    edits_sha256=e.text_hash(m.json_text(edits)), selected_ids=[r['id'] for r in rows],
                    feature_convention=e.FEATURE_CONVENTION, frozen_probe_layer=28,
                    runtime_versions={k: e.version(k) for k in ['torch', 'transformers', 'numpy', 'scikit-learn']},
                    forward='decoder-only prefill, use_cache=False, BF16/SDPA; no LM head, no generation, no feedback',
                    semantic_labels='No semantic labels or accuracy: O sources are published-answer configurations, not a new gold judgment.',
                    bridge='Smoke recomputes both known endpoints for val_31, validates state/probability tolerances before full.',
                    reuse='20 exact-prompt cached endpoints, 32 new cells; smoke all6 recomputed, no gate on semantic scores.',
                    no_training='No fit, calibration, layer or threshold search; no original test/confirmation access.')
    all_lengths = {r['id']: len(e.encode(tokenizer, prompt(r, tokenizer), 'chat')['input_ids']) for r in all_rows}
    lengths = {r['id']: all_lengths[r['id']] for r in rows}
    context = e.read_json(Path(args.model) / 'config.json')['max_position_embeddings']
    require(max(lengths.values()) <= context, 'Context overflow; never truncate')
    historical = [r['source']['record'] for r in all_rows if r['question_level'] == r['document_level'] == 'O']
    historical_max_seconds_per_input_token = max(r['elapsed_seconds'] / r['input_tokens'] for r in historical)
    planned_tokens = sum(all_lengths[r['id']] for r in all_rows if r['source'] is None) + sum(
        all_lengths[r['id']] for r in all_rows if r['original_id'] == spec['smoke_base'])
    capacity_seconds = historical_max_seconds_per_input_token * planned_tokens
    planning = [math.ceil(3 + 2 * capacity_seconds / 60), math.ceil(8 + 10 * capacity_seconds / 60)]
    pre = dict(status='cpu_preflight_passed', cells=len(rows), input_tokens=lengths,
               max_input_tokens=max(lengths.values()), context_tokens=context,
               expected_new_forwards=6 if args.smoke else 32, reused_endpoints=0 if args.smoke else 20,
               whole_smoke_plus_full_forward_count=38, planned_whole_minutes=planning,
               planned_new_input_tokens_including_smoke=planned_tokens,
               historical_max_seconds_per_input_token=historical_max_seconds_per_input_token,
               timing='Capacity estimate from max elapsed/input-token over ten old cached original prefill records; 2x/10x allowances +3/8min load/IO. Attention cost is not linear in input length; not a new GPU benchmark. User launches; no guarantee under10 minutes.')
    artifacts = {'protocol.json': m.json_text(protocol), 'materials/inputs.json': m.json_text(rows),
                 'materials/edits.json': m.json_text(edits), 'preflight.json': m.json_text(pre)}
    for name, text in artifacts.items():
        if write:
            m.write_new(args.run_dir / name, text)
        else:
            require((args.run_dir / name).read_bytes() == text.encode(), f'Frozen artifact differs: {name}')
    if write and not (args.run_dir / 'progress.json').exists():
        e.repro.write_json(args.run_dir / 'progress.json', dict(status='prepared_not_started', saved=0, target=len(rows)))
    return spec, rows, probe, tokenizer, protocol


def prediction(probe, states):
    result = p.predict_probe(probe, states)
    result.pop('probe_decision_pre_first_token')
    return result


def cache(args, rows, probe, tokenizer):
    path = args.run_dir / 'states.json'
    if not path.exists():
        return []
    value = e.read_json(path)
    require(value['protocol_sha256'] == m.digest(args.run_dir / 'protocol.json') and len(value['records']) <= len(rows), 'Cache protocol/count differs')
    records = value['records']
    for row, record in zip(rows, records):
        require(all(record[k] == row[k] for k in ['id', 'original_id', 'question_level', 'document_level']), 'Cache identity/order differs')
        require(record['prompt_sha256'] == e.text_hash(prompt(row, tokenizer)), 'Cached prompt differs')
        require(record['input_tokens'] == len(e.encode(tokenizer, prompt(row, tokenizer), 'chat')['input_ids']), 'Token count differs')
        require(record['origin'] == ('new_forward' if args.smoke or row['source'] is None else 'reused_endpoint'), 'Source origin differs')
        states = np.load(args.run_dir / record['feature_file'], allow_pickle=False)
        validate_states(states, p.free.feature_shape(args.model))
        require(m.digest(args.run_dir / record['feature_file']) == record['feature_sha256'], 'New feature hash differs')
        expected = prediction(probe, states)
        require(record['capture_phase'] == 'decoder_prefill_without_generation', 'Unexpected generation stage')
        require(record['probe_pred'] == expected['probe_pred'] and record['probe_layer_zero_based'] == 28, 'Probe label differs')
        require(all(abs(record['probe_probabilities'][k] - expected['probe_probabilities'][k]) < 1e-9 for k in e.MODES), 'Probe probabilities differ')
        if record['origin'] == 'reused_endpoint':
            require(np.array_equal(states, source_state(row, tokenizer, args.model)), 'Copied source feature differs')
    return records


def bridge_error(left, right, probe):
    relative = np.linalg.norm(left.astype(np.float32) - right.astype(np.float32), axis=1) / np.maximum(np.linalg.norm(right.astype(np.float32), axis=1), 1e-12)
    a, b = prediction(probe, left), prediction(probe, right)
    return dict(max_layer_relative_l2=float(max(relative)),
                max_probability_absolute_error=max(abs(a['probe_probabilities'][k] - b['probe_probabilities'][k]) for k in e.MODES))


def smoke_gate(args, spec, rows, records, probe, tokenizer):
    require(len(rows) == len(records) == 6 and all(r['origin'] == 'new_forward' for r in records), 'Smoke incomplete')
    checks = []
    for row, record in zip(rows, records):
        if row['source']:
            actual = np.load(args.run_dir / record['feature_file'], allow_pickle=False)
            error = bridge_error(actual, source_state(row, tokenizer, args.model), probe)
            require(all(error[k] <= limit for k, limit in spec['bridge_tolerances'].items()), f'Endpoint prefill bridge failed: {row["id"]}: {error}')
            checks.append(dict(id=row['id'], **error))
    require(len(checks) == 2, 'Expected two endpoint bridges')
    return dict(status='technical_smoke_passed', forward_cells=6, bridges=checks, semantic_accuracy_gate=False)


def require_smoke(args, protocol):
    smoke_args = argparse.Namespace(run_dir=SMOKE, model=args.model, smoke=True)
    ss, rr, pp, tt, proto = prepare(smoke_args, write=False)
    require(proto['implementation_sha256'] == protocol['implementation_sha256'] and proto['source_sha256'] == protocol['source_sha256'], 'Smoke belongs to another setup')
    gate = smoke_gate(smoke_args, ss, rr, cache(smoke_args, rr, pp, tt), pp, tt)
    require(gate == e.read_json(SMOKE / 'smoke_gate.json'), 'Smoke gate differs')


def run(args, spec, rows, probe, tokenizer, protocol):
    if not args.smoke:
        require_smoke(args, protocol)
    records = cache(args, rows, probe, tokenizer)
    model = None
    try:
        for row in rows[len(records):]:
            is_new = args.smoke or row['source'] is None
            started = time.monotonic()
            if not is_new:
                states = source_state(row, tokenizer, args.model)
            else:
                import torch
                if model is None:
                    p.s.assert_gpu_idle()
                    model = e.load_model(args.model)
                inputs = e.encode(tokenizer, prompt(row, tokenizer), 'chat', return_tensors='pt').to(model.device)
                torch.cuda.synchronize()
                with e.LastPromptCapture(model) as capture, torch.inference_mode():
                    model.model(**inputs, use_cache=False, output_hidden_states=False)
                states = capture.array()
                torch.cuda.synchronize()
                del inputs
            validate_states(states, p.free.feature_shape(args.model))
            relative = f'features/{len(records):04d}.npy'
            e.save_array(args.run_dir / relative, states)
            record = {k: row[k] for k in ['id', 'original_id', 'question_level', 'document_level']}
            record.update(prompt_sha256=e.text_hash(prompt(row, tokenizer)),
                          input_tokens=len(e.encode(tokenizer, prompt(row, tokenizer), 'chat')['input_ids']),
                          origin='new_forward' if is_new else 'reused_endpoint',
                          feature_file=relative, feature_sha256=m.digest(args.run_dir / relative),
                          elapsed_seconds=time.monotonic() - started, completed_at=datetime.now(timezone.utc).isoformat(),
                          capture_phase='decoder_prefill_without_generation', **prediction(probe, states))
            records.append(record)
            e.repro.write_json(args.run_dir / 'states.json', dict(protocol_sha256=m.digest(args.run_dir / 'protocol.json'), records=records))
            e.repro.write_json(args.run_dir / 'progress.json', dict(status='running', saved=len(records), target=len(rows), last_id=row['id']))
            print(f'prefill [{len(records)}/{len(rows)}] {row["id"]} {record["origin"]}', flush=True)
    except Exception as error:
        e.repro.write_json(args.run_dir / 'last_failure.json', dict(stage='prefill_or_source', id=row['id'], error=str(error)))
        raise
    finally:
        if model is not None:
            del model
            import torch
            torch.cuda.empty_cache()
    return records


def report(rows, records):
    require(len(rows) == len(records), 'Incomplete extraction')
    lookup = {r['id']: r for r in records}
    groups = {}
    for row in rows:
        groups.setdefault(row['original_id'], {})[row['question_level'] + row['document_level']] = lookup[row['id']]
    comparisons = []
    directions = [('AO', 'OO', 'question_on_original_docs'), ('AP', 'OP', 'question_on_pilot_docs'),
                  ('AN', 'ON', 'question_on_neutral_docs'), ('OP', 'OO', 'document_bundle_original_question'),
                  ('AP', 'AO', 'document_bundle_adapted_question'), ('ON', 'OP', 'remove_negatives_original_question'),
                  ('AN', 'AP', 'remove_negatives_adapted_question')]
    for oid, group in groups.items():
        for left, right, name in directions:
            if left in group and right in group:
                a, b = group[left], group[right]
                comparisons.append(dict(original_id=oid, contrast=name, direction=f'{left} minus {right}',
                                        left_id=a['id'], right_id=b['id'], left_pred=a['probe_pred'], right_pred=b['probe_pred'],
                                        token_delta=a['input_tokens'] - b['input_tokens'],
                                        probability_delta={k: a['probe_probabilities'][k] - b['probe_probabilities'][k] for k in e.MODES}))
    aggregate = {}
    for name in dict.fromkeys(c['contrast'] for c in comparisons):
        selected = [c for c in comparisons if c['contrast'] == name]
        aggregate[name] = dict(n_pairs=len(selected), changed_labels=sum(c['left_pred'] != c['right_pred'] for c in selected),
                               mean_probability_delta={k: sum(c['probability_delta'][k] for c in selected) / len(selected) for k in e.MODES})
    by_cell = {cell: dict(n=sum(r['question_level'] + r['document_level'] == cell for r in records),
                         predictions=dict(Counter(r['probe_pred'] for r in records if r['question_level'] + r['document_level'] == cell)))
               for cell in ['OO', 'AO', 'OP', 'AP', 'ON', 'AN'] if any(r['question_level'] + r['document_level'] == cell for r in records)}
    return dict(status='prefill_diagnostic_complete', cells=len(records), by_cell=by_cell, contrasts=aggregate, paired=comparisons,
                new_forwards=sum(r['origin'] == 'new_forward' for r in records),
                reused_endpoints=sum(r['origin'] == 'reused_endpoint' for r in records),
                generated_answers=0, trained_probes=0,
                limitation='Endpoint-informed exposed development diagnostic. O-to-P bundles facts/targets/distractors/order; Q changes can change scope; N deletes redundant negatives and changes length. No semantic accuracy, behavior result, population or hidden-state causal claim.')


def endpoints(args, rows, probe, tokenizer, write):
    endpoints = []
    for row in rows:
        if row['source']:
            states = source_state(row, tokenizer, args.model)
            endpoints.append(dict(id=row['id'], original_id=row['original_id'], question_level=row['question_level'],
                                  document_level=row['document_level'], input_tokens=row['source']['record']['input_tokens'],
                                  **prediction(probe, states)))
    return dict(status='cached_endpoint_cpu_replay_complete', endpoint_count=len(endpoints),
                new_gpu_forwards=0, endpoints=endpoints,
                limitation='OO and AP differ jointly in question, documents, answer facts, distractors/order; their gap alone cannot identify a cause. Original val was used for probe selection/calibration.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=['prepare', 'run', 'verify'], default='prepare')
    parser.add_argument('--run_dir', type=Path, default=DEFAULT)
    parser.add_argument('--model', default=os.environ.get('KBA_MODEL'))
    parser.add_argument('--smoke', action='store_true')
    parser.add_argument('--prepared_only', action='store_true', help='With verify, check unstarted artifacts only')
    args = parser.parse_args()
    if not args.model:
        parser.error('Use supplied shell entry or --model')
    args.model = str(Path(args.model).resolve())
    args.run_dir = e.resolve(args.run_dir)
    require(args.run_dir.is_relative_to(ROOT / 'runs') and not any(
        args.run_dir.is_relative_to(old) for old in [p.DEFAULT, p.SMOKE, p.PROBE_SOURCE]), 'Use a new diagnostic directory')
    require(not args.smoke or args.run_dir != DEFAULT, 'Smoke needs a separate directory')
    require(not args.prepared_only or args.stage == 'verify', 'prepared_only requires verify')
    with nullcontext() if args.stage == 'verify' else e.legacy.run_lock(args.run_dir):
        spec, rows, probe, tokenizer, protocol = prepare(args, write=args.stage != 'verify')
        endpoint_report = endpoints(args, rows, probe, tokenizer, args.stage != 'verify')
        if args.stage != 'verify':
            m.write_new(args.run_dir / 'reports/cached_endpoints.json', m.json_text(endpoint_report))
        else:
            require(e.read_json(args.run_dir / 'reports/cached_endpoints.json') == endpoint_report, 'Endpoint report differs')
        if args.stage == 'prepare' or args.prepared_only:
            require(not (args.run_dir / 'states.json').exists(), 'Outputs exist; use verify instead')
            require(e.read_json(args.run_dir / 'progress.json') == dict(status='prepared_not_started', saved=0, target=len(rows)), 'Prepared progress differs')
            print(m.json_text(dict(status='prepared_verified_not_started' if args.prepared_only else 'prepared_not_started',
                                   cells=len(rows), new_gpu_forwards=0, cached_endpoints=endpoint_report['endpoint_count'])))
            return
        records = run(args, spec, rows, probe, tokenizer, protocol) if args.stage == 'run' else cache(args, rows, probe, tokenizer)
        result = report(rows, records)
        gate = smoke_gate(args, spec, rows, records, probe, tokenizer) if args.smoke else None
        if args.stage == 'run':
            m.write_new(args.run_dir / 'reports/diagnostic.json', m.json_text(result))
            if gate:
                m.write_new(args.run_dir / 'smoke_gate.json', m.json_text(gate))
            e.repro.write_json(args.run_dir / 'progress.json', dict(status=result['status'], saved=len(records), target=len(rows)))
        else:
            require(e.read_json(args.run_dir / 'reports/diagnostic.json') == result, 'Report replay differs')
            require(e.read_json(args.run_dir / 'progress.json') == dict(status=result['status'], saved=len(records), target=len(rows)), 'Progress differs')
            if gate:
                require(e.read_json(args.run_dir / 'smoke_gate.json') == gate, 'Gate replay differs')
            else:
                require_smoke(args, protocol)
        print(m.json_text(dict(status='verified_complete' if args.stage == 'verify' else result['status'], cells=len(rows),
                               new_forwards=result['new_forwards'], reused_endpoints=result['reused_endpoints'], generated_answers=0)))


if __name__ == '__main__':
    main()
