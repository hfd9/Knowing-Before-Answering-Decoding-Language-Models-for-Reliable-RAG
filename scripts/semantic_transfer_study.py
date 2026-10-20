"""Versioned chat L28 transfer executor. Default is CPU preparation; reviews gate inference."""

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import pickle
import time

import semantic_transfer_review_intake as intake
import semantic_transfer_metrics as metrics

ROOT = intake.ROOT
MATERIALS = ROOT / 'runs/qwen2.5-3b-semantic-transfer-materials-v4-r2'
DEFAULT = ROOT / 'runs/qwen2.5-3b-semantic-transfer-study-preparation-v1'
PROBE = ROOT / 'runs/qwen2.5-3b-free-answer-study'
require, read, serialize = intake.require, intake.read, intake.serialize


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def text_hash(value):
    return hashlib.sha256(value.encode()).hexdigest()


def put(path, value, write=True):
    expected = serialize(value)
    if path.exists():
        require(path.read_text() == expected, f'Frozen artifact differs; use a new version: {path}')
    elif write:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(expected)
        temporary.replace(path)
    else:
        raise ValueError(f'Missing frozen artifact: {path}')


def approval_labels(materials, rows, mapping, packets, design, approval_path):
    """Validate explicit approval plus source reviews and retained context audit receipts.

    Software checks identities, hashes and declarations; the named auditor remains responsible
    for checking actual context completeness/independence. Agreement alone approves nothing.
    """
    labels = {row['id']: None for row in rows}
    evidence = {}
    audited = 0
    if approval_path is not None:
        value = read(approval_path)
        require(value.get('status') == 'explicitly_approved_after_context_audit', 'Explicit audited approval required')
        require(value.get('materials_protocol_sha256') == digest(materials / 'protocol.json'), 'Approval materials mismatch')
        require(isinstance(value.get('approved_by'), str) and value['approved_by'].strip(), 'Named approver required')
        require(value.get('approval_rationale', '').strip(), 'Approval rationale required')
        require(value.get('no_probe_or_generated_outputs_seen') is True, 'Labels must precede inference')
        require(value.get('independence_limit_acknowledged') is True, 'Audit declaration limits must be acknowledged')
        reviews, context_ids, context_hashes = {}, set(), set()
        evidence[str(approval_path.resolve())] = digest(approval_path)
        for side in ['a', 'b']:
            source = value['reviews'][side]
            path = Path(source['path']).resolve()
            require(digest(path) == source['sha256'], 'Source review hash mismatch')
            raw = read(path)
            ratings = intake.validate_review(raw, packets[side], digest(materials / f'review_{side}/packet.json'))
            reviews[side] = dict(metadata=raw, ratings=ratings)
            audit = value['context_audits'][side]
            require(audit.get('reviewer') == raw['reviewer'], 'Context reviewer identity mismatch')
            require(isinstance(audit.get('auditor'), str) and audit['auditor'].strip(), 'Named context auditor required')
            require(audit.get('audit_rationale', '').strip(), 'Actual context audit rationale required')
            require(audit.get('received_packet_sha256') == raw['packet_sha256'], 'Context packet mismatch')
            for field in ['history_exposed', 'author_labels_exposed', 'probe_or_outputs_exposed']:
                require(audit.get(field) is False, f'Contaminated or undeclared context: {field}')
            require(audit.get('complete_received_context_checked') is True, 'Complete context must be audited')
            require(isinstance(audit.get('context_id'), str) and audit['context_id'].strip(), 'Context identity required')
            context = Path(audit['full_context_path']).resolve()
            require(context.is_file() and context.stat().st_size > 0, 'Retained complete context record required')
            require(digest(context) == audit['full_context_sha256'], 'Context record hash mismatch')
            context_ids.add(audit['context_id'])
            context_hashes.add(audit['full_context_sha256'])
            evidence.update({str(path): digest(path), str(context): digest(context)})
        require(len(context_ids) == len(context_hashes) == 2, 'Two distinct auditable contexts required')
        _, candidates = intake.summarize(rows, [], mapping, reviews, design)
        supplied = value['labels']
        require(isinstance(supplied, list) and all(isinstance(r, dict) for r in supplied), 'Explicit label rows required')
        require(len(supplied) == len({r['id'] for r in supplied}) == len(rows), 'Approval must cover each material exactly once')
        require({r['id'] for r in supplied} == set(labels), 'Approval label IDs mismatch')
        by_id = {r['id']: r for r in candidates}
        for row in supplied:
            label = row['semantic_label']
            require(label is None or label in metrics.MODES, 'Unknown semantic labels must be null')
            require(label is None or label == by_id[row['id']]['consensus_candidate'],
                'Label lacks two-review consensus; disagreements stay unknown in this protocol')
            labels[row['id']] = label
        audited = 2
    partitions = {}
    for part, bases in design['partitions'].items():
        n = sum(labels[r['id']] in metrics.MODES for r in rows if r['partition'] == part)
        partitions[part] = dict(planned=len(bases) * 8, approved=n, coverage=n / (len(bases) * 8))
    n = sum(label in metrics.MODES for label in labels.values())
    ready = audited == 2 and n / 240 >= .90 and all(p['coverage'] >= .90 for p in partitions.values())
    return labels, dict(status='review_gate_passed' if ready else 'pending_independent_semantic_reviews',
        planned_cells=240, constructed_cells=len(rows), construction_coverage=len(rows) / 240,
        approved_semantic_labels=n, semantic_coverage=n / 240, partitions=partitions,
        audited_context_receipts=audited, gpu_launch_ready=ready,
        approval_is_explicit_not_automatic=True,
        context_audit_limit='Hashes verify retained records, not the truth or completeness of an external auditor declaration.',
        no_model_weights_loaded=True, no_probe_deserialized=True,
        new_gpu_forwards=0, generated_answers=0, trained_probes=0), evidence


