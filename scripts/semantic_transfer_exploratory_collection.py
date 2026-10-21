"""User-authorized v5 exploratory collection only; no semantic gold, fits or formal gate changes."""

import argparse
from collections import Counter
import copy
from datetime import datetime, timezone
from pathlib import Path

import semantic_transfer_study_v5 as binding

ROOT, core = binding.ROOT, binding.core
DEFAULT = ROOT / 'runs/qwen2.5-3b-semantic-transfer-exploratory-v5-v1'
AMENDMENT = ROOT / 'prompts/semantic_transfer_exploratory_collection_v1.json'
require, read, digest, put, serialize = core.require, core.read, core.digest, core.put, core.serialize


def amendment():
    value = read(AMENDMENT)
    require(value['parent_frozen_design_sha256'] == digest(core.intake.DESIGN), 'Frozen design changed')
    require(value['materials_protocol_sha256'] == digest(binding.MATERIALS / 'protocol.json'), 'Wrong v5 materials')
    require(value['authorization']['actor'] == 'user' and value['authorization']['gpu_launch_actor'] == 'user'
        and value['authorization']['user_reply'] == '行直接开始运行吧', 'Explicit user amendment missing')
    scope = value['scope']
    require(scope['existing_v5_cells'] == scope['max_model_generations'] == 240
        and scope['max_new_training_fits'] == 0 and scope['max_new_tokens_each'] == 128
        and scope['fixed_old_probe_layer_zero_based'] == 28 and scope['formal_approved_labels_remain_null'] is True,
        'Exploratory budget/readout scope changed')
    require(scope['new_bases'] == scope['material_edits'] == 0 and scope['greedy'] is True
        and scope['old_probe_feedback_to_generator'] is False, 'Exploratory input/generation scope changed')
    require(all(value['interpretation'][k] is False for k in ['independent_semantic_approval',
        'author_modes_used_as_gold', 'formal_semantic_accuracy_or_macroF1', 'new_probe_training_or_dev_trigger',
        'causal_intervention', 'heldout380_access']), 'Exploratory collection cannot become formal approval')
    return value


def validate_run_location(run):
    run = run.resolve()
    binding.validate_locations(binding.MATERIALS, run)
    for path in [binding.DEFAULT, ROOT / 'runs/qwen2.5-3b-semantic-transfer-study-v5-preparation-audit-v1']:
        require(not run.is_relative_to(path.resolve()) and not path.resolve().is_relative_to(run),
            'Exploration must not modify formal v5 preparation or audit directories')


def prepare(run=DEFAULT, write=False):
    validate_run_location(run)
    change = amendment()
    rows, labels, gate, parent, tokenizer = binding.prepare(write=False)
    require(all(v is None for v in labels.values()) and gate['gpu_launch_ready'] is False,
        'This version binds the still-unapproved parent; do not change formal gates')
    preflight = read(binding.DEFAULT / 'preflight.json')
    prefix = change['technical_smoke']['prefix_ids']
    require(len(prefix) == len(set(prefix)) == 4 and set(prefix) <= {r['id'] for r in rows}, 'Invalid smoke prefix')
    by_id = {r['id']: r for r in rows}
    ordered = [by_id[k] for k in prefix] + [r for r in rows if r['id'] not in prefix]
    permission = dict(status='user_authorized_exploratory_collection_before_independent_review',
        amendment_sha256=digest(AMENDMENT), collection_allowed=True,
        independent_semantic_approval=False, formal_gpu_launch_ready=False,
        approved_semantic_labels=0, max_training_fits=0, max_model_generations=240,
        launch_actor='user', original_formal_review_gate_unchanged=True)
    plan = dict(ordered_ids=[r['id'] for r in ordered], smoke_prefix_ids=prefix,
        smoke_included_in_total240=True, no_fit_or_dev_selection=True,
        frozen_old_probe_sha256=digest(core.PROBE / 'chat/probe/probe.pkl'),
        parent_preparation_protocol_sha256=digest(binding.DEFAULT / 'protocol.json'),
        amendment_sha256=digest(AMENDMENT), evaluation_identity_is_provenance_only=True)
    protocol = copy.deepcopy(parent)
    protocol['formal_review_gate'] = protocol.pop('review_gate')
    protocol.update(task='semantic_transfer_exploratory_collection_v5_v1',
        collection_permission=permission, max_training_fits=0,
        selected_ids=plan['ordered_ids'], collection_plan=plan,
        formal_semantic_metrics_allowed=False, new_probe_training_allowed=False,
        staged_order=['four_existing_inputs_technical_smoke', 'remaining236_collection',
            'strict_cache_verify', 'technical_summary', 'unscored_behavior_export'],
        original_eval_no_longer_undisclosed_after_collection=True)
    protocol.pop('bootstrap_resamples', None)
    for path in [Path(__file__), ROOT / 'scripts/run_semantic_transfer_exploratory_collection.sh']:
        protocol['implementation_sha256'][str(path.relative_to(ROOT))] = digest(path)
    for path in [AMENDMENT] + [binding.DEFAULT / p for p in ['protocol.json', 'review_gate.json', 'approved_labels.json', 'preflight.json']]:
        protocol['sources'][str(path.resolve())] = digest(path)
    preflight = dict(preflight, collection_allowed=True, independent_semantic_approval=False,
        new_training_fits=0, max_model_generations=240, smoke_prefix_ids=prefix,
        full_input_tokens=preflight['total_input_tokens'], max_output_tokens=240*128)
    for name, value in [('protocol.json', protocol), ('collection_authorization.json', permission),
            ('collection_plan.json', plan), ('approved_labels.json', labels), ('preflight.json', preflight)]:
        put(run / name, value, write)
    return ordered, protocol, tokenizer


