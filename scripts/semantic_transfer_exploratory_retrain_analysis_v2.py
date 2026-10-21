"""Analyze the sealed one-fit model; repair token metadata without any fitting path."""

import argparse
from collections import Counter
import pickle
from pathlib import Path

import semantic_transfer_exploratory_retrain as fit

ROOT, PREFIX = fit.ROOT, fit.PREFIX
OUTPUT = 'runs/qwen2.5-3b-semantic-transfer-exploratory-author-retrain-analysis-v2'
SEAL = PREFIX + '-fit-seal.json'


def with_token_metadata(predictions, original):
    fit.review.require(set(predictions) == set(original), 'Prediction/source ID mismatch')
    result = {}
    for key, value in predictions.items():
        length = original[key]['input_tokens']
        fit.review.require(type(length) is int and length > 0, 'Invalid source token length')
        result[key] = dict(value, input_tokens=length)
    return result


def compute(root=ROOT):
    seal = fit.review.read(root, SEAL)
    fit.review.require(seal['fit_attempts'] == 1 and seal['remaining_original_design_fits'] == 0,
        'Wrong sealed budget')
    fit.review.verify_files(root, seal['files'])
    rows, labels, records, protocol, _ = fit.prepare(root, write=False)
    probe, metadata = fit.saved_probe(root, root / fit.RUN)
    ids = [r['id'] for r in rows]
    vectors = fit.load_features(root, records, ids)
    new = with_token_metadata(fit.predict(probe, vectors, ids), records)
    old_path = root / 'runs/qwen2.5-3b-free-answer-study/chat/probe/probe.pkl'
    design = fit.review.read(root, fit.DESIGN)
    fit.review.require(fit.sha(old_path) == design['probe']['old_source_pkl_sha256'], 'Old probe changed')
    old_replayed = fit.predict(pickle.loads(old_path.read_bytes()), vectors, ids)
    error = max(abs(old_replayed[k]['probe_probabilities'][m] - records[k]['probe_probabilities'][m])
        for k in ids for m in fit.MODES)
    fit.review.require(error < 1e-10 and all(old_replayed[k]['probe_pred'] == records[k]['probe_pred']
        for k in ids), 'Old probability replay mismatch')
    slices = dict(fit_train_A=[r for r in rows if r['partition'] == 'semantic_train' and r['expression'] == 'A'],
        same_base_train_B=[r for r in rows if r['partition'] == 'semantic_train' and r['expression'] == 'B'],
        source_dev=[r for r in rows if r['partition'] == 'semantic_dev'],
        source_eval=[r for r in rows if r['partition'] == 'semantic_eval'],
        source_eval_A=[r for r in rows if r['partition'] == 'semantic_eval' and r['expression'] == 'A'],
        source_eval_B=[r for r in rows if r['partition'] == 'semantic_eval' and r['expression'] == 'B'],
        all_descriptive=rows)
    report = dict(status='one_fit_exploratory_author_reference_comparison_complete', analysis_version=2,
        history_exposed=True, independent_gold=False, formal_semantic_labels_added=0,
        new_gpu_calls=0, new_generated_answers=0, new_probe_fits=1,
        analysis_stage_new_fits=0, original_design_fit_budget_remaining=0,
        author_reference_counts=dict(Counter(labels.values())),
        old_probability_replay_max_abs_error=error, fit=metadata,
        analysis_v1_error='KeyError: input_tokens after fit completed; original failed implementation retained',
        analysis_v2_fix='Copy exact frozen source input_tokens into new offline predictions before paired metrics',
        fit_seal_sha256=fit.sha(root / SEAL),
        interpretation='All agreement/accuracy/macroF1 values use exposed-author references, not independent '
            'semantic gold. Source eval outputs and author judgments were previously viewed. New readout '
            'is offline on pre-generation features and cannot change existing behavior. Paired bootstrap '
            'resamples bases and excludes judgment/training uncertainty.', slices={})
    for name, group in slices.items():
        report['slices'][name] = dict(cells=len(group), bases=len({r['original_id'] for r in group}),
            old_author_reference_metrics=fit.metrics.summarize(group, records, labels),
            new_author_reference_metrics=fit.metrics.summarize(group, new, labels),
            new_minus_old_paired_base_bootstrap=fit.metrics.bootstrap(group, new, labels,
                repeats=10000, seed=42, comparison=records),
            old_behavior=fit.behavior_report(group, labels, records),
            new_behavior=fit.behavior_report(group, labels, new))
    cells = [dict(id=r['id'], original_id=r['original_id'], partition=r['partition'],
        expression=r['expression'], condition=r['condition'], author_reference=labels[r['id']],
        in_fit=r['id'] in protocol['training_ids'],
        input_tokens=records[r['id']]['input_tokens'], old_probe=records[r['id']]['probe_pred'],
        new_probe=new[r['id']]['probe_pred'], old_probabilities=records[r['id']]['probe_probabilities'],
        new_probabilities=new[r['id']]['probe_probabilities'],
        **{f: r[f] for f in fit.metrics.BEHAVIOR_FIELDS}) for r in rows]
    return report, cells, new


def execute(root=ROOT, write=False):
    report, cells, predictions = compute(root)
    protocol = dict(task='offline_analysis_v2_of_sealed_single_fit', new_fits_in_analysis=0,
        source_fit_run=fit.RUN, source_fit_seal_sha256=fit.sha(root / SEAL),
        source_model_sha256=report['fit']['pickle_sha256'],
        implementation_sha256={p: fit.sha(root / p) for p in [
            'scripts/semantic_transfer_exploratory_retrain_analysis_v2.py',
            'tests/test_semantic_transfer_exploratory_retrain_analysis_v2.py']},
        offline_readout_from_prefill_features=True, original_eval_outputs_previously_seen=True,
        prospective_confirmation=False)
    output = root / OUTPUT
    for name, value in [('protocol.json', protocol), ('comparison.json', report),
            ('cells.json', cells), ('offline_predictions.json', list(predictions.values()))]:
        fit.put(output / name, value, write)
    fit.put(root / (PREFIX + '.json'), report, write)
    data = fit.review.csv_bytes(cells)
    path = root / (PREFIX + '-cells.csv')
    if path.exists():
        fit.review.require(path.read_bytes() == data, 'Comparison CSV changed')
    else:
        fit.review.require(write, 'Missing comparison CSV')
        path.write_bytes(data)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=['analyze', 'verify'], required=True)
    args = parser.parse_args()
    report = execute(write=args.stage == 'analyze')
    print(fit.json.dumps(dict(stage=args.stage, analysis_version=2, total_real_fits=1,
        new_analysis_fits=0, remaining_design_fits=0,
        source_eval_reference_agreement=report['slices']['source_eval']['new_author_reference_metrics'][
            'accuracy'], independent_gold=False)))


if __name__ == '__main__':
    main()
