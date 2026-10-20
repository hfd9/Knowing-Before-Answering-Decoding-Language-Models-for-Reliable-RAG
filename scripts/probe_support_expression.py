"""Frozen-probe support wording, redundant negatives and consistent answer-value controls."""

import argparse
from collections import Counter
from contextlib import nullcontext
from datetime import datetime, timezone
import math
import os
from pathlib import Path
import re
import time

import numpy as np

import probe_document_factors as f

ROOT, d, e, m, p = f.ROOT, f.d, f.e, f.m, f.p
require = f.require
SPEC = ROOT / 'prompts/probe_support_expression_v1.json'
TRAIN = ROOT / 'runs/qwen2.5-3b-small/data/instances_train.jsonl'
DEFAULT = ROOT / 'runs/qwen2.5-3b-probe-support-expression-v1'
SMOKE = ROOT / 'runs/qwen2.5-3b-probe-support-expression-smoke-v1'
AXES = ['wording_level', 'value_level', 'negative_level']


def build():
    spec = e.read_json(SPEC)
    old_rows = {r['original_id']: r for r in f.build()[1] if r['document_level'] == 'CS0'}
    source = {r['original_id']: r for r in e.read_json(f.DEFAULT / 'states.json')['records'] if r['document_level'] == 'CS0'}
    require(spec['base_order'] == list(old_rows) == [u['base_id'] for u in spec['units']], 'Base order differs')
    require(spec['negative_bases'] == [u['base_id'] for u in spec['units'] if u['redundant_negative']] and len(spec['negative_bases']) == 6, 'Negative subset differs')
    require(spec['value_bases'] == ['val_81', 'val_35', 'val_31', 'val_86'], 'Person/date subset fixed before extraction')
    rows, reviews, edits = [], [], []
    for number, unit in enumerate(spec['units'], 1):
        oid = unit['base_id']; old = old_rows[oid]; slots = old['native_target_slots']
        require(unit['review_reason'] and unit['reviewer'] == 'same_exposed_assistant' and unit['independent_gold'] is False, 'Explicit exposed review required')
        require(bool(unit['alternate_value']) == (oid in spec['value_bases']), 'Value subset differs')
        require(set(unit['templates']) == {'D', 'P'}, 'Two wording levels required')
        for cell, (wording, value_level, negative_level) in spec['cell_definitions'].items():
            if value_level == 'alternate' and not unit['alternate_value']:
                continue
            if negative_level == 'negative' and not unit['redundant_negative']:
                continue
            docs = list(old['docs']); cached = None
            if cell == 'B':
                cached = dict(base=str(f.DEFAULT.relative_to(ROOT)), record=source[oid])
            else:
                value = unit['authored_value'] if value_level == 'authored' else unit['alternate_value']
                require(len(unit['templates'][wording]) == 2, 'Two target templates required')
                for slot, template in zip(slots, unit['templates'][wording]):
                    require('{value}' in template, 'Template must explicitly carry value')
                    positive = template.format(value=value)
                    text = positive + (' ' + unit['redundant_negative'] if negative_level == 'negative' else '')
                    require(value in positive and '{' not in text and '}' not in text, 'Unrendered target/value')
                    before = docs[slot - 1]; docs[slot - 1] = text
                    edits.append(dict(id=f'support{number:02d}_{cell}', original_id=oid, doc_slot=slot,
                                      start=0, end=len(before), before=before, after=text,
                                      positive_quote=positive, quote_start=0, quote_end=len(positive),
                                      negative_suffix=unit['redundant_negative'] if negative_level == 'negative' else None,
                                      value=value, reviewer=unit['reviewer'], independent_gold=False,
                                      reason=unit['review_reason']))
                require([i + 1 for i, (a, b) in enumerate(zip(old['docs'], docs)) if a != b] == sorted(slots), 'Only both target slots may change')
            row = dict(id=f'support{number:02d}_{cell}', original_id=oid, cell=cell,
                       question_level='A', document_level=cell, wording_level=wording,
                       value_level=value_level, negative_level=negative_level,
                       question=old['question'], docs=docs, native_target_slots=slots, source=cached)
            rows.append(row)
        reviews.append(dict(original_id=oid, reviewer=unit['reviewer'], independent_gold=False,
                            question_sha256=e.text_hash(old['question']), target_slots=slots,
                            unchanged_background_sha256=[e.text_hash(text) for i, text in enumerate(old['docs'], 1) if i not in slots],
                            required_fact_review=unit['review_reason'], alternate_reason=unit['alternate_reason'],
                            authored_value=unit['authored_value'], alternate_value=unit['alternate_value'],
                            supports_scope='Same authored question-answer relation within D/P; value-switch changes both targets consistently. No independent semantic certification or real-world truth claim.'))
    require(len(rows) == 50 and sum(r['source'] is not None for r in rows) == 10 and len(edits) == 80, 'Expected50/10/80')
    require(spec['smoke_bases'] == ['val_31', 'val_35'], 'Smoke scope fixed before new states')
    return spec, rows, edits, reviews