def prepare(materials=MATERIALS, run=DEFAULT, approval=None, write=True):
    import evidence_experiment as e
    from transformers import AutoTokenizer
    rows, unavailable, mapping, packets, design = intake.load_materials(materials)
    require(not unavailable and len(rows) == 240, 'This executor binds the complete v4-r2 material batch')
    material_protocol = read(materials / 'protocol.json')
    require(material_protocol.get('material_version') == 4 and
        material_protocol.get('material_replay_revision') == 2, 'Expected reviewed-material candidate v4-r2')
    for relative, sha in material_protocol['implementation_sha256'].items():
        require(digest(ROOT / relative) == sha, f'Material implementation changed: {relative}')
    for relative, sha in material_protocol['source_sha256'].items():
        require(digest(ROOT / relative) == sha, f'Material source changed: {relative}')
    require(digest(ROOT / 'prompts/semantic_transfer_materials_v4.json') == material_protocol['authored_sha256'],
        'Authored material specification changed')
    require(digest(materials / 'coordinator/source_policy_amendment.json') == material_protocol['source_policy_amendment_sha256']
        and digest(materials / 'sources/supplemental_source_excerpts.json') == material_protocol['supplemental_sources_sha256'],
        'Source snapshot mismatch')
    labels, gate, evidence = approval_labels(materials, rows, mapping, packets, design, approval)
    source_paths = [PROBE / p for p in ['protocol.json', 'chat/probe/probe.json', 'chat/probe/probe.pkl',
        'chat/train/states.json', 'chat/val/states.json']]
    require(digest(PROBE / 'chat/probe/probe.pkl') == design['probe']['old_source_pkl_sha256'], 'Wrong frozen chat L28 probe')
    old = read(PROBE / 'protocol.json')
    require(old['instructions']['free_answer'] == e.FREE_INSTRUCTION and old['feature_convention'] == e.FEATURE_CONVENTION,
        'Frozen instruction/readout definition changed')
    model = Path(old['model'])
    signature = old['reference_specs']['val']
    model_files = {name: digest(model / name) for name in signature['model_files']}
    require(model_files == signature['model_files'], 'Frozen model/tokenizer metadata mismatch')
    weights = {}
    for shard in signature['weights']:
        path = model / shard['file']
        require(path.stat().st_size == shard['size'] and path.stat().st_mtime_ns == shard['mtime_ns'], 'Backbone shard changed')
        weights[shard['file']] = digest(path)
    tokenizer = AutoTokenizer.from_pretrained(str(model), local_files_only=True)
    lengths, prompts = {}, {}
    context = read(model / 'config.json')['max_position_embeddings']
    for row in rows:
        text = e.render_input(row, 'free_answer', 'chat', tokenizer)
        lengths[row['id']] = len(e.encode(tokenizer, text, 'chat')['input_ids'])
        prompts[row['id']] = e.text_hash(text)
        require(lengths[row['id']] + 128 <= context, 'Context overflow; no truncation permitted')
    prior = read(materials / 'preflight.json')
    require(lengths == prior['input_tokens'] and prompts == prior['prompt_sha256'], 'Material preflight interface mismatch')
    sources = [materials / p for p in ['protocol.json', 'preflight.json', 'materials/inputs.json',
        'materials/unavailable_cells.json', 'coordinator/review_mapping.json',
        'review_a/packet.json', 'review_b/packet.json', 'coordinator/source_policy_amendment.json',
        'sources/supplemental_source_excerpts.json']]
    files = ['scripts/semantic_transfer_study.py', 'scripts/semantic_transfer_metrics.py',
        'scripts/run_semantic_transfer_study.sh', 'scripts/semantic_transfer_review_intake.py',
        'scripts/evidence_experiment.py', 'scripts/free_answer_study.py', 'scripts/free_answer_review.py',
        'scripts/small_repro.py', 'scripts/prompt_baseline.py', 'scripts/analyze_prompt_baseline.py',
        'scripts/classification_semantic_baseline.py', 'scripts/classification_prompt_search.py',
        'code/prompts.py', 'prompts/baseline_prompts.json', 'configs/local.env']
    protocol = dict(schema_version=1, task='semantic_transfer_chat_L28_v1',
        materials_dir=str(materials.resolve()), design_sha256=digest(intake.DESIGN),
        implementation_sha256={p: digest(ROOT / p) for p in files},
        sources={str(p.resolve()): digest(p) for p in sources + source_paths}, approval_sources=evidence,
        model=str(model), model_files=model_files, weight_sha256=weights,
        generation_config_sha256=digest(model / 'generation_config.json'),
        versions={n: version(n) for n in ['torch', 'transformers', 'numpy', 'scikit-learn']},
        free_instruction=e.FREE_INSTRUCTION, feature_convention=e.FEATURE_CONVENTION,
        runtime=dict(dtype='bfloat16', attention='sdpa', greedy=True, beams=1, use_cache=True,
            max_new_tokens=128, logits_to_keep=1, probe_feedback=False),
        fixed_layer_zero_based=28, max_training_fits=1, bootstrap_resamples=10000,
        selected_ids=[r['id'] for r in rows], review_gate=gate,
        staged_order=['train_dev_generation', 'dev_only_trigger', 'optional_single_train_A_fit',
            'immutable_evaluation_lock', 'eval_generation', 'separate_old_and_new_reports', 'separate_behavior_review'],
        approval_change_requires_new_run=True, current_preparation_contains_no_inference=True)
    preflight = dict(planned_cells=240, input_tokens=lengths, prompt_sha256=prompts,
        min_input_tokens=min(lengths.values()), max_input_tokens=max(lengths.values()),
        total_input_tokens=sum(lengths.values()), max_output_tokens=240 * 128,
        context_tokens=context, **{k: gate[k] for k in ['gpu_launch_ready', 'approved_semantic_labels', 'semantic_coverage']})
    for name, value in [('protocol.json', protocol), ('review_gate.json', gate),
            ('approved_labels.json', labels), ('preflight.json', preflight)]:
        put(run / name, value, write)
    return rows, labels, gate, protocol, tokenizer


