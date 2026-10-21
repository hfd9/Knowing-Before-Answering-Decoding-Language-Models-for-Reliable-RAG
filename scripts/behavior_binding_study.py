"""Fixed 12-scenario synthetic behavior study: CPU prepare and strict one-answer collection."""

import argparse
from collections import Counter
from datetime import datetime, timezone
from importlib.metadata import version
import hashlib
from itertools import permutations
import json
import math
from pathlib import Path
import random
import time

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / 'runs/qwen2.5-3b-behavior-binding-v1'
SPEC = ROOT / 'prompts/behavior_binding_materials_v1.json'
DESIGN = ROOT / 'prompts/behavior_binding_followup_design_v1.json'
REVIEW = ROOT / 'prompts/behavior_binding_author_review_v1.json'
RUBRIC = ROOT / 'prompts/behavior_binding_scoring_v1.json'
MODEL_REFERENCE = ROOT / 'runs/qwen2.5-3b-semantic-transfer-exploratory-v5-v1/protocol.json'
FIELDS = ['has_substantive_target_answer', 'adopts_cell_distractor_value',
          'supported_target_answer', 'acknowledges_insufficiency', 'claimed_evidence_supports_target']


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text())


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(2**20), b''):
            h.update(block)
    return h.hexdigest()


def save(path, value, immutable=False, verify=False):
    path = Path(path)
    data = encoded(value)
    if verify or (immutable and path.exists()):
        require(path.exists() and path.read_bytes() == data, 'Frozen artifact mismatch: ' + str(path))
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_bytes(data)
    temporary.replace(path)


def make_materials(spec=None):
    spec = read(SPEC) if spec is None else spec
    require(spec['seed'] == 42 and spec['base_scenarios'] == 12
            and spec['maximum_generations'] == 48 and spec['new_probe_fits'] == 0
            and spec['max_new_tokens'] == 128 and spec['review_fields'] == FIELDS, 'Material scope changed')
    rng = random.Random(spec['seed'])
    units = [f'U-{n}' for n in rng.sample(range(100, 1000), 24)]
    codes = [f'K-{n}' for n in rng.sample(range(10000, 100000), 36)]
    roles = list(permutations(range(3))) * 2
    rows, witnesses = [], {}
    for index, slots in enumerate(spec['target_distractor_slots_one_based']):
        target, distractor = units[index * 2:index * 2 + 2]
        candidates = sorted(codes[index * 3:index * 3 + 3])
        t, v1, v2 = [candidates[k] for k in roles[index]]
        question = spec['question_template'].format(target=target)
        for cell in spec['cells']:
            support, variant = cell.split('_')
            active = dict(v1=v1, v2=v2)[variant]
            docs = [None] * 5
            target_text = (spec['relation_sentence'].format(entity=target, value=t) if support == 'S'
                           else spec['absent_target_sentence'].format(target=target))
            docs[slots[0] - 1] = target_text
            docs[slots[1] - 1] = spec['relation_sentence'].format(entity=distractor, value=active)
            backgrounds = iter(s.format(target=target, distractor=distractor)
                               for s in spec['background_sentences'])
            docs = [next(backgrounds) if d is None else d for d in docs]
            key = f'bind{index + 1:02d}_{cell}'
            rows.append(dict(id=key, original_id=f'bind{index + 1:02d}', condition=support,
                variant=variant, question=question, docs=docs, target_entity=target,
                distractor_entity=distractor, target_value=t, distractor_value=active,
                v1=v1, v2=v2, target_slot=slots[0], distractor_slot=slots[1],
                role_permutation=list(roles[index]), fictional=True))
            if support == 'I':
                alternative = v2 if variant == 'v1' else v1
                witnesses[key] = dict(input_sha256=sha(json.dumps(dict(question=question, docs=docs), sort_keys=True)),
                    worlds=[dict(assignments={target: value, distractor: active},
                        preserved_documents=docs, added_target_fact=spec['relation_sentence'].format(
                            entity=target, value=value)) for value in [t, alternative]])
    validate_materials(rows, witnesses, spec)
    return rows, witnesses


