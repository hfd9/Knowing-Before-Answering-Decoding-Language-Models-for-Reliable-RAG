"""One user-amended CPU fit on exposed-author references and cached L28 states.

The original formal executor, review gates and labels remain unchanged. This
attempt consumes the original design's shared one-fit allowance, even on failure.
"""

import argparse
from collections import Counter
from datetime import datetime, timezone
import fcntl
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import pickle
import time
import warnings

import numpy as np

import semantic_transfer_exploratory_behavior_review as review
import semantic_transfer_metrics as metrics

ROOT = Path(__file__).resolve().parents[1]
AMENDMENT = 'prompts/semantic_transfer_exploratory_retrain_v1.json'
DESIGN = 'prompts/semantic_transfer_validation_v1.json'
RUN = 'runs/qwen2.5-3b-semantic-transfer-exploratory-author-retrain-v1'
PREFIX = 'docs/records/2026-10-21-semantic-transfer-exploratory-retrain'
BUDGET = 'runs/semantic-transfer-shared-one-fit-budget-v1.json'
MODES = metrics.MODES


def sha(path):
    return review.digest(Path(path).read_bytes())


def put(path, value, write=True):
    data = review.json_bytes(value)
    if path.exists():
        review.require(path.read_bytes() == data, 'Frozen artifact differs: ' + str(path))
    elif write:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    else:
        raise ValueError('Missing artifact: ' + str(path))


def load_features(root, records, ids):
    """Read only the explicitly supplied IDs. Fitting calls this with train A only."""
    vectors = []
    for key in ids:
        record = records[key]
        relative = Path(record['feature_file'])
        review.require(len(relative.parts) == 2 and relative.parts[0] == 'features'
            and relative.suffix == '.npy', 'Unexpected cached feature path')
        path = root / review.RUN / relative
        review.require(sha(path) == record['feature_sha256'], 'Cached feature hash changed')
        array = np.load(path, allow_pickle=False)
        review.require(array.shape == (36, 2048) and array.dtype == np.float16
            and np.isfinite(array).all() and not np.any(np.all(array == 0, axis=1)),
            'Invalid cached states')
        vectors.append(array[28].astype(np.float32))
    return np.stack(vectors)


def training_rows(rows, labels):
    result = [r for r in rows if r['partition'] == 'semantic_train' and r['expression'] == 'A']
    review.require(len(result) == 48 and len({r['original_id'] for r in result}) == 12,
        'Fit must use exactly 12 training bases / A48')
    counts = Counter(labels[r['id']] for r in result)
    review.require(counts == Counter(answer=24, refuse=12, conflict=12),
        'Incomplete/unknown training references or class support changed')
    return result