def require_ready(gate):
    require(gate['gpu_launch_ready'] is True, 'Review gate closed: independent audited semantic labels are missing; model/probe loading forbidden')


def predict(probe, states):
    import numpy as np
    vector = states[28][None].astype(np.float32)
    probability = probe['router'].predict_proba(probe['scaler'].transform(vector))[0]
    classes = list(probe['router'].classes_)
    require(classes == [0, 1, 2] and np.isfinite(probability).all(), 'Invalid probe classes/probabilities')
    require(np.all(probability >= 0) and np.isclose(sum(probability), 1), 'Invalid probability simplex')
    return dict(probe_pred=metrics.MODES[int(np.argmax(probability))],
        probe_probabilities=dict(zip(metrics.MODES, map(float, probability))),
        probe_layer_zero_based=28, probe_decision_pre_first_token=True)


def validate_cache(run, rows, tokenizer, old_probe):
    import evidence_experiment as e
    import numpy as np
    path = run / 'predictions.json'
    if not path.exists():
        return []
    value = read(path)
    require(value['protocol_sha256'] == digest(run / 'protocol.json'), 'Cache protocol mismatch')
    records = value['records']
    require(len(records) <= len(rows), 'Cache count overflow')
    eos = read(Path(read(run / 'protocol.json')['model']) / 'generation_config.json')['eos_token_id']
    eos = eos if isinstance(eos, list) else [eos]
    for index, (row, record) in enumerate(zip(rows, records)):
        for key in ['id', 'original_id', 'partition', 'expression', 'condition']:
            require(record[key] == row[key], 'Cache identity/order changed')
        prompt = e.render_input(row, 'free_answer', 'chat', tokenizer)
        require(record['prompt_sha256'] == e.text_hash(prompt), 'Cache prompt mismatch')
        require(record['input_tokens'] == len(e.encode(tokenizer, prompt, 'chat')['input_ids']), 'Cache input length mismatch')
        tokens = record['generated_token_ids']
        require(isinstance(tokens, list) and 0 < len(tokens) <= 128 and all(type(t) is int for t in tokens), 'Invalid cached tokens')
        require(record['generated_tokens'] == len(tokens) and not any(t in eos for t in tokens[:-1]), 'Cached token count/EOS mismatch')
        require(tokenizer.decode(tokens, skip_special_tokens=True) == record['raw_output'], 'Cache decoded text mismatch')
        require(text_hash(record['raw_output']) == record['raw_output_sha256'], 'Cache output hash mismatch')
        require(record['ended_with_eos'] == (tokens[-1] in eos) and record['hit_output_limit'] ==
            (len(tokens) == 128 and tokens[-1] not in eos), 'Cache termination flags mismatch')
        require(record['feature_file'] == f'features/{index:04d}.npy', 'Unexpected feature path')
        feature = run / record['feature_file']
        require(digest(feature) == record['feature_sha256'], 'Feature hash mismatch')
        states = np.load(feature, allow_pickle=False)
        require(states.shape == (36, 2048) and states.dtype == np.float16 and np.isfinite(states).all()
            and not np.any(np.all(states == 0, axis=1)), 'Invalid feature array')
        expected = predict(old_probe, states)
        require(all(record[k] == expected[k] for k in ['probe_pred', 'probe_layer_zero_based', 'probe_decision_pre_first_token']), 'Cache old probe decision mismatch')
        require(set(record['probe_probabilities']) == set(metrics.MODES) and all(np.isclose(
            record['probe_probabilities'][m], expected['probe_probabilities'][m], atol=1e-10, rtol=0)
            for m in metrics.MODES), 'Cache old probe probability mismatch')
    return records