def validate_materials(rows, witnesses, spec):
    require(len(rows) == len({r['id'] for r in rows}) == 48, 'Expected 48 unique inputs')
    require(len({r['original_id'] for r in rows}) == 12 and len(witnesses) == 24, 'Wrong base/witness count')
    require(len(set(spec['smoke_prefix_ids'])) == 4
            and set(spec['smoke_prefix_ids']) <= {r['id'] for r in rows}, 'Invalid smoke prefix')
    by_id = {r['id']: r for r in rows}
    for row in rows:
        require(len(row['docs']) == 5 and all(type(d) is str and d for d in row['docs']), 'Invalid documents')
        values = [row['target_value'], row['v1'], row['v2']]
        require(len(set(values)) == 3 and not any(a in b for a in values for b in values if a != b),
                'Value collision')
        require(row['target_entity'] != row['distractor_entity']
                and row['target_slot'] != row['distractor_slot'], 'Entity/slot collision')
        require(not any(value in row['question'] for value in values), 'Question leaks answer value')
        required_target = (spec['relation_sentence'].format(entity=row['target_entity'], value=row['target_value'])
            if row['condition'] == 'S' else spec['absent_target_sentence'].format(target=row['target_entity']))
        require(row['docs'][row['target_slot'] - 1] == required_target, 'Wrong target record')
        require(row['docs'][row['distractor_slot'] - 1] == spec['relation_sentence'].format(
            entity=row['distractor_entity'], value=row['distractor_value']), 'Wrong distractor record')
        for index, doc in enumerate(row['docs'], 1):
            if index not in [row['target_slot'], row['distractor_slot']]:
                require(not any(value in doc for value in values), 'Background leaks attribute value')
        if row['condition'] == 'I':
            require(row['target_value'] not in '\n'.join(row['docs']), 'Missing-relation value leaked')
            other = by_id[row['id'].replace('_I_', '_S_')]
            require(row['question'] == other['question'] and [i + 1 for i, (a, b) in enumerate(
                zip(row['docs'], other['docs'])) if a != b] == [row['target_slot']], 'S/I multi-slot change')
            witness = witnesses[row['id']]
            require(witness['input_sha256'] == sha(json.dumps(dict(question=row['question'], docs=row['docs']),
                    sort_keys=True)), 'Witness binds wrong packet')
            worlds = witness['worlds']
            require(len(worlds) == 2 and len({w['assignments'][row['target_entity']] for w in worlds}) == 2,
                    'Witness does not establish non-uniqueness')
            for world in worlds:
                require(world['preserved_documents'] == row['docs'] and world['assignments'][
                    row['distractor_entity']] == row['distractor_value'], 'Witness changes provided fact')
                require(world['added_target_fact'] == spec['relation_sentence'].format(
                    entity=row['target_entity'], value=world['assignments'][row['target_entity']]),
                    'Witness target assignment/text mismatch')
        if row['variant'] == 'v1':
            other = by_id[row['id'][:-1] + '2']
            require([i + 1 for i, (a, b) in enumerate(zip(row['docs'], other['docs'])) if a != b]
                    == [row['distractor_slot']], 'Distractor edit changes other slot')
    scenarios = [r for r in rows if r['condition'] == 'S' and r['variant'] == 'v1']
    require(Counter(tuple(r['role_permutation']) for r in scenarios) == Counter({p: 2 for p in permutations(range(3))}),
            'Unbalanced code roles')
    require(sum(r['target_slot'] < r['distractor_slot'] for r in scenarios) == 6, 'Unbalanced record order')


def ordered_rows(rows, spec):
    by_id = {r['id']: r for r in rows}
    prefix = spec['smoke_prefix_ids']
    return [by_id[key] for key in prefix] + sorted((r for r in rows if r['id'] not in prefix),
        key=lambda r: sha('behavior-binding-order-v1|' + r['id']))


