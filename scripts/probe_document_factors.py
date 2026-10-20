"""Fixed-question/fact target, background and ordering factorial diagnostic."""

import argparse
from collections import Counter
from contextlib import nullcontext
from datetime import datetime, timezone
import itertools
import json
import math
import os
from pathlib import Path
import time

import numpy as np

import probe_input_shift as d

ROOT, e, m, p = d.ROOT, d.e, d.m, d.p
SPEC = ROOT / 'prompts/probe_document_factors_v1.json'
DEFAULT = ROOT / 'runs/qwen2.5-3b-probe-document-factors-v1'
SMOKE = ROOT / 'runs/qwen2.5-3b-probe-document-factors-smoke-v1'
require = d.require


def build():
    spec = e.read_json(SPEC)
    previous_spec, previous_rows, _, provenance = m.build()
    source = {r['id']: r for r in map(json.loads, m.SOURCE.read_text().splitlines())}
    endpoints = {r['original_id']: r for r in e.read_json(d.DEFAULT / 'states.json')['records']
                 if r['question_level'] == 'A' and r['document_level'] == 'P'}
    pilot = {r['original_id']: r for r in previous_rows if r['condition'] == 'S'}
    slots = {r['original_id']: r['target_slots'] for r in provenance}
    require(spec['target_levels'] == ['F', 'C'] and spec['background_levels'] == ['S', 'L'] and
            spec['rotation_levels'] == [0, 1], 'Factor levels changed')
    rows, edits, background_review = [], [], []
    for number, unit in enumerate(previous_spec['units'], 1):
        oid = unit['base_id']; original = source[oid + '_refuse']
        targets = [unit['target_a'], unit['target_b']]
        require(len(spec['target_tail_deletions'][oid]) == 2, 'Two target-tail entries required')
        compact = []
        for target_index, (text, tail) in enumerate(zip(targets, spec['target_tail_deletions'][oid])):
            require(tail is None or tail and text.endswith(tail), 'Tail must be an exact suffix')
            shortened = text if tail is None else text[:-len(tail)]
            require(unit['remove'] in shortened and text.startswith(shortened), 'Answer/scope prefix must survive')
            compact.append(shortened)
            if tail is not None:
                edits.append(dict(original_id=oid, target_index=target_index, source_target_slot=slots[oid][target_index],
                                  start=len(shortened), end=len(text), before=tail, after='',
                                  retained_fact_quote=unit['remove'], fact_start=shortened.index(unit['remove']),
                                  reviewer='same_exposed_assistant', reason='Delete only reviewed trailing background, retain exact answer-bearing and scope prefix.'))
        order = sorted(range(5), key=lambda i: (len(original['docs'][i]), i))
        selections = {'S': sorted(order[:3]), 'L': sorted(order[-3:])}
        new_slots = sorted(set(selections['L']) - set(selections['S']))
        manual = spec['new_background_review'][oid]
        require(manual['source_slots'] == [i + 1 for i in new_slots], 'Background review slots differ')
        for i in new_slots:
            background_review.append(dict(original_id=oid, source_id=original['id'], source_slot=i + 1,
                                          text_sha256=e.text_hash(original['docs'][i]),
                                          reviewer='same_exposed_assistant', independent_gold=False,
                                          judgment='No contradiction of fixed question/answer facts found in full-text reading; may contain lexical/topic overlap.',
                                          reason=manual['reason']))
        for t, b, rotation in itertools.product(spec['target_levels'], spec['background_levels'], spec['rotation_levels']):
            pair = targets if t == 'F' else compact
            backgrounds = iter(original['docs'][i] for i in selections[b])
            native = [pair[slots[oid].index(i + 1)] if i + 1 in slots[oid] else next(backgrounds) for i in range(5)]
            if (t, b, rotation) == ('F', 'S', 0):
                require(native == pilot[oid]['docs'] and unit['question'] == pilot[oid]['question'], 'Baseline changed')
            docs = native[rotation:] + native[:rotation]
            require(Counter(docs) == Counter(native), 'Rotation lost a document/duplicate')
            source_state = dict(base=str(d.DEFAULT.relative_to(ROOT)), record=endpoints[oid]) if (t, b, rotation) == ('F', 'S', 0) else None
            rows.append(dict(id=f'factor{number:02d}_t{t}_b{b}_r{rotation}', original_id=oid,
                             question_level='A', document_level=f'{t}{b}{rotation}',
                             target_level=t, background_level=b, rotation=rotation,
                             question=unit['question'], docs=docs, source=source_state,
                             background_source_id=original['id'], background_source_slots=[i + 1 for i in selections[b]],
                             native_target_slots=slots[oid],
                             rotated_target_slots=[(i - 1 - rotation) % 5 + 1 for i in slots[oid]]))
    require(len(rows) == 80 and sum(r['source'] is not None for r in rows) == 10, 'Expected80/10')
    require(len(edits) == 19 and len(background_review) == 20, 'Expected19 tail edits /20 new source slots')
    require(set(spec['smoke_bases']) <= {r['original_id'] for r in rows} and len(spec['smoke_bases']) == 2, 'Two fixed smoke bases required')
    return spec, rows, edits, background_review