def prepare(root=ROOT, write=False):
    amendment = review.read(root, AMENDMENT)
    review.require(amendment['parent_frozen_design_sha256'] == sha(root / DESIGN)
        and amendment['authorization']['user_reply'] == '你直接开始', 'Wrong amendment/design')
    scope = amendment['scope']
    review.require(scope['max_training_fits'] == 1 and scope['layer_zero_based'] == 28
        and scope['counts_against_original_design_one_fit_budget'] is True
        and scope['new_model_forwards'] == scope['new_answers'] == 0,
        'Exploratory fit scope changed')
    preserved = review.read(root, PREFIX + '-preserved.json')
    review.require(len(preserved) == 901, 'Unexpected preservation inventory')
    review.verify_files(root, preserved)
    packet, ratings, _ = review.load_sealed(root)
    rows = review.join_rows(root, packet, ratings)
    author = review.read(root, review.AUTHOR)
    review.require(sha(root / review.AUTHOR) == amendment['author_ratings_sha256']
        and author['independent_gold'] is False and author['approved_for_training'] is False,
        'Author reference is not independent approval')
    labels = {r['id']: r['exposed_author_input_mode'] for r in rows}
    source = review.read(root, review.RUN + '/protocol.json')
    review.require(source['design_sha256'] == sha(root / DESIGN)
        and sha(root / (review.RUN + '/protocol.json')) == amendment['source_collection_protocol_sha256']
        and sha(root / review.MATERIALS) == amendment['material_inputs_sha256'],
        'Wrong cached collection or materials')
    records = {r['id']: r for r in review.read(root, review.RUN + '/predictions.json')['records']}
    review.require(set(records) == set(labels) and len(records) == 240, 'Missing cached records')
    ids = [r['id'] for r in rows]
    features = load_features(root, records, ids)
    train = training_rows(rows, labels)
    dev = [r for r in rows if r['partition'] == 'semantic_dev']
    numeric = metrics.trigger_on_dev(dev, records, labels)
    decision = dict(status='exposed_author_dev_numeric_trigger_only',
        original_numeric_rule_result=numeric, triggered=numeric['triggered'],
        independent_semantic_quality_gate_satisfied=False,
        amended_exploratory_fit_allowed=bool(numeric['triggered']),
        evaluation_used_for_setting_selection=False,
        all_original_outputs_and_author_judgments_previously_seen=True,
        training_ids=[r['id'] for r in train],
        training_class_counts=dict(Counter(labels[r['id']] for r in train)))
    inventory = dict(cells=240, source_feature_shape=[36, 2048], layer_zero_based=28,
        selected_vector_shape=list(features.shape), source_dtype='float16', fit_dtype='float32',
        features={key: dict(file=records[key]['feature_file'], sha256=records[key]['feature_sha256'])
            for key in ids},
        all_vectors_sha256=review.digest(features.tobytes()),
        preflight_inspected_all_cached_vectors=True,
        fitting_function_reads_training_A_only=True)
    paths = [AMENDMENT, DESIGN, review.AUTHOR, review.MATERIALS,
        review.RUN + '/protocol.json', review.RUN + '/predictions.json',
        review.RUN + '/approved_labels.json', review.PREFIX + '-seal.json',
        PREFIX + '-preserved.json', 'scripts/semantic_transfer_exploratory_retrain.py',
        'tests/test_semantic_transfer_exploratory_retrain.py',
        'scripts/semantic_transfer_metrics.py', 'scripts/semantic_transfer_study_v5.py']
    protocol = dict(schema_version=1,
        task='semantic_transfer_chat_L28_exposed_author_retrain_v1',
        design_sha256=sha(root / DESIGN), amendment_sha256=sha(root / AMENDMENT),
        sources={p: sha(root / p) for p in paths},
        versions={n: version(n) for n in ['numpy', 'scikit-learn']},
        history_exposed=True, independent_gold=False,
        formal_gate_unchanged=True, formal_approved_labels_added=0,
        author_reference_used_under_separate_exploratory_amendment=True,
        all_eval_outputs_already_seen=True, prospective_confirmation=False,
        max_training_fits=1, fixed_layer_zero_based=28,
        classifier=amendment['classifier'], training_ids=decision['training_ids'],
        shared_budget_path=BUDGET, shared_budget_task_prefix='semantic_transfer_chat_L28_',
        development_decision_sha256=review.digest(review.json_bytes(decision)),
        feature_inventory_sha256=review.digest(review.json_bytes(inventory)),
        labels_sha256=review.digest(review.json_bytes(labels)),
        new_gpu_calls=0, new_model_forwards=0, new_generated_answers=0,
        new_readout_timing='Offline after generation from pre-first-token captured features')
    run = root / RUN
    for name, value in [('protocol.json', protocol), ('author_reference_labels.json', labels),
            ('fit_decision.json', decision), ('feature_inventory.json', inventory)]:
        put(run / name, value, write)
    return rows, labels, records, protocol, decision


def shared_attempts(root, design_sha, own_run):
    found = []
    for marker in sorted((root / 'runs').glob('*/fit_attempt.json')):
        if marker.parent.resolve() == own_run.resolve():
            continue
        protocol = marker.parent / 'protocol.json'
        review.require(protocol.exists(), 'Unidentified fit marker requires review: ' + str(marker))
        value = json.loads(protocol.read_text())
        if value.get('design_sha256') == design_sha:
            found.append(str(marker.relative_to(root)))
    return found