def generate(model, tokenizer, row, probe, eos):
    import evidence_experiment as e
    import torch
    from transformers import GenerationConfig
    prompt = e.render_input(row, 'free_answer', 'chat', tokenizer)
    inputs = e.encode(tokenizer, prompt, 'chat', return_tensors='pt').to(model.device)
    length = inputs.input_ids.shape[1]
    require(length + 128 <= model.config.max_position_embeddings, 'Context overflow')
    config = GenerationConfig(max_new_tokens=128, do_sample=False, num_beams=1, use_cache=True,
        eos_token_id=eos, bos_token_id=model.generation_config.bos_token_id,
        pad_token_id=tokenizer.pad_token_id if tokenizer.pad_token_id is not None else tokenizer.eos_token_id)
    decision = {}
    def callback(states):
        require(not decision, 'Multiple prefill decisions')
        decision.update(predict(probe, states))
    torch.cuda.synchronize()
    started = time.monotonic()
    with e.LastPromptCapture(model, on_prefill=callback) as capture, torch.inference_mode():
        output = model.generate(**inputs, generation_config=config, logits_to_keep=1)
    require(bool(decision), 'No pre-first-token probe decision')
    states = capture.array()
    tokens = output[0, length:].tolist()
    require(bool(tokens), 'No generated tokens')
    raw = tokenizer.decode(tokens, skip_special_tokens=True)
    torch.cuda.synchronize()
    return dict(**{k: row[k] for k in ['id', 'original_id', 'partition', 'expression', 'condition']},
        prompt_sha256=e.text_hash(prompt), input_tokens=length, generated_token_ids=tokens,
        generated_tokens=len(tokens), raw_output=raw, raw_output_sha256=text_hash(raw),
        ended_with_eos=tokens[-1] in eos, hit_output_limit=len(tokens) == 128 and tokens[-1] not in eos,
        elapsed_seconds=time.monotonic() - started, completed_at=datetime.now(timezone.utc).isoformat(), **decision), states