def prepare(args, write=True):
    spec, all_rows, edits, background = build()
    rows = [r for r in all_rows if r['original_id'] in spec['smoke_bases']] if args.smoke else all_rows
    probe, _, old = p.probe_resources(args.model)
    previous = e.read_json(d.DEFAULT / 'protocol.json')
    for name, expected in {**previous['implementation_sha256'], **previous['source_sha256']}.items():
        require(m.digest(ROOT / name) == expected, f'Previous frozen source differs: {name}')
    require(previous['model'] == args.model, 'Source model differs')
    signature = e.repro.feature_spec(argparse.Namespace(model=args.model, template='P0'), [dict(r, label=-1) for r in all_rows], m.SOURCE)
    for key in ['model', 'model_files', 'weights', 'template_sha256', 'renderer_sha256', 'render_policy']:
        require(signature[key] == old['reference_specs']['val'][key], f'Backbone differs: {key}')
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(args.model, local_files_only=True)
    for row in all_rows:
        if row['source']:
            d.source_state(row, tokenizer, args.model)
    implementations = set(previous['implementation_sha256']) | {
        'scripts/probe_document_factors.py', 'scripts/run_probe_document_factors.sh',
        'scripts/run_probe_document_factors_review.sh', 'prompts/probe_document_factors_v1.json'}
    sources = dict(previous['source_sha256'])
    for path in [d.DEFAULT / 'protocol.json', d.DEFAULT / 'states.json', d.DEFAULT / 'materials/inputs.json']:
        sources[str(path.relative_to(ROOT))] = m.digest(path)
    lengths = {r['id']: len(e.encode(tokenizer, d.prompt(r, tokenizer), 'chat')['input_ids']) for r in all_rows}
    context = e.read_json(Path(args.model) / 'config.json')['max_position_embeddings']
    require(max(lengths.values()) <= context, 'Context overflow; no truncation')
    all_history = [r for r in e.read_json(d.DEFAULT / 'states.json')['records'] if r['origin'] == 'new_forward']
    require(len(all_history) == 32, 'Expected completed previous32 new forwards')
    # First new row includes model loading. Use other31 for throughput and add load allowance separately.
    actual_history = all_history[1:]
    historical_ratio = max(r['elapsed_seconds'] / r['input_tokens'] for r in actual_history)
    planned_tokens = sum(lengths[r['id']] for r in all_rows if r['source'] is None) + sum(
        lengths[r['id']] for r in all_rows if r['original_id'] in spec['smoke_bases'])
    capacity = historical_ratio * planned_tokens
    preflight = dict(status='cpu_preflight_passed', cells=len(rows), input_tokens={r['id']: lengths[r['id']] for r in rows},
                     max_input_tokens=max(lengths[r['id']] for r in rows), context_tokens=context,
                     expected_new_forwards=len(rows) if args.smoke else 70, reused_endpoints=0 if args.smoke else 10,
                     whole_smoke_plus_full_forward_count=86, planned_new_input_tokens=planned_tokens,
                     historical_max_elapsed_per_token=historical_ratio,
                     timing_history_rows=31, model_load_row_excluded=True,
                     planned_whole_minutes=[math.ceil(3 + 2 * capacity / 60), math.ceil(8 + 10 * capacity / 60)],
                     timing_note='Capacity from previous31 forwards after excluding first new row containing model load; max elapsed/token ratio with2x/10x allowance +3/8min load/IO. Attention is nonlinear; no new GPU timing guarantee. User launches.')
    runtime = {k: e.version(k) for k in previous['runtime_versions']}
    require(runtime == previous['runtime_versions'], 'Runtime versions differ from source extraction')
    protocol = dict(schema_version=1, task='fixed_question_fact_document_factors', model=args.model, smoke=args.smoke,
                    specification=spec, backbone_signature=signature,
                    implementation_sha256={name: m.digest(ROOT / name) for name in sorted(implementations)},
                    source_sha256=sources, selected_ids=[r['id'] for r in rows],
                    inputs_sha256=e.text_hash(m.json_text(rows)), edits_sha256=e.text_hash(m.json_text(edits)),
                    background_review_sha256=e.text_hash(m.json_text(background)),
                    runtime_versions=runtime, feature_convention=e.FEATURE_CONVENTION,
                    forward=previous['forward'], frozen_probe_layer=28,
                    no_training='No fit/calibration/layer/threshold selection or probe feedback.',
                    no_generation='No LM head, generated answers or new behavior scoring.',
                    no_gold='Author-supported facts fixed; no independent gold or new accuracy metric.',
                    analysis='12 prespecified paired one-factor contrasts, 10 bases each; not120 independent questions.',
                    no_test='Only the same exposed validation bases, no original test/confirmation inputs.',
                    bridge='16 smoke cells over two fixed bases; both reused-baseline states recomputed before full.')
    review_seal = dict(inputs_sha256=protocol['inputs_sha256'], edits_sha256=protocol['edits_sha256'],
                       background_review_sha256=protocol['background_review_sha256'],
                       reviewer='same_exposed_assistant', independent_gold=False,
                       reviewed_new_target_tail_deletions=19, reviewed_additional_background_slots=20,
                       scope='Reviewed explicit changed target prefixes/tails and full additional background texts; unchanged inputs reuse previous exposed materials. Not independent semantic certification of all80 rows.')
    artifacts = {'protocol.json': protocol, 'preflight.json': preflight, 'materials/inputs.json': rows,
                 'materials/target_edits.json': edits, 'materials/background_review.json': background,
                 'materials/review_seal.json': review_seal}
    for name, value in artifacts.items():
        text = m.json_text(value)
        if write:
            m.write_new(args.run_dir / name, text)
        else:
            require((args.run_dir / name).read_bytes() == text.encode(), f'Frozen artifact differs: {name}')
    if write and not (args.run_dir / 'progress.json').exists():
        e.repro.write_json(args.run_dir / 'progress.json', dict(status='prepared_not_started', saved=0, target=len(rows)))
    return spec, rows, probe, tokenizer, protocol