def require_collection_permission(run, protocol):
    permission = read(run / 'collection_authorization.json')
    require(permission == protocol['collection_permission'], 'Collection authorization changed')
    require(permission['collection_allowed'] is True and permission['independent_semantic_approval'] is False
        and permission['formal_gpu_launch_ready'] is False and permission['max_training_fits'] == 0,
        'Exploration does not grant formal approval or training')
    require(protocol['formal_semantic_metrics_allowed'] is False and protocol['new_probe_training_allowed'] is False,
        'Formal scoring/training is outside collection scope')
    require(all(v is None for v in read(run / 'approved_labels.json').values()), 'Exploratory labels must remain null')
    require(not any((run / name).exists() for name in ['fit_attempt.json', 'semantic_probe.pkl', 'semantic_probe.json',
        'fit_decision.json', 'evaluation_lock.json']), 'Unexpected training/formal-study artifact in collection directory')


def validate_attempts(run, rows, records):
    directory = run / 'generation_attempts'
    attempts = sorted(directory.glob('*.json')) if directory.exists() else []
    require(len(attempts) == len(records),
        'Uncommitted generation attempt exists; stop for explicit recovery instead of repeating an input')
    for index, path in enumerate(attempts):
        require(path.name == f'{index:04d}.json' and read(path) == dict(id=rows[index]['id'],
            protocol_sha256=digest(run / 'protocol.json')), 'Generation attempt order/protocol mismatch')


def smoke_gate(run, records, write=True):
    require(len(records) >= 4, 'Smoke requires four committed answers')
    first = records[:4]
    passed = all(r['raw_output'].strip() and r['ended_with_eos'] and not r['hit_output_limit'] for r in first)
    value = dict(status='technical_smoke_passed' if passed else 'technical_smoke_failed_stop',
        ids=[r['id'] for r in first], included_in_total240=True, extra_generations=0,
        nonempty=sum(bool(r['raw_output'].strip()) for r in first),
        ended_with_eos=sum(r['ended_with_eos'] for r in first),
        hit_output_limit=sum(r['hit_output_limit'] for r in first), passed=passed,
        semantic_correctness_assessed=False)
    put(run / 'smoke_gate.json', value, write)
    require(passed, 'Technical smoke failed; preserved answers must be reviewed, not regenerated or relabeled as refusals')
    return value


def load_old_probe():
    import free_answer_study as free
    old, _ = free.load_probe(argparse.Namespace(run_dir=core.PROBE), 'chat', digest(core.PROBE / 'protocol.json'))
    require(old['layer'] == 28 and old['scaler'].n_features_in_ == 2048, 'Wrong frozen old probe')
    return old


def collect(run, rows, protocol, tokenizer):
    require_collection_permission(run, protocol)
    import evidence_experiment as e
    import classification_semantic_baseline as baseline
    old = load_old_probe()
    records = core.validate_cache(run, rows, tokenizer, old)
    validate_attempts(run, rows, records)
    if len(records) >= 4:
        smoke_gate(run, records)
    model = None
    eos = baseline.eos_ids(protocol['model'], tokenizer)
    try:
        for row in rows[len(records):]:
            if model is None:
                baseline.assert_gpu_idle()
                model = e.load_model(protocol['model'])
            index = len(records)
            attempt = run / f'generation_attempts/{index:04d}.json'
            require(not attempt.exists(), 'Uncommitted generation attempt exists; explicit recovery required')
            put(attempt, dict(id=row['id'], protocol_sha256=digest(run / 'protocol.json')))
            record, states = core.generate(model, tokenizer, row, old, eos)
            relative = f'features/{index:04d}.npy'
            e.save_array(run / relative, states)
            record.update(feature_file=relative, feature_sha256=digest(run / relative))
            records.append(record)
            e.repro.write_json(run / 'predictions.json', dict(protocol_sha256=digest(run / 'protocol.json'), records=records))
            e.repro.write_json(run / 'progress.json', dict(status='exploratory_collection_running',
                completed=len(records), planned=240, independent_semantic_approval=False, trained_probes=0,
                last_saved_at=record['completed_at']))
            print(f'exploratory {len(records)}/240 {row["id"]} saved', flush=True)
            if len(records) == 4:
                # Re-read committed caches before allowing the remaining236.
                core.validate_cache(run, rows, tokenizer, old)
                smoke_gate(run, records)
    except Exception as error:
        e.repro.write_json(run / 'last_failure.json', dict(completed=len(records), error=repr(error),
            completed_at=datetime.now(timezone.utc).isoformat(), no_automatic_regeneration=True))
        raise
    finally:
        if model is not None:
            del model
            import torch
            torch.cuda.empty_cache()