def train_lexical_summary(spec):
    """Descriptive exact term-presence counts only; no semantic scoring or parameter selection."""
    import json
    rows = list(map(json.loads, TRAIN.read_text().splitlines()))
    require(len(rows) == 600 and len({r['original_id'] for r in rows}) == 200, 'Expected fixed train600/200')
    require(all(r['split'] == 'train' and len(r['docs']) == 5 for r in rows), 'Train only, five full documents')
    terms = list(dict.fromkeys([v for u in spec['units'] for v in [u['authored_value'], u['alternate_value']] if v] +
                              ['not', 'no', 'sole', 'only', 'unique', 'single', 'exclusively']))
    counts = {}
    for term in terms:
        pattern = re.compile(r'(?<!\w)' + re.escape(term) + r'(?!\w)', re.IGNORECASE)
        by_mode = {}
        for mode in e.MODES:
            selected = [r for r in rows if r['true_mode'] == mode]
            require(len(selected) == 200, 'Expected200 published configurations per mode')
            by_mode[mode] = dict(rows=len(selected), question_rows=sum(bool(pattern.search(r['question'])) for r in selected),
                                 document_rows=sum(any(pattern.search(t) for t in r['docs']) for r in selected),
                                 document_slots=sum(bool(pattern.search(t)) for r in selected for t in r['docs']))
        counts[term] = by_mode
    return dict(status='train_only_descriptive_lexical_counts', instances=600, base_questions=200,
                source_sha256=m.digest(TRAIN), term_counts=counts,
                limitation='Case-insensitive boundary-matched literal presence in questions/documents, counted by published construction category. Does not establish proposition support, real-world truth, memorization, semantic distance, OOD detection or cause. No target/threshold selection from these counts.')