def cache(args, rows, probe, tokenizer):
    records = d.cache(args, rows, probe, tokenizer)
    for row, record in zip(rows, records):
        require(all(record[k] == row[k] for k in ['target_level', 'background_level', 'rotation']), 'Factor metadata differs')
    return records


def gate(args, spec, rows, records, probe, tokenizer):
    require(len(rows) == len(records) == 16 and all(r['origin'] == 'new_forward' for r in records), 'Smoke16 incomplete')
    bridges = []
    for row, record in zip(rows, records):
        if row['source']:
            error = d.bridge_error(np.load(args.run_dir / record['feature_file'], allow_pickle=False), d.source_state(row, tokenizer, args.model), probe)
            require(all(error[k] <= limit for k, limit in spec['bridge_tolerances'].items()), f'Baseline bridge failed: {row["id"]}: {error}')
            bridges.append(dict(id=row['id'], **error))
    require(len(bridges) == 2, 'Two smoke bridges required')
    return dict(status='technical_smoke_passed', cells=16, bridges=bridges, semantic_accuracy_gate=False)


def require_smoke(args, protocol):
    other = argparse.Namespace(run_dir=SMOKE, model=args.model, smoke=True)
    spec, rows, probe, tokenizer, reference = prepare(other, write=False)
    require(reference['implementation_sha256'] == protocol['implementation_sha256'] and
            reference['source_sha256'] == protocol['source_sha256'], 'Smoke setup differs')
    require(gate(other, spec, rows, cache(other, rows, probe, tokenizer), probe, tokenizer) == e.read_json(SMOKE / 'smoke_gate.json'), 'Gate replay differs')


