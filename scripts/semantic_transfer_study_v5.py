"""v5-bound chat L28 study preparation and execution; independent review still gates inference."""

import argparse
from importlib.metadata import version
from pathlib import Path

import semantic_transfer_study as core
import semantic_transfer_v5_acceptance as acceptance

ROOT, PROBE = core.ROOT, core.PROBE
MATERIALS = ROOT / 'runs/qwen2.5-3b-semantic-transfer-materials-v5'
DEFAULT = ROOT / 'runs/qwen2.5-3b-semantic-transfer-study-v5-preparation-v1'
ACCEPTANCE = acceptance.DEFAULT
require, read, digest, put, serialize = core.require, core.read, core.digest, core.put, core.serialize


def validate_locations(materials, run):
    materials, run = materials.resolve(), run.resolve()
    require(materials == MATERIALS.resolve(), 'This version binds the frozen v5 materials directory')
    require(run.is_relative_to(ROOT / 'runs'), 'Use project runs directories')
    protected = [MATERIALS, core.MATERIALS, core.DEFAULT, ACCEPTANCE,
        ROOT / 'runs/qwen2.5-3b-semantic-transfer-review-intake-v4']
    for path in protected:
        require(not run.is_relative_to(path.resolve()) and not path.resolve().is_relative_to(run),
            'Keep v5 study separate from protected material, intake, acceptance and old study directories')


def material_inputs(materials):
    rows, unavailable, mapping, packets, design = core.intake.load_materials(materials)
    require(not unavailable and len(rows) == 240, 'Complete240 v5 materials required')
    protocol = read(materials / 'protocol.json')
    require(protocol.get('material_version') == 5, 'Expected v5 material version')
    for field in ['implementation_sha256', 'source_sha256']:
        for name, sha in protocol[field].items():
            require(digest(ROOT / name) == sha, f'Frozen v5 dependency changed: {name}')
    require(digest(ROOT / 'prompts/semantic_transfer_materials_v5.json') == protocol['authored_sha256'],
        'Frozen v5 specification changed')
    for relative, key in [('coordinator/source_policy_amendment.json', 'source_policy_amendment_sha256'),
            ('sources/supplemental_source_excerpts.json', 'supplemental_sources_sha256'),
            ('coordinator/control_revision.json', 'control_revision_sha256')]:
        require(digest(materials / relative) == protocol[key], 'Frozen v5 source/control snapshot changed')
    return rows, mapping, packets, design