def claim_budget(root, run, protocol):
    review.require(not shared_attempts(root, protocol['design_sha256'], run),
        'This design already consumed its fit allowance in another run')
    claim = dict(design_sha256=protocol['design_sha256'], owner_run=str(run.relative_to(root)),
        protocol_sha256=sha(run / 'protocol.json'), maximum_attempts=1,
        counts_against_original_design_budget=True,
        created_at=datetime.now(timezone.utc).isoformat(), failed_or_interrupted_attempt_is_consumed=True)
    path = root / BUDGET
    path.parent.mkdir(parents=True, exist_ok=True)
    # O_EXCL prevents a second process/run from acquiring the same design allowance.
    with path.open('x') as stream:
        stream.write(review.json_bytes(claim).decode())
    marker = dict(protocol_sha256=sha(run / 'protocol.json'), budget_claim_sha256=sha(path),
        training_ids=protocol['training_ids'], maximum_attempts=1,
        created_at=claim['created_at'])
    with (run / 'fit_attempt.json').open('x') as stream:
        stream.write(review.json_bytes(marker).decode())
    return marker


def saved_probe(root, run):
    metadata = json.loads((run / 'semantic_probe.json').read_text())
    review.require(metadata['status'] == 'fit_complete', 'Failed/interrupted fit cannot be retried')
    marker = json.loads((run / 'fit_attempt.json').read_text())
    review.require(marker['protocol_sha256'] == sha(run / 'protocol.json')
        and marker['budget_claim_sha256'] == sha(root / BUDGET)
        and metadata['fit_attempt_sha256'] == sha(run / 'fit_attempt.json')
        and metadata['pickle_sha256'] == sha(run / 'semantic_probe.pkl'), 'Fit artifact changed')
    claim = json.loads((root / BUDGET).read_text())
    review.require(claim['owner_run'] == str(run.relative_to(root))
        and claim['protocol_sha256'] == sha(run / 'protocol.json'), 'Shared budget owner changed')
    return pickle.loads((run / 'semantic_probe.pkl').read_bytes()), metadata


def fit_once(root, rows, labels, records, protocol, decision, factories=None):
    run = root / RUN
    review.require(decision['amended_exploratory_fit_allowed'], 'Dev numeric trigger not met')
    if (run / 'semantic_probe.json').exists():
        return saved_probe(root, run)
    review.require(not (run / 'fit_attempt.json').exists() and not (root / BUDGET).exists(),
        'Existing attempt/claim without completion; do not retry or reset budget')
    claim_budget(root, run, protocol)
    started = time.monotonic()
    try:
        selected = training_rows(rows, labels)
        ids = [r['id'] for r in selected]
        review.require(ids == protocol['training_ids'], 'Training IDs changed')
        x = load_features(root, records, ids)
        y = [MODES.index(labels[key]) for key in ids]
        if factories is None:
            from sklearn.linear_model import LogisticRegression
            from sklearn.preprocessing import StandardScaler
            factories = StandardScaler, LogisticRegression
        scaler = factories[0]()
        classifier = factories[1](**protocol['classifier'])
        with warnings.catch_warnings(record=True) as notices:
            warnings.simplefilter('always')
            scaler.fit(x)
            classifier.fit(scaler.transform(x), y)
        probe = dict(layer=28, scaler=scaler, router=classifier)
        payload = run / 'semantic_probe.pkl'
        temp = payload.with_suffix('.pkl.tmp')
        temp.write_bytes(pickle.dumps(probe, protocol=pickle.HIGHEST_PROTOCOL))
        os.replace(temp, payload)
        metadata = dict(status='fit_complete', training_fits=1,
            fit_attempt_sha256=sha(run / 'fit_attempt.json'), pickle_sha256=sha(payload),
            training_ids=ids, training_rows=48, training_bases=12,
            training_class_counts=dict(Counter(labels[k] for k in ids)),
            training_matrix_sha256=review.digest(x.tobytes()),
            n_iter=classifier.n_iter_.tolist(), classes=classifier.classes_.tolist(),
            warnings=[str(n.message) for n in notices],
            convergence_limit_reached=bool(np.max(classifier.n_iter_) >= 2000),
            elapsed_seconds=time.monotonic() - started,
            completed_at=datetime.now(timezone.utc).isoformat(),
            history_exposed=True, independent_gold=False,
            original_design_fit_budget_remaining=0)
        put(run / 'semantic_probe.json', metadata)
        return probe, metadata
    except Exception as error:
        put(run / 'semantic_probe.json', dict(status='fit_failed_no_retry', training_fits=1,
            fit_attempt_sha256=sha(run / 'fit_attempt.json'), error=repr(error),
            original_design_fit_budget_remaining=0))
        raise