def optional_fit(run, rows, labels, records):
    """Dev decides once; an interrupted or failed fit cannot silently be attempted again."""
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    by_id = {r['id']: r for r in records}
    dev = [r for r in rows if r['partition'] == 'semantic_dev']
    decision = metrics.trigger_on_dev(dev, by_id, labels)
    training = [r for r in rows if r['partition'] == 'semantic_train' and r['expression'] == 'A'
        and labels.get(r['id']) in metrics.MODES]
    decision.update(training_ids=[r['id'] for r in training],
        training_class_counts=dict(Counter(labels[r['id']] for r in training)))
    put(run / 'fit_decision.json', decision)
    metadata = run / 'semantic_probe.json'
    payload = run / 'semantic_probe.pkl'
    if metadata.exists():
        saved = read(metadata)
        require(saved['decision_sha256'] == digest(run / 'fit_decision.json'), 'Fit decision changed')
        if saved['status'] == 'fit_complete':
            require(digest(payload) == saved['pickle_sha256'], 'Semantic probe changed')
            return saved, pickle.loads(payload.read_bytes())
        return saved, None
    status = None
    if not decision['triggered']:
        status = 'not_triggered'
    elif set(decision['training_class_counts']) != set(metrics.MODES):
        status = 'not_fit_missing_training_class'
    if status:
        saved = dict(status=status, training_fits=0, decision_sha256=digest(run / 'fit_decision.json'))
        put(metadata, saved)
        return saved, None
    require(not (run / 'fit_attempt.json').exists(), 'A fit was already attempted; interrupted fits must not be retried')
    put(run / 'fit_attempt.json', dict(decision_sha256=digest(run / 'fit_decision.json'),
        training_ids=[r['id'] for r in training], max_fits=1))
    try:
        features = np.stack([np.load(run / by_id[r['id']]['feature_file'], allow_pickle=False)[28]
            for r in training]).astype(np.float32)
        scaler = StandardScaler().fit(features)
        classifier = LogisticRegression(C=1, class_weight='balanced', solver='lbfgs', max_iter=2000, random_state=42)
        classifier.fit(scaler.transform(features), [metrics.MODES.index(labels[r['id']]) for r in training])
        probe = dict(layer=28, scaler=scaler, router=classifier)
        temporary = payload.with_suffix('.pkl.tmp')
        temporary.write_bytes(pickle.dumps(probe, protocol=pickle.HIGHEST_PROTOCOL))
        temporary.replace(payload)
        saved = dict(status='fit_complete', training_fits=1, pickle_sha256=digest(payload),
            decision_sha256=digest(run / 'fit_decision.json'), n_iter=classifier.n_iter_.tolist(),
            convergence_limit_reached=bool(max(classifier.n_iter_) >= 2000))
    except Exception as error:
        saved = dict(status='fit_failed_no_retry', training_fits=1,
            decision_sha256=digest(run / 'fit_decision.json'), error=repr(error))
        put(metadata, saved)
        return saved, None
    put(metadata, saved)
    return saved, probe