def finish(run, rows, protocol, tokenizer, write=True):
    require_collection_permission(run, protocol)
    old = load_old_probe()
    records = core.validate_cache(run, rows, tokenizer, old)
    validate_attempts(run, rows, records)
    require(len(records) == len(rows) == 240, 'Completion reports require all240 cached inputs')
    smoke_gate(run, records, write)
    summary = dict(status='exploratory_collection_complete_not_semantically_validated',
        completed=240, model_generations=240, extra_smoke_generations=0,
        input_tokens=sum(r['input_tokens'] for r in records), output_tokens=sum(r['generated_tokens'] for r in records),
        empty_outputs=sum(not r['raw_output'].strip() for r in records),
        ended_with_eos=sum(r['ended_with_eos'] for r in records), hit_output_limit=sum(r['hit_output_limit'] for r in records),
        frozen_old_probe_predictions=dict(Counter(r['probe_pred'] for r in records)),
        prediction_distribution_is_not_semantic_accuracy=True,
        independent_semantic_labels=0, semantic_accuracy=None, semantic_macroF1=None,
        training_fits=0, probe_feedback=False, original_formal_gpu_gate_changed=False,
        original_eval_partition_not_prospective_confirmation=True,
        behavior_ratings_completed=0, actual_behavior_rates=None,
        amended_order='Exploratory collection before independent input review; future labels/scoring must disclose timing and exposure.')
    put(run / 'reports/collection.json', summary, write)
    by_id = {r['id']: r for r in records}
    shuffled = sorted(rows, key=lambda r: core.text_hash('exploratory-v5-behavior-v1|' + r['id']))
    packet = dict(items=[dict(item_id=f'B{i:03d}', question=r['question'], documents=r['docs'],
        answer=by_id[r['id']]['raw_output']) for i, r in enumerate(shuffled, 1)])
    put(run / 'behavior_review/packet.json', packet, write)
    put(run / 'coordinator/behavior_mapping.json', {r['id']: f'B{i:03d}' for i, r in enumerate(shuffled, 1)}, write)
    put(run / 'behavior_review/ratings_template.json', dict(reviewer='', history_exposed=None,
        packet_sha256=digest(run / 'behavior_review/packet.json'),
        ratings=[dict(item_id=r['item_id'], status='unreviewed',
            **{f:'unknown' for f in core.metrics.BEHAVIOR_FIELDS}, rationale='', input_citations=[], output_citations=[])
            for r in packet['items']]), write)
    put(run / 'completion.json', dict(status=summary['status'], protocol_sha256=digest(run / 'protocol.json'),
        predictions_sha256=digest(run / 'predictions.json'), collection_summary_sha256=digest(run / 'reports/collection.json'),
        collection_plan_sha256=digest(run / 'collection_plan.json'), completed=240, trained_probes=0,
        independent_semantic_approval=False), write)
    progress = dict(status=summary['status'], completed=240, planned=240,
        independent_semantic_approval=False, trained_probes=0, last_saved_at=records[-1]['completed_at'])
    if write:
        import evidence_experiment as e
        e.repro.write_json(run / 'progress.json', progress)
    else:
        require(read(run / 'progress.json') == progress, 'Completion progress differs')
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=['prepare', 'verify', 'run', 'finish', 'verify-results', 'all'], default='verify')
    parser.add_argument('--run-dir', type=Path, default=DEFAULT)
    args = parser.parse_args()
    run = args.run_dir.resolve()
    rows, protocol, tokenizer = prepare(run, write=args.stage == 'prepare')
    if args.stage in ['prepare','verify']:
        print(serialize(protocol['collection_permission']))
        return
    import evidence_experiment as e
    with e.legacy.run_lock(run):
        if args.stage in ['run','all']:
            collect(run, rows, protocol, tokenizer)
        if args.stage in ['finish','verify-results','all']:
            print(serialize(finish(run, rows, protocol, tokenizer, write=args.stage != 'verify-results')))


if __name__ == '__main__':
    main()