def runtime():
    import evidence_experiment as e
    from transformers import AutoTokenizer
    reference = read(MODEL_REFERENCE)
    model = Path(reference['model'])
    require(model.name == 'Qwen2.5-3B-Instruct', 'Wrong backbone')
    expected = {**reference['model_files'], **reference['weight_sha256']}
    actual = {name: digest(model / name) for name in expected}
    require(actual == expected, 'Backbone/tokenizer fingerprint differs from saved model')
    actual['generation_config.json'] = digest(model / 'generation_config.json')
    tokenizer = AutoTokenizer.from_pretrained(str(model), local_files_only=True)
    return e, tokenizer, dict(model=str(model), model_files_sha256=actual,
        runtime_versions={n: version(n) for n in ['torch', 'transformers', 'numpy']},
        context_tokens=read(model / 'config.json')['max_position_embeddings'])


def renderer_inputs(row):
    # Only these fields reach the shared renderer; expected values/witnesses remain coordinator data.
    return dict(question=row['question'], docs=row['docs'])


def validate_location(run):
    require(run.resolve() == DEFAULT.resolve(), 'This fixed collection uses only its dedicated run directory')


def prepare(run=DEFAULT, write=False):
    validate_location(run)
    spec = read(SPEC)
    rows, witnesses = make_materials(spec)
    review = read(REVIEW)
    require(review['history_exposed'] is True and review['independent_gold'] is False
            and review['materials_sha256'] == sha(encoded(rows).decode())
            and review['reviewed_ids'] == [r['id'] for r in rows], 'Author review missing or mismatched')
    e, tokenizer, model_info = runtime()
    ordered = ordered_rows(rows, spec)
    preflight_rows = []
    for row in ordered:
        rendered = e.render_input(renderer_inputs(row), 'free_answer', 'chat', tokenizer)
        tokens = e.encode(tokenizer, rendered, 'chat')['input_ids']
        require(len(tokens) + 128 <= model_info['context_tokens'], 'Context overflow')
        if row['condition'] == 'I':
            require(row['target_value'] not in rendered, 'Rendered prompt leaks missing target value')
        require(not any(marker in rendered for marker in [row['id'], 'role_permutation', 'assignments']),
                'Coordinator metadata leaked into prompt')
        preflight_rows.append(dict(id=row['id'], input_tokens=len(tokens), prompt_sha256=sha(rendered),
                                   input_token_ids_sha256=sha(json.dumps(tokens))))
    files = ['scripts/behavior_binding_study.py', 'scripts/run_behavior_binding_study.sh',
        'tests/test_behavior_binding_study.py', 'scripts/evidence_experiment.py',
        'scripts/small_repro.py', 'scripts/prompt_baseline.py', 'scripts/analyze_prompt_baseline.py',
        'scripts/classification_semantic_baseline.py', 'scripts/classification_prompt_search.py',
        'code/prompts.py', 'prompts/prompt_robustness_P0_P5.json', 'configs/local.env']
    sources = [SPEC, DESIGN, REVIEW, RUBRIC, MODEL_REFERENCE]
    protocol = dict(task='fictional_entity_attribute_binding_v1', **model_info,
        material_spec_sha256=digest(SPEC), design_sha256=digest(DESIGN),
        instruction=e.FREE_INSTRUCTION, format='chat', do_sample=False, num_beams=1,
        use_cache=True, logits_to_keep=1, max_new_tokens=128,
        total_generation_budget=48, extra_smoke_generations=0, new_probe_fits=0,
        no_probe_feedback=True, no_hidden_state_collection=True, independent_semantic_approval=False,
        author_review_history_exposed=True, original_formal_gate_changed=False,
        ordered_ids=[r['id'] for r in ordered], smoke_prefix_ids=spec['smoke_prefix_ids'],
        implementation_sha256={p: digest(ROOT / p) for p in files},
        source_sha256={str(p.relative_to(ROOT)): digest(p) for p in sources},
        scoring_rubric_sha256=digest(RUBRIC),
        eos_token_ids=read(Path(model_info['model']) / 'generation_config.json')['eos_token_id'])
    if not isinstance(protocol['eos_token_ids'], list):
        protocol['eos_token_ids'] = [protocol['eos_token_ids']]
    lengths = [r['input_tokens'] for r in preflight_rows]
    preflight = dict(status='prepared_not_started', cells=48, bases=12, smoke_cells_included=4,
        input_tokens_min=min(lengths), input_tokens_max=max(lengths), total_input_tokens=sum(lengths),
        reserved_output_tokens=48 * 128, no_model_weights_loaded=True,
        no_probe_loaded=True, no_gpu_calls=True, prompts=preflight_rows)
    plan = dict(status='prepared_for_user_launch', launch_actor='user', max_answers=48,
        semantic_independent_approval=False, synthetic_author_review_complete=True,
        ordered_ids=protocol['ordered_ids'], smoke_prefix_ids=protocol['smoke_prefix_ids'],
        new_probe_fits=0, original_fit_budget_remaining=0,
        behavior_scoring='Unreviewed; no automatic answer-value matching or behavior rates')
    for name, value in [('materials/inputs.json', rows), ('coordinator/witnesses.json', witnesses),
            ('protocol.json', protocol), ('preflight.json', preflight), ('collection_plan.json', plan)]:
        save(run / name, value, immutable=True, verify=not write)
    return ordered, protocol, tokenizer