def evaluation_lock(run, metadata, write=True):
    value = dict(protocol_sha256=digest(run / 'protocol.json'),
        labels_sha256=digest(run / 'approved_labels.json'),
        old_probe_sha256=digest(PROBE / 'chat/probe/probe.pkl'),
        decision_sha256=digest(run / 'fit_decision.json'),
        semantic_probe_metadata_sha256=digest(run / 'semantic_probe.json'), semantic_probe=metadata,
        evaluation_not_used_for_selection=True)
    put(run / 'evaluation_lock.json', value, write)
    return value


def execute(run, rows, labels, gate, protocol, tokenizer):
    # Keep the review gate before all probe deserialization, cache/eval access and model loading.
    require_ready(gate)
    import evidence_experiment as e
    import free_answer_study as free
    import classification_semantic_baseline as baseline
    old, _ = free.load_probe(argparse.Namespace(run_dir=PROBE), 'chat', digest(PROBE / 'protocol.json'))
    require(old['layer'] == 28 and old['scaler'].n_features_in_ == 2048, 'Wrong frozen probe interface')
    ordered = [r for r in rows if r['partition'] != 'semantic_eval'] + [r for r in rows if r['partition'] == 'semantic_eval']
    train_dev_n = sum(r['partition'] != 'semantic_eval' for r in rows)
    require(not (run / 'predictions.json').exists() or len(read(run / 'predictions.json')['records']) <= train_dev_n
        or (run / 'evaluation_lock.json').exists(), 'Evaluation cache exists without prior lock')
    # An existing lock must verify before evaluation features/predictions are read.
    if (run / 'evaluation_lock.json').exists():
        evaluation_lock(run, read(run / 'semantic_probe.json'), write=False)
    records = validate_cache(run, ordered, tokenizer, old)
    model = None
    eos = baseline.eos_ids(protocol['model'], tokenizer)
    try:
        for boundary in [train_dev_n, len(ordered)]:
            if boundary == len(ordered):
                metadata, _ = optional_fit(run, rows, labels, records[:train_dev_n])
                evaluation_lock(run, metadata)
            if len(records) >= boundary:
                continue
            if model is None:
                baseline.assert_gpu_idle()
                model = e.load_model(protocol['model'])
            for row in ordered[len(records):boundary]:
                index = len(records)
                # Do not generate a second answer after an ambiguous crash between inference and commit.
                attempt = run / f'generation_attempts/{index:04d}.json'
                require(not attempt.exists(), 'Uncommitted generation attempt exists; stop for recovery instead of repeating the input')
                put(attempt, dict(id=row['id'], protocol_sha256=digest(run / 'protocol.json')))
                record, states = generate(model, tokenizer, row, old, eos)
                relative = f'features/{index:04d}.npy'
                e.save_array(run / relative, states)
                record.update(feature_file=relative, feature_sha256=digest(run / relative))
                records.append(record)
                e.repro.write_json(run / 'predictions.json', dict(protocol_sha256=digest(run / 'protocol.json'), records=records))
                print(f"{row['partition']} {len(records)}/240 {row['id']} saved", flush=True)
    except Exception as error:
        e.repro.write_json(run / 'last_failure.json', dict(completed=len(records), error=repr(error),
            completed_at=datetime.now(timezone.utc).isoformat()))
        raise
    finally:
        if model is not None:
            del model
            import torch
            torch.cuda.empty_cache()