def predict(probe, matrix, ids):
    probability = probe['router'].predict_proba(probe['scaler'].transform(matrix))
    review.require(probe['layer'] == 28 and list(probe['router'].classes_) == [0, 1, 2]
        and probability.shape == (len(ids), 3) and np.isfinite(probability).all()
        and np.all(probability >= 0) and np.allclose(probability.sum(axis=1), 1),
        'Invalid saved probe/prediction')
    return {key: dict(id=key, probe_pred=MODES[int(np.argmax(p))],
        probe_probabilities=dict(zip(MODES, map(float, p))), probe_layer_zero_based=28,
        probe_feature_pre_first_token=True, probe_decision_pre_first_token=False,
        executed_offline_after_generation=True) for key, p in zip(ids, probability)}


def behavior_report(rows, labels, predictions):
    ratings = {r['id']: r for r in rows}
    insufficient = [r for r in rows if labels[r['id']] == 'refuse']
    conflicts = [r for r in rows if labels[r['id']] == 'conflict']
    return dict(primary_unchanged=metrics.behavior_summary(rows, labels, ratings),
        insufficient_probe_refuse=review.rate([r for r in insufficient
            if predictions[r['id']]['probe_pred'] == 'refuse'], 'has_substantive_answer'),
        insufficient_probe_not_refuse=review.rate([r for r in insufficient
            if predictions[r['id']]['probe_pred'] != 'refuse'], 'has_substantive_answer'),
        conflict_probe_conflict_unresolved_selection=review.rate([r for r in conflicts
            if predictions[r['id']]['probe_pred'] == 'conflict'], 'selection_without_resolution'))