def run(args, spec, rows, probe, tokenizer, protocol):
    if not args.smoke:
        require_smoke(args, protocol)
    records = cache(args, rows, probe, tokenizer)
    model = None
    try:
        for row in rows[len(records):]:
            is_new = args.smoke or row['source'] is None
            started = time.monotonic()
            if is_new:
                import torch
                if model is None:
                    p.s.assert_gpu_idle()
                    model = e.load_model(args.model)
                inputs = e.encode(tokenizer, d.prompt(row, tokenizer), 'chat', return_tensors='pt').to(model.device)
                torch.cuda.synchronize()
                with e.LastPromptCapture(model) as capture, torch.inference_mode():
                    model.model(**inputs, use_cache=False, output_hidden_states=False)
                states = capture.array()
                torch.cuda.synchronize(); del inputs
            else:
                states = d.source_state(row, tokenizer, args.model)
            d.validate_states(states, p.free.feature_shape(args.model))
            relative = f'features/{len(records):04d}.npy'; e.save_array(args.run_dir / relative, states)
            record = {k: row[k] for k in ['id', 'original_id', 'question_level', 'document_level', 'target_level', 'background_level', 'rotation']}
            record.update(origin='new_forward' if is_new else 'reused_endpoint', capture_phase='decoder_prefill_without_generation',
                          prompt_sha256=e.text_hash(d.prompt(row, tokenizer)),
                          input_tokens=len(e.encode(tokenizer, d.prompt(row, tokenizer), 'chat')['input_ids']),
                          feature_file=relative, feature_sha256=m.digest(args.run_dir / relative),
                          elapsed_seconds=time.monotonic() - started, completed_at=datetime.now(timezone.utc).isoformat(),
                          **d.prediction(probe, states))
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