def prepare(materials=MATERIALS, run=DEFAULT, approval=None, write=True):
    validate_locations(materials, run)
    rows, mapping, packets, design = material_inputs(materials)
    # The sealed exposed QA pass is context/risk provenance only. Its semantic
    # modes are never passed to approval_labels, fit, generation or metrics.
    acceptance.process(ACCEPTANCE, write=False)
    labels, gate, evidence = core.approval_labels(materials, rows, mapping, packets, design, approval)
    gate.update(material_version=5, author_acceptance_is_independent_approval=False,
        author_acceptance_risks_retained=True, old_v4_study_directory_unchanged=True)
    import evidence_experiment as e
    from transformers import AutoTokenizer
    probe_sources = [PROBE / p for p in ['protocol.json', 'chat/probe/probe.json', 'chat/probe/probe.pkl',
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
    material_preflight = read(materials / 'preflight.json')
    require(lengths == material_preflight['input_tokens'] and prompts == material_preflight['prompt_sha256'],
        'v5 material preflight interface mismatch')
    sources = [materials / p for p in ['protocol.json', 'preflight.json', 'materials/inputs.json',
        'materials/unavailable_cells.json', 'coordinator/review_mapping.json', 'coordinator/control_revision.json',
        'review_a/packet.json', 'review_b/packet.json', 'coordinator/source_policy_amendment.json',
        'sources/supplemental_source_excerpts.json']]
    sources += [ACCEPTANCE / p for p in ['protocol.json', 'summary.json', 'risks.json', 'seal_manifest.json']]
    # Freeze the unchanged execution implementation as well as this new binding.
    files = ['scripts/semantic_transfer_study_v5.py', 'scripts/run_semantic_transfer_study_v5.sh',
        'scripts/semantic_transfer_study.py', 'scripts/semantic_transfer_metrics.py',
        'scripts/semantic_transfer_review_intake.py', 'scripts/semantic_transfer_v5_acceptance.py',
        'scripts/run_semantic_transfer_v5_acceptance.sh',
        'scripts/evidence_experiment.py', 'scripts/free_answer_study.py', 'scripts/free_answer_review.py',
        'scripts/small_repro.py', 'scripts/prompt_baseline.py', 'scripts/analyze_prompt_baseline.py',
        'scripts/classification_semantic_baseline.py', 'scripts/classification_prompt_search.py',
        'code/prompts.py', 'prompts/baseline_prompts.json', 'configs/local.env']
    protocol = dict(schema_version=1, task='semantic_transfer_chat_L28_v5_v1', material_version=5,
        materials_dir=str(materials.resolve()), design_sha256=digest(core.intake.DESIGN),
        implementation_sha256={p: digest(ROOT / p) for p in files},
        sources={str(p.resolve()): digest(p) for p in sources + probe_sources}, approval_sources=evidence,
        model=str(model), model_files=model_files, weight_sha256=weights,
        generation_config_sha256=digest(model / 'generation_config.json'),
        versions={n: version(n) for n in ['torch', 'transformers', 'numpy', 'scikit-learn']},
        free_instruction=e.FREE_INSTRUCTION, feature_convention=e.FEATURE_CONVENTION,
        runtime=dict(dtype='bfloat16', attention='sdpa', greedy=True, beams=1, use_cache=True,
            max_new_tokens=128, logits_to_keep=1, probe_feedback=False),
        fixed_layer_zero_based=28, max_training_fits=1, bootstrap_resamples=10000,
        selected_ids=[r['id'] for r in rows], review_gate=gate,
        exposed_author_acceptance_used_for_labels=False,
        residual_risks_do_not_disappear_after_CPU_preparation=True,
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


def require_shared_fit_budget(run, root=ROOT / 'runs'):
    """Do not reset this design's one-fit budget just by changing the study version/run."""
    for marker in sorted(root.glob('*/fit_attempt.json')):
        if marker.parent.resolve() == run.resolve():
            continue
        protocol = marker.parent / 'protocol.json'
        if protocol.is_file():
            value = read(protocol)
            if value.get('task', '').startswith('semantic_transfer_chat_L28_'):
                require(value.get('design_sha256') != digest(core.intake.DESIGN),
                    'This frozen design already has a fit attempt in another run; do not reset the one-fit budget')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=['prepare', 'verify', 'run', 'analyze', 'verify-results'], default='prepare')
    parser.add_argument('--materials-dir', type=Path, default=MATERIALS)
    parser.add_argument('--run-dir', type=Path, default=DEFAULT)
    parser.add_argument('--approval', type=Path)
    args = parser.parse_args()
    materials, run = args.materials_dir.resolve(), args.run_dir.resolve()
    validate_locations(materials, run)
    if args.stage in ['prepare', 'verify']:
        result = prepare(materials, run, args.approval, write=args.stage == 'prepare')
        print(serialize(result[2]))
    else:
        core.require_ready(read(run / 'review_gate.json'))
        require_shared_fit_budget(run)
        rows, labels, gate, protocol, tokenizer = prepare(materials, run, args.approval, write=False)
        import evidence_experiment as e
        with e.legacy.run_lock(run):
            if args.stage == 'run':
                core.execute(run, rows, labels, gate, protocol, tokenizer)
            else:
                core.analyze(run, rows, labels, gate, protocol, tokenizer, write=args.stage == 'analyze')


if __name__ == '__main__':
    main()