def prepare(args, write=True):
    spec, all_rows, edits, reviews = build()
    rows = [r for r in all_rows if r['original_id'] in spec['smoke_bases']] if args.smoke else all_rows
    previous = e.read_json(f.DEFAULT / 'protocol.json')
    for name, digest in {**previous['implementation_sha256'], **previous['source_sha256']}.items():
        require(m.digest(ROOT / name) == digest, f'Frozen dependency differs: {name}')
    require(args.model == previous['model'], 'Model path differs')
    probe, _, old = p.probe_resources(args.model)
    signature = e.repro.feature_spec(argparse.Namespace(model=args.model, template='P0'), [dict(r, label=-1) for r in all_rows], m.SOURCE)
    for key in ['model', 'model_files', 'weights', 'template_sha256', 'renderer_sha256', 'render_policy']:
        require(signature[key] == old['reference_specs']['val'][key], f'Backbone differs: {key}')
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(args.model, local_files_only=True)
    endpoints = []
    for row in all_rows:
        if row['source']:
            states = d.source_state(row, tokenizer, args.model)
            endpoints.append(dict(id=row['id'], original_id=row['original_id'], **d.prediction(probe, states)))
    lengths = {r['id']: len(e.encode(tokenizer, d.prompt(r, tokenizer), 'chat')['input_ids']) for r in all_rows}
    context = e.read_json(Path(args.model) / 'config.json')['max_position_embeddings']
    require(max(lengths.values()) <= context, 'Context overflow; no truncation')
    files = set(previous['implementation_sha256']) | {'scripts/probe_support_expression.py',
        'scripts/run_probe_support_expression.sh', 'scripts/run_probe_support_expression_review.sh',
        'prompts/probe_support_expression_v1.json'}
    sources = dict(previous['source_sha256'])
    for path in [f.DEFAULT / 'protocol.json', f.DEFAULT / 'states.json', f.DEFAULT / 'materials/inputs.json', TRAIN]:
        sources[str(path.relative_to(ROOT))] = m.digest(path)
    runtime = {k: e.version(k) for k in previous['runtime_versions']}
    require(runtime == previous['runtime_versions'], 'Runtime versions differ')
    protocol = dict(schema_version=1, task='support_expression_value_development', model=args.model, smoke=args.smoke,
                    specification=spec, backbone_signature=signature, runtime_versions=runtime,
                    implementation_sha256={name: m.digest(ROOT / name) for name in sorted(files)}, source_sha256=sources,
                    selected_ids=[r['id'] for r in rows], inputs_sha256=e.text_hash(m.json_text(rows)),
                    edits_sha256=e.text_hash(m.json_text(edits)), reviews_sha256=e.text_hash(m.json_text(reviews)),
                    feature_convention=e.FEATURE_CONVENTION, frozen_probe_layer=28, forward=previous['forward'],
                    no_training='No fitting, calibration, layer/threshold selection or feedback.',
                    no_generation='No LM head, generated answers or new behavior scoring.',
                    no_gold='Same exposed assistant, no independent semantic gold, new accuracy or population claim.',
                    no_test='Same exposed ten val bases plus descriptive fixed train600 counts, no original test/confirmation.')
    history = [r for r in e.read_json(f.DEFAULT / 'states.json')['records'] if r['origin'] == 'new_forward'][1:]
    require(len(history) == 69, 'Expected69 previous timings excluding model-load row')
    ratio = max(r['elapsed_seconds'] / r['input_tokens'] for r in history)
    tokens = sum(lengths[r['id']] for r in all_rows if not r['source']) + sum(lengths[r['id']] for r in all_rows if r['original_id'] in spec['smoke_bases'])
    capacity = tokens * ratio
    preflight = dict(status='cpu_preflight_passed', cells=len(rows), input_tokens={r['id']: lengths[r['id']] for r in rows},
                     max_input_tokens=max(lengths[r['id']] for r in rows), context_tokens=context,
                     expected_new_forwards=12 if args.smoke else 40, reused_endpoints=0 if args.smoke else 10,
                     whole_smoke_plus_full_new_forwards=52, planned_new_input_tokens=tokens,
                     historical_rows=69, historical_max_seconds_per_token=ratio,
                     planned_whole_minutes=[math.ceil(3 + 2 * capacity / 60), math.ceil(8 + 10 * capacity / 60)],
                     timing_note='Previous69 document-factor forwards excluding first model-load row; max elapsed/token with2x/10x and3/8min load/IO allowance. Attention nonlinear, not a new GPU measurement; user launches if not guaranteed under10min.')
    seal = dict(reviewer='same_exposed_assistant', independent_gold=False, reviewed_new_targets=80,
                inputs_sha256=protocol['inputs_sha256'], edits_sha256=protocol['edits_sha256'], reviews_sha256=protocol['reviews_sha256'],
                scope='All80 new target texts and answer/scope arguments reviewed; three fixed complete background documents and baseline targets reuse inspected prior materials. Not independent gold.')
    artifacts = {'protocol.json':protocol, 'preflight.json':preflight, 'materials/inputs.json':rows,
                 'materials/target_edits.json':edits, 'materials/semantic_review.json':reviews,
                 'materials/review_seal.json':seal, 'reports/cached_endpoints.json':dict(new_gpu_forwards=0, endpoints=endpoints),
                 'reports/train_lexical_counts.json':train_lexical_summary(spec)}
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
        require(all(record[k] == row[k] for k in ['cell', *AXES]), 'Support metadata differs')
    return records