def validate_cache(run, rows, protocol, tokenizer):
    import evidence_experiment as e
    path = run / 'predictions.json'
    ph = digest(run / 'protocol.json')
    records = []
    if path.exists():
        saved = read(path)
        require(saved['protocol_sha256'] == ph, 'Prediction protocol mismatch')
        records = saved['records']
    require(len(records) <= len(rows) == 48, 'Cache exceeds generation budget')
    attempts = sorted((run / 'generation_attempts').glob('*.json'))
    require(len(attempts) == len(records), 'Uncommitted generation attempt; stop without regeneration')
    eos = protocol['eos_token_ids']
    for index, (row, record) in enumerate(zip(rows, records)):
        require(attempts[index].name == f'{index:04d}.json' and read(attempts[index]) == dict(
            id=row['id'], protocol_sha256=ph), 'Attempt order/protocol mismatch')
        require(all(record[k] == row[k] for k in ['id', 'original_id', 'condition', 'variant']),
                'Cache order/metadata mismatch')
        prompt = e.render_input(renderer_inputs(row), 'free_answer', 'chat', tokenizer)
        input_ids = e.encode(tokenizer, prompt, 'chat')['input_ids']
        require(record['prompt_sha256'] == sha(prompt) and record['input_tokens'] == len(input_ids)
                and record['input_token_ids_sha256'] == sha(json.dumps(input_ids)), 'Cached input mismatch')
        tokens = record['generated_token_ids']
        require(isinstance(tokens, list) and 1 <= len(tokens) <= 128
                and all(type(t) is int and 0 <= t < len(tokenizer) for t in tokens), 'Invalid output tokens')
        require(not any(t in eos for t in tokens[:-1]), 'Tokens after EOS')
        raw = tokenizer.decode(tokens, skip_special_tokens=True)
        require(raw == record['raw_output'] and sha(raw) == record['raw_output_sha256'], 'Cached text mismatch')
        ended = tokens[-1] in eos
        require(record['generated_tokens'] == len(tokens) and record['ended_with_eos'] is ended
                and record['hit_output_limit'] is (len(tokens) == 128 and not ended), 'Cached stop mismatch')
        require(ended or len(tokens) == 128, 'Unexpected early termination')
        require(isinstance(record['elapsed_seconds'], (int, float)) and math.isfinite(record['elapsed_seconds'])
                and record['elapsed_seconds'] >= 0, 'Invalid timing')
    return records