def analyze(root, rows, labels, records, protocol, write=False):
    run = root / RUN
    probe, metadata = saved_probe(root, run)
    lock = dict(protocol_sha256=sha(run / 'protocol.json'),
        semantic_probe_sha256=metadata['pickle_sha256'],
        author_reference_labels_sha256=sha(run / 'author_reference_labels.json'),
        original_evaluation_outputs_already_seen=True,
        lock_prevents_postfit_revision_only=True, clean_prospective_evaluation=False)
    put(run / 'offline_comparison_lock.json', lock, write)
    ids = [r['id'] for r in rows]
    vectors = load_features(root, records, ids)
    new = predict(probe, vectors, ids)
    old_path = root / 'runs/qwen2.5-3b-free-answer-study/chat/probe/probe.pkl'
    design = review.read(root, DESIGN)
    review.require(sha(old_path) == design['probe']['old_source_pkl_sha256'], 'Old probe changed')
    old_replayed = predict(pickle.loads(old_path.read_bytes()), vectors, ids)
    error = max(abs(old_replayed[k]['probe_probabilities'][m] - records[k]['probe_probabilities'][m])
        for k in ids for m in MODES)
    review.require(error < 1e-10 and all(old_replayed[k]['probe_pred'] == records[k]['probe_pred']
        for k in ids), 'Cached old-probe values did not replay')
    slices = dict(fit_train_A=[r for r in rows if r['partition'] == 'semantic_train' and r['expression'] == 'A'],
        same_base_train_B=[r for r in rows if r['partition'] == 'semantic_train' and r['expression'] == 'B'],
        source_dev=[r for r in rows if r['partition'] == 'semantic_dev'],
        source_eval=[r for r in rows if r['partition'] == 'semantic_eval'],
        source_eval_A=[r for r in rows if r['partition'] == 'semantic_eval' and r['expression'] == 'A'],
        source_eval_B=[r for r in rows if r['partition'] == 'semantic_eval' and r['expression'] == 'B'],
        all_descriptive=rows)
    report = dict(status='one_fit_exploratory_author_reference_comparison_complete',
        history_exposed=True, independent_gold=False, formal_semantic_labels_added=0,
        new_gpu_calls=0, new_generated_answers=0, new_probe_fits=1,
        original_design_fit_budget_remaining=0,
        author_reference_counts=dict(Counter(labels.values())),
        old_probability_replay_max_abs_error=error, fit=metadata,
        interpretation='Agreement/accuracy and macroF1 below use exposed-author references, '
            'not independent semantic gold. All source evaluation outputs were previously viewed. '
            'New readout runs offline on pre-generation features; existing behavior cannot change. '
            'Bootstrap retains entire bases and excludes annotation/training uncertainty.',
        slices={})
    for name, group in slices.items():
        entry = dict(cells=len(group), bases=len({r['original_id'] for r in group}),
            old_author_reference_metrics=metrics.summarize(group, records, labels),
            new_author_reference_metrics=metrics.summarize(group, new, labels),
            new_minus_old_paired_base_bootstrap=metrics.bootstrap(group, new, labels,
                repeats=10000, seed=42, comparison=records),
            old_behavior=behavior_report(group, labels, records),
            new_behavior=behavior_report(group, labels, new))
        report['slices'][name] = entry
    cells = [dict(id=r['id'], original_id=r['original_id'], partition=r['partition'],
        expression=r['expression'], condition=r['condition'],
        author_reference=labels[r['id']], in_fit=r['id'] in protocol['training_ids'],
        old_probe=records[r['id']]['probe_pred'], new_probe=new[r['id']]['probe_pred'],
        old_probabilities=records[r['id']]['probe_probabilities'],
        new_probabilities=new[r['id']]['probe_probabilities'],
        **{f: r[f] for f in metrics.BEHAVIOR_FIELDS}) for r in rows]
    for name, value in [('offline_predictions.json', list(new.values())),
            ('reports/comparison.json', report), ('reports/cells.json', cells)]:
        put(run / name, value, write)
    put(root / (PREFIX + '.json'), report, write)
    data = review.csv_bytes(cells)
    csv_path = root / (PREFIX + '-cells.csv')
    if csv_path.exists():
        review.require(csv_path.read_bytes() == data, 'Comparison CSV changed')
    else:
        review.require(write, 'Missing comparison CSV')
        csv_path.write_bytes(data)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=['prepare', 'verify-prepared', 'run', 'analyze', 'verify-results'], required=True)
    args = parser.parse_args()
    rows, labels, records, protocol, decision = prepare(write=args.stage == 'prepare')
    if args.stage in ['prepare', 'verify-prepared']:
        print(json.dumps(dict(stage=args.stage, training_rows=48,
            trigger=decision['triggered'], new_fits_this_stage=0,
            existing_fit_attempt=(ROOT / RUN / 'fit_attempt.json').exists())))
        return
    if args.stage == 'run':
        lock_path = ROOT / 'runs/.semantic-transfer-one-fit.lock'
        with lock_path.open('a') as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            fit_once(ROOT, rows, labels, records, protocol, decision)
    report = analyze(ROOT, rows, labels, records, protocol,
        write=args.stage in ['run', 'analyze'])
    print(json.dumps(dict(stage=args.stage, new_training_fits=report['new_probe_fits'],
        remaining_design_fits=0, source_eval_reference_agreement=report['slices'][
            'source_eval']['new_author_reference_metrics']['accuracy'], independent_gold=False)))


if __name__ == '__main__':
    main()