def analyze(run, rows, labels, gate, protocol, tokenizer, write=True):
    require_ready(gate)
    import free_answer_study as free
    import numpy as np
    old, _ = free.load_probe(argparse.Namespace(run_dir=PROBE), 'chat', digest(PROBE / 'protocol.json'))
    metadata = read(run / 'semantic_probe.json')
    evaluation_lock(run, metadata, write=False)
    ordered = [r for r in rows if r['partition'] != 'semantic_eval'] + [r for r in rows if r['partition'] == 'semantic_eval']
    records = validate_cache(run, ordered, tokenizer, old)
    require(len(records) == 240, 'Reports require all240 cached answers; no partial evaluation disclosure')
    by_method = {'frozen_old_chat_L28': {r['id']: r for r in records}}
    if metadata['status'] == 'fit_complete':
        path = run / 'semantic_probe.pkl'
        require(digest(path) == metadata['pickle_sha256'], 'Semantic probe hash mismatch')
        new = pickle.loads(path.read_bytes())
        by_method['single_fit_semantic_L28'] = {r['id']: {
            **r, **predict(new, np.load(run / r['feature_file'], allow_pickle=False)),
            'probe_decision_pre_first_token': False, 'probe_feature_pre_first_token': True,
            'readout_timing': 'offline_on_saved_prefill_state_no_generation_feedback'} for r in records}
    for method, predictions in by_method.items():
        for part in ['semantic_train', 'semantic_dev', 'semantic_eval']:
            own = [r for r in rows if r['partition'] == part]
            report = metrics.summarize(own, predictions, labels)
            report['by_expression'] = {expr: metrics.summarize([r for r in own if r['expression'] == expr],
                predictions, labels) for expr in ['A', 'B']}
            report['bootstrap'] = metrics.bootstrap(own, predictions, labels)
            if method == 'single_fit_semantic_L28':
                report['paired_difference_vs_old'] = metrics.bootstrap(own, predictions, labels,
                    comparison=by_method['frozen_old_chat_L28'])
            report['behavior_pending'] = metrics.behavior_summary(own, labels, {})
            put(run / f'reports/{method}/{part}.json', report, write)
            put(run / f'reports/{method}/{part}_pairs.json', metrics.paired_rows(own, predictions, labels), write)
    # Input/answer-only packet deliberately omits probe, condition, partition and input labels.
    shuffled = sorted(rows, key=lambda r: text_hash('semantic-transfer-behavior-v1|' + r['id']))
    source = by_method['frozen_old_chat_L28']
    packet = dict(items=[dict(item_id=f'B{i:03d}', question=r['question'], documents=r['docs'],
        answer=source[r['id']]['raw_output']) for i, r in enumerate(shuffled, 1)])
    put(run / 'behavior_review/packet.json', packet, write)
    put(run / 'coordinator/behavior_mapping.json', {r['id']: f'B{i:03d}' for i, r in enumerate(shuffled, 1)}, write)
    put(run / 'behavior_review/ratings_template.json', dict(reviewer='', history_exposed=None,
        packet_sha256=digest(run / 'behavior_review/packet.json'),
        ratings=[dict(item_id=r['item_id'], **{f: 'unknown' for f in metrics.BEHAVIOR_FIELDS},
            rationale='', input_citations=[], output_citations=[]) for r in packet['items']]), write)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=['prepare', 'verify', 'run', 'analyze', 'verify-results'], default='prepare')
    parser.add_argument('--materials-dir', type=Path, default=MATERIALS)
    parser.add_argument('--run-dir', type=Path, default=DEFAULT)
    parser.add_argument('--approval', type=Path)
    args = parser.parse_args()
    materials, run = args.materials_dir.resolve(), args.run_dir.resolve()
    require(materials.is_relative_to(ROOT / 'runs') and run.is_relative_to(ROOT / 'runs'), 'Use project runs directories')
    require(not run.is_relative_to(materials) and not materials.is_relative_to(run), 'Use separate study/material directories')
    if args.stage in ['prepare', 'verify']:
        result = prepare(materials, run, args.approval, args.stage == 'prepare')
        print(serialize(result[2]))
    else:
        # Check persisted gate before expensive preparation or any probe/model operation.
        require_ready(read(run / 'review_gate.json'))
        result = prepare(materials, run, args.approval, write=False)
        import evidence_experiment as e
        with e.legacy.run_lock(run):
            rows, labels, gate, protocol, tokenizer = result
            if args.stage == 'run':
                execute(run, rows, labels, gate, protocol, tokenizer)
            else:
                analyze(run, rows, labels, gate, protocol, tokenizer, args.stage == 'analyze')


if __name__ == '__main__':
    main()