def gate(args, spec, rows, records, probe, tokenizer):
    require(len(rows) == len(records) == 12 and all(r['origin'] == 'new_forward' for r in records), 'Smoke12 incomplete')
    bridges = []
    for row, record in zip(rows, records):
        if row['source']:
            error = d.bridge_error(np.load(args.run_dir / record['feature_file'], allow_pickle=False), d.source_state(row, tokenizer, args.model), probe)
            require(all(error[k] <= limit for k, limit in spec['bridge_tolerances'].items()), f'Baseline bridge failed: {row["id"]}: {error}')
            bridges.append(dict(id=row['id'], **error))
    require(len(bridges) == 2, 'Two bridges required')
    return dict(status='technical_smoke_passed', cells=12, bridges=bridges, semantic_accuracy_gate=False)


def require_smoke(args, protocol):
    other = argparse.Namespace(run_dir=SMOKE, model=args.model, smoke=True)
    spec, rows, probe, tokenizer, reference = prepare(other, write=False)
    require(reference['implementation_sha256'] == protocol['implementation_sha256'] and reference['source_sha256'] == protocol['source_sha256'], 'Smoke setup differs')
    require(gate(other, spec, rows, cache(other, rows, probe, tokenizer), probe, tokenizer) == e.read_json(SMOKE / 'smoke_gate.json'), 'Gate replay differs')


def run(args, spec, rows, probe, tokenizer, protocol):
    if not args.smoke:
        require_smoke(args, protocol)
    records = cache(args, rows, probe, tokenizer); model = None
    try:
        for row in rows[len(records):]:
            is_new = args.smoke or row['source'] is None; started = time.monotonic()
            if is_new:
                import torch
                if model is None:
                    p.s.assert_gpu_idle(); model = e.load_model(args.model)
                inputs = e.encode(tokenizer, d.prompt(row, tokenizer), 'chat', return_tensors='pt').to(model.device)
                torch.cuda.synchronize()
                with e.LastPromptCapture(model) as capture, torch.inference_mode():
                    model.model(**inputs, use_cache=False, output_hidden_states=False)
                states = capture.array(); torch.cuda.synchronize(); del inputs
            else:
                states = d.source_state(row, tokenizer, args.model)
            d.validate_states(states, p.free.feature_shape(args.model))
            relative = f'features/{len(records):04d}.npy'; e.save_array(args.run_dir / relative, states)
            record = {k: row[k] for k in ['id', 'original_id', 'question_level', 'document_level', 'cell', *AXES]}
            record.update(origin='new_forward' if is_new else 'reused_endpoint', capture_phase='decoder_prefill_without_generation',
                          prompt_sha256=e.text_hash(d.prompt(row, tokenizer)), input_tokens=len(e.encode(tokenizer, d.prompt(row, tokenizer), 'chat')['input_ids']),
                          feature_file=relative, feature_sha256=m.digest(args.run_dir / relative), elapsed_seconds=time.monotonic() - started,
                          completed_at=datetime.now(timezone.utc).isoformat(), **d.prediction(probe, states))
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