def summarize(rows, records):
    require(len(rows) == len(records), 'Extraction incomplete')
    groups = {}
    for row, record in zip(rows, records):
        require(row['id'] == record['id'], 'Report order differs')
        groups.setdefault(row['original_id'], {})[(row['target_level'], row['background_level'], row['rotation'])] = record
    pairs = []
    for oid, group in groups.items():
        require(len(group) == 8, 'Each base needs all8 cells')
        for right, a in group.items():
            for axis, changed in enumerate(['C', 'L', 1]):
                if right[axis] == changed:
                    continue
                left = tuple(changed if i == axis else right[i] for i in range(3)); b = group[left]
                fixed = ''.join(str(right[i]) for i in range(3) if i != axis)
                name = ['compact_minus_full', 'long_minus_short_background', 'rotate1_minus_native'][axis] + '_fixed_' + fixed
                pairs.append(dict(original_id=oid, contrast=name, left_id=b['id'], right_id=a['id'],
                                  left_pred=b['probe_pred'], right_pred=a['probe_pred'],
                                  token_delta=b['input_tokens'] - a['input_tokens'],
                                  probability_delta={k: b['probe_probabilities'][k] - a['probe_probabilities'][k] for k in e.MODES}))
    contrasts = {}
    for name in dict.fromkeys(p['contrast'] for p in pairs):
        selected = [x for x in pairs if x['contrast'] == name]
        contrasts[name] = dict(n_pairs=len(selected), changed_labels=sum(x['left_pred'] != x['right_pred'] for x in selected),
                               mean_probability_delta={k: sum(x['probability_delta'][k] for x in selected) / len(selected) for k in e.MODES})
    by_cell = {}
    for row, record in zip(rows, records):
        by_cell.setdefault(row['document_level'], []).append(record['probe_pred'])
    return dict(status='document_factor_diagnostic_complete', cells=len(records), bases=len(groups),
                by_cell={k: dict(n=len(v), predictions=dict(Counter(v))) for k, v in by_cell.items()},
                contrasts=contrasts, paired=pairs, new_forwards=sum(r['origin'] == 'new_forward' for r in records),
                reused_endpoints=sum(r['origin'] == 'reused_endpoint' for r in records), generated_answers=0, trained_probes=0,
                limitation='Same exposed ten bases; fixed authored question/answer facts, no independent gold. Target tail deletion changes length, background changes content/length/duplicates, rotation changes absolute slots and order. No new semantic accuracy, behavior, population or hidden-state causal claim.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=['prepare', 'run', 'verify'], default='prepare')
    parser.add_argument('--run_dir', type=Path, default=DEFAULT)
    parser.add_argument('--smoke', action='store_true')
    parser.add_argument('--prepared_only', action='store_true')
    parser.add_argument('--model', default=os.environ.get('KBA_MODEL'))
    args = parser.parse_args()
    if not args.model:
        parser.error('Use supplied shell entry or --model')
    args.model = str(Path(args.model).resolve()); args.run_dir = e.resolve(args.run_dir)
    require(args.run_dir.is_relative_to(ROOT / 'runs') and not any(args.run_dir.is_relative_to(x)
        for x in [p.DEFAULT, p.SMOKE, p.PROBE_SOURCE, d.DEFAULT, d.SMOKE]), 'Use a new factor diagnostic directory')
    require(not args.smoke or args.run_dir != DEFAULT, 'Smoke needs a separate directory')
    require(not args.prepared_only or args.stage == 'verify', 'prepared_only requires verify')
    with nullcontext() if args.stage == 'verify' else e.legacy.run_lock(args.run_dir):
        spec, rows, probe, tokenizer, protocol = prepare(args, write=args.stage != 'verify')
        if args.stage == 'prepare' or args.prepared_only:
            require(not (args.run_dir / 'states.json').exists() and e.read_json(args.run_dir / 'progress.json') ==
                    dict(status='prepared_not_started', saved=0, target=len(rows)), 'Not an unstarted preparation')
            print(m.json_text(dict(status='prepared_verified_not_started' if args.prepared_only else 'prepared_not_started',
                                  cells=len(rows), new_gpu_forwards=0)))
            return
        records = run(args, spec, rows, probe, tokenizer, protocol) if args.stage == 'run' else cache(args, rows, probe, tokenizer)
        result = summarize(rows, records)
        smoke = gate(args, spec, rows, records, probe, tokenizer) if args.smoke else None
        progress = dict(status=result['status'], saved=len(records), target=len(rows))
        if args.stage == 'run':
            m.write_new(args.run_dir / 'reports/diagnostic.json', m.json_text(result))
            if smoke:
                m.write_new(args.run_dir / 'smoke_gate.json', m.json_text(smoke))
            e.repro.write_json(args.run_dir / 'progress.json', progress)
        else:
            require(e.read_json(args.run_dir / 'reports/diagnostic.json') == result and e.read_json(args.run_dir / 'progress.json') == progress, 'Report/progress differs')
            if smoke:
                require(e.read_json(args.run_dir / 'smoke_gate.json') == smoke, 'Gate differs')
            else:
                require_smoke(args, protocol)
        print(m.json_text(dict(status='verified_complete' if args.stage == 'verify' else result['status'], cells=len(rows),
                              new_forwards=result['new_forwards'], reused_endpoints=result['reused_endpoints'], generated_answers=0)))


if __name__ == '__main__':
    main()