def smoke_gate(run, records, verify=False):
    require(len(records) >= 4, 'Four committed smoke inputs required')
    first = records[:4]
    passed = all(r['raw_output'].strip() and r['ended_with_eos'] and not r['hit_output_limit'] for r in first)
    result = dict(status='passed' if passed else 'failed_stop', passed=passed,
        ids=[r['id'] for r in first], included_in_total48=True, extra_answers=0,
        semantic_correctness_assessed=False)
    save(run / 'smoke_gate.json', result, immutable=True, verify=verify)
    require(passed, 'Technical smoke failed; inspect saved answers, do not regenerate')


def generate(model, tokenizer, row, protocol):
    import torch
    from transformers import GenerationConfig
    import evidence_experiment as e
    prompt = e.render_input(renderer_inputs(row), 'free_answer', 'chat', tokenizer)
    encoded_input = e.encode(tokenizer, prompt, 'chat', return_tensors='pt').to(model.device)
    input_ids = encoded_input.input_ids[0].tolist()
    require(len(input_ids) + 128 <= model.config.max_position_embeddings, 'Context overflow')
    cfg = GenerationConfig(max_new_tokens=128, do_sample=False, num_beams=1, use_cache=True,
        eos_token_id=protocol['eos_token_ids'], bos_token_id=model.generation_config.bos_token_id,
        pad_token_id=tokenizer.pad_token_id if tokenizer.pad_token_id is not None else tokenizer.eos_token_id)
    torch.cuda.synchronize()
    start = time.monotonic()
    with torch.inference_mode():
        result = model.generate(**encoded_input, generation_config=cfg, logits_to_keep=1)
    torch.cuda.synchronize()
    tokens = result[0, len(input_ids):].tolist()
    require(bool(tokens), 'No generated tokens')
    raw = tokenizer.decode(tokens, skip_special_tokens=True)
    ended = tokens[-1] in protocol['eos_token_ids']
    return dict(**{k: row[k] for k in ['id', 'original_id', 'condition', 'variant']},
        prompt_sha256=sha(prompt), input_tokens=len(input_ids),
        input_token_ids_sha256=sha(json.dumps(input_ids)), generated_token_ids=tokens,
        generated_tokens=len(tokens), raw_output=raw, raw_output_sha256=sha(raw),
        ended_with_eos=ended, hit_output_limit=len(tokens) == 128 and not ended,
        elapsed_seconds=time.monotonic() - start, completed_at=datetime.now(timezone.utc).isoformat())


def collect(run, rows, protocol, tokenizer):
    import evidence_experiment as e
    from classification_semantic_baseline import assert_gpu_idle
    records = validate_cache(run, rows, protocol, tokenizer)
    if len(records) >= 4:
        smoke_gate(run, records)
    model = None
    try:
        for row in rows[len(records):]:
            if model is None:
                assert_gpu_idle()
                model = e.load_model(protocol['model'])
            index = len(records)
            attempt = run / f'generation_attempts/{index:04d}.json'
            require(not attempt.exists(), 'Uncommitted attempt; explicit recovery required')
            save(attempt, dict(id=row['id'], protocol_sha256=digest(run / 'protocol.json')), immutable=True)
            record = generate(model, tokenizer, row, protocol)
            records.append(record)
            save(run / 'predictions.json', dict(protocol_sha256=digest(run / 'protocol.json'), records=records))
            save(run / 'progress.json', dict(status='running', completed=len(records), planned=48,
                 last_saved_at=record['completed_at']))
            print(f'binding {len(records)}/48 {row["id"]} saved', flush=True)
            if len(records) == 4:
                validate_cache(run, rows, protocol, tokenizer)
                smoke_gate(run, records)
    except Exception as error:
        save(run / 'last_failure.json', dict(completed=len(records), error=repr(error),
            no_automatic_regeneration=True, recorded_at=datetime.now(timezone.utc).isoformat()))
        raise
    finally:
        if model is not None:
            del model
            import torch
            torch.cuda.empty_cache()