def summarize(spec, rows, records):
    require(len(rows) == len(records), 'Extraction incomplete')
    groups = {}
    for row, record in zip(rows, records):
        require(row['id'] == record['id'], 'Report order differs')
        group = groups.setdefault(row['original_id'], {})
        require(row['cell'] not in group, 'Duplicate cell'); group[row['cell']] = record
    paired, contrasts = [], {}
    for left, right, name in spec['planned_contrasts']:
        selected = []
        for oid, group in groups.items():
            if left not in group or right not in group:
                continue
            a, b = group[left], group[right]
            selected.append(dict(original_id=oid, contrast=name, left_id=a['id'], right_id=b['id'], left_pred=a['probe_pred'], right_pred=b['probe_pred'],
                                 token_delta=a['input_tokens'] - b['input_tokens'],
                                 probability_delta={k:a['probe_probabilities'][k] - b['probe_probabilities'][k] for k in e.MODES}))
        require(selected, f'No paired support: {name}')
        paired.extend(selected)
        contrasts[name] = dict(n_pairs=len(selected), changed_labels=sum(a['left_pred'] != a['right_pred'] for a in selected),
                               mean_probability_delta={k:sum(a['probability_delta'][k] for a in selected)/len(selected) for k in e.MODES})
    by_cell = {}
    for row, record in zip(rows, records):
        by_cell.setdefault(row['cell'], []).append(record['probe_pred'])
    return dict(status='support_expression_diagnostic_complete', cells=len(records), bases=len(groups),
                by_cell={k:dict(n=len(v), predictions=dict(Counter(v))) for k,v in by_cell.items()}, contrasts=contrasts, paired=paired,
                new_forwards=sum(r['origin']=='new_forward' for r in records), reused_endpoints=sum(r['origin']=='reused_endpoint' for r in records),
                generated_answers=0, trained_probes=0, limitation=spec['limits'], contrast_note=spec['note'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=['prepare','run','verify'], default='prepare')
    parser.add_argument('--run_dir', type=Path, default=DEFAULT)
    parser.add_argument('--model', default=os.environ.get('KBA_MODEL'))
    parser.add_argument('--smoke', action='store_true'); parser.add_argument('--prepared_only', action='store_true')
    args = parser.parse_args()
    if not args.model: parser.error('Use supplied shell entry or --model')
    args.model = str(Path(args.model).resolve()); args.run_dir = e.resolve(args.run_dir)
    require(args.run_dir.is_relative_to(ROOT/'runs') and not any(args.run_dir.is_relative_to(x) for x in
        [p.DEFAULT,p.SMOKE,p.PROBE_SOURCE,d.DEFAULT,d.SMOKE,f.DEFAULT,f.SMOKE]), 'Use a new support diagnostic directory')
    require(not args.smoke or args.run_dir != DEFAULT, 'Smoke needs separate directory')
    require(not args.prepared_only or args.stage == 'verify', 'prepared_only requires verify')
    with nullcontext() if args.stage == 'verify' else e.legacy.run_lock(args.run_dir):
        spec, rows, probe, tokenizer, protocol = prepare(args, write=args.stage!='verify')
        if args.stage == 'prepare' or args.prepared_only:
            require(not (args.run_dir/'states.json').exists() and e.read_json(args.run_dir/'progress.json') ==
                    dict(status='prepared_not_started',saved=0,target=len(rows)), 'Not an unstarted preparation')
            print(m.json_text(dict(status='prepared_verified_not_started' if args.prepared_only else 'prepared_not_started',cells=len(rows),new_gpu_forwards=0))); return
        records = run(args,spec,rows,probe,tokenizer,protocol) if args.stage=='run' else cache(args,rows,probe,tokenizer)
        result = summarize(spec,rows,records); smoke = gate(args,spec,rows,records,probe,tokenizer) if args.smoke else None
        progress = dict(status=result['status'],saved=len(records),target=len(rows))
        if args.stage=='run':
            m.write_new(args.run_dir/'reports/diagnostic.json',m.json_text(result))
            if smoke: m.write_new(args.run_dir/'smoke_gate.json',m.json_text(smoke))
            e.repro.write_json(args.run_dir/'progress.json',progress)
        else:
            require(e.read_json(args.run_dir/'reports/diagnostic.json')==result and e.read_json(args.run_dir/'progress.json')==progress,'Report/progress differs')
            if smoke: require(e.read_json(args.run_dir/'smoke_gate.json')==smoke,'Gate differs')
            else: require_smoke(args,protocol)
        print(m.json_text(dict(status='verified_complete' if args.stage=='verify' else result['status'],cells=len(rows),new_forwards=result['new_forwards'],reused_endpoints=result['reused_endpoints'],generated_answers=0)))


if __name__=='__main__':
    main()