def finish(run, rows, protocol, tokenizer, verify=False):
    records = validate_cache(run, rows, protocol, tokenizer)
    require(len(records) == 48, 'Completion requires all48 cached answers')
    smoke_gate(run, records, verify=verify)
    summary = dict(status='collection_complete_behavior_unreviewed', completed=48, bases=12,
        generations=48, extra_smoke_generations=0, new_probe_fits=0, probe_loaded=False,
        independent_semantic_approval=False, input_tokens=sum(r['input_tokens'] for r in records),
        output_tokens=sum(r['generated_tokens'] for r in records),
        empty_outputs=sum(not r['raw_output'].strip() for r in records),
        ended_with_eos=sum(r['ended_with_eos'] for r in records),
        hit_output_limit=sum(r['hit_output_limit'] for r in records),
        behavior_rows_reviewed=0, primary_distractor_adoption_rate=None, S_correct_rate=None)
    by_id = {r['id']: r for r in records}
    anonymous = sorted(rows, key=lambda r: sha('binding-behavior-review-v1|' + r['id']))
    packet = dict(items=[dict(item_id=f'R{i:03d}', question=r['question'], documents=r['docs'],
        answer=by_id[r['id']]['raw_output']) for i, r in enumerate(anonymous, 1)])
    packet_path = run / 'behavior_review/packet.json'
    save(packet_path, packet, immutable=True, verify=verify)
    mapping = {r['id']: f'R{i:03d}' for i, r in enumerate(anonymous, 1)}
    template = dict(reviewer='', history_exposed=None, independent_gold=False,
        packet_sha256=digest(packet_path), ratings=[dict(item_id=r['item_id'], status='unreviewed',
        **{field: 'unknown' for field in FIELDS}, rationale='', input_citations=[], output_citations=[])
        for r in packet['items']])
    for name, value in [('coordinator/behavior_mapping.json', mapping),
            ('behavior_review/ratings_template.json', template), ('reports/collection.json', summary),
            ('completion.json', dict(status=summary['status'], protocol_sha256=digest(run / 'protocol.json'),
                predictions_sha256=digest(run / 'predictions.json'), completed=48)),
            ('progress.json', dict(status=summary['status'], completed=48, planned=48,
                last_saved_at=records[-1]['completed_at']))]:
        save(run / name, value, immutable=name != 'progress.json', verify=verify)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=['prepare', 'verify', 'run', 'finish', 'verify-results', 'all'],
                        default='verify')
    args = parser.parse_args()
    # Lock protects preparation and all mutations; verify stages remain read-only.
    import evidence_experiment as e
    if args.stage in ['verify', 'verify-results']:
        rows, protocol, tokenizer = prepare(write=False)
        result = finish(DEFAULT, rows, protocol, tokenizer, verify=True) if args.stage == 'verify-results' else dict(
            stage='verify', prepared_cells=48, generated=0 if not (DEFAULT / 'predictions.json').exists() else
                len(read(DEFAULT / 'predictions.json')['records']), no_new_gpu=True)
        print(json.dumps(result))
    else:
        with e.legacy.run_lock(DEFAULT):
            rows, protocol, tokenizer = prepare(write=args.stage == 'prepare')
            if args.stage in ['run', 'all']:
                collect(DEFAULT, rows, protocol, tokenizer)
            if args.stage in ['finish', 'all']:
                print(json.dumps(finish(DEFAULT, rows, protocol, tokenizer)))
            elif args.stage == 'prepare':
                print(json.dumps(dict(stage='prepare', cells=48, gpu_calls=0, probe_fits=0)))


if __name__ == '__main__':
    main()
