"""Prepare and collect pre-specified 7B first turns on two authored rules.

This is development, not a legal gold standard or a held-out confirmation set.
GPU `collect` is intended for the user. Preserve every partial run.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import time

import answer_change_7b_development as base

ROOT = base.ROOT
DESIGN = ROOT / 'docs/review/2026-11-26-new-rule-development-protocol-v1'
MATERIAL = ROOT / 'docs/review/2026-11-26-new-rule-materials-v1'
PACK = ROOT / 'docs/review/2026-11-26-two-rule-7b-first-v1'
RUN = ROOT / 'runs/answer-change-two-rule-7b-first-v1'
LIMIT = 768
SOURCES = (DESIGN / 'protocol.md', DESIGN / 'protocol.json', MATERIAL / 'rules.json',
           MATERIAL / 'public.json', MATERIAL / 'reference.json', MATERIAL / 'build.py',
           Path(__file__), Path(base.__file__))


def load(path):
    return json.loads(path.read_text())


def build_plan(protocol, public):
    base.require(protocol['max_new_tokens'] == LIMIT and not protocol['do_sample'] and
                 protocol['routes'] == ['direct', 'by_version'], 'protocol mismatch')
    base.require(len(public['cases']) == 12, 'wrong case count')
    ids = set()
    result = []
    for case in public['cases']:
        base.require(case['id'] not in ids, 'duplicate case')
        ids.add(case['id'])
        snippets = '\n'.join(f'[{e["id"]}] Official-source excerpt: "{e["excerpt"]}"'
                             for e in case['evidence'])
        snippets += '\n\n' + case['metadata']
        common = protocol['common'].format(question=case['question'],
            facts_and_date_status=case['facts_and_date_status'], old_date=case['old_date'],
            new_date=case['new_date'], source_excerpts_and_explicitly_attributed_metadata=snippets)
        for route in protocol['routes']:
            result.append({'id': f'{case["id"]}/{route}', 'case': case['id'], 'route': route,
                           'messages': [{'role': 'system', 'content': protocol['system']},
                                        {'role': 'user', 'content': common + '\n\n' + protocol[route]}]})
    base.require(len(result) == protocol['max_first_turn_calls'] == 24, 'wrong task count')
    return result


def prepare():
    old_meta, _, tokenizer = base.check_prepared()
    protocol, public = load(DESIGN / 'protocol.json'), load(MATERIAL / 'public.json')
    base.require(protocol['new_rule_collection_release'] is False and protocol['old_gate_changed'] is False,
                 'prior protocol gate changed')
    plan = build_plan(protocol, public)
    context = old_meta['context']
    lengths = {t['id']: len(base.render(tokenizer, t['messages'])[1]) for t in plan}
    base.require(max(lengths.values()) + LIMIT <= context, 'model context too short')
    manifest = {'status': 'prepared_not_started', 'purpose': 'author_informed_development',
        'operator': 'user', 'prior_design_not_a_collection_release': True,
        'model': str(base.MODEL), 'model_sha256': old_meta['model_sha256'],
        'versions': old_meta['versions'], 'context': context, 'limit': LIMIT,
        'sources_sha256': {str(p.relative_to(ROOT)): base.sha(p) for p in SOURCES},
        'plan_sha256': hashlib.sha256(base.encode(plan)).hexdigest(), 'input_tokens': lengths,
        'independent_legal_review': False, 'gpu_inference_performed': False}
    PACK.mkdir(parents=True, exist_ok=True)
    base.write_new(PACK / 'plan.json', plan)
    base.write_new(PACK / 'manifest.json', manifest)
    print(json.dumps({'items': len(plan), 'input_token_range': [min(lengths.values()), max(lengths.values())],
                      'status': manifest['status']}))


def check_prepared():
    manifest, plan = load(PACK / 'manifest.json'), load(PACK / 'plan.json')
    base.require(manifest['sources_sha256'] == {str(p.relative_to(ROOT)): base.sha(p) for p in SOURCES},
                 'source, protocol, material or implementation changed')
    old_meta, _, tokenizer = base.check_prepared()
    base.require(manifest['model_sha256'] == old_meta['model_sha256'] and
                 manifest['versions'] == old_meta['versions'] and manifest['model'] == str(base.MODEL),
                 'model or environment mismatch')
    base.require(manifest['operator'] == 'user' and manifest['limit'] == LIMIT and
                 manifest['context'] == old_meta['context'] and manifest['independent_legal_review'] is False,
                 'contract mismatch')
    expected = build_plan(load(DESIGN / 'protocol.json'), load(MATERIAL / 'public.json'))
    base.require(plan == expected and manifest['plan_sha256'] == hashlib.sha256(base.encode(plan)).hexdigest(),
                 'plan mismatch')
    lengths = {t['id']: len(base.render(tokenizer, t['messages'])[1]) for t in plan}
    base.require(lengths == manifest['input_tokens'] and max(lengths.values()) + LIMIT <= manifest['context'],
                 'token lengths or context differ')
    return manifest, plan, tokenizer


def collect():
    import torch
    from transformers import AutoModelForCausalLM, GenerationConfig
    base.require(os.environ.get('ANSWER_CHANGE_USER_EXECUTED') == '1', 'user execution flag required')
    manifest, plan, tokenizer = check_prepared()
    base.require(not RUN.exists(), 'run exists; preserve for review')
    base.require(torch.cuda.is_available() and torch.cuda.device_count() == 1 and torch.cuda.is_bf16_supported(),
                 'one visible CUDA device with bf16 support required')
    free, total = torch.cuda.mem_get_info(0)
    base.require(free >= 18 * 1024**3, 'less than 18 GiB free GPU memory')
    RUN.mkdir(parents=True, mode=0o700)
    base.write_new(RUN / 'start.json', {'manifest_sha256': base.sha(PACK / 'manifest.json'),
        'started_utc': datetime.now(timezone.utc).isoformat(), 'device_name': torch.cuda.get_device_name(0),
        'free_bytes': free, 'total_bytes': total, 'visible_devices': 1})
    model = AutoModelForCausalLM.from_pretrained(str(base.MODEL), local_files_only=True,
             dtype=torch.bfloat16, device_map={'': 0}, attn_implementation='sdpa').eval()
    eos = model.generation_config.eos_token_id
    eos = eos if isinstance(eos, list) else [eos]
    expected = load(base.MODEL / 'generation_config.json')['eos_token_id']
    base.require(eos == expected and all(type(x) is int for x in eos), 'model EOS differs')
    config = GenerationConfig(max_new_tokens=LIMIT, do_sample=False, num_beams=1, use_cache=True,
             eos_token_id=eos, pad_token_id=tokenizer.pad_token_id,
             bos_token_id=model.generation_config.bos_token_id)
    for i, task in enumerate(plan):
        text, ids = base.render(tokenizer, task['messages'])
        base.require(len(ids) + LIMIT <= manifest['context'], 'context exceeded')
        base.write_new(RUN / f'{i:02d}.attempt.json', {'task': task, 'rendered_prompt': text,
                                                        'input_token_ids': ids})
        start = time.monotonic()
        x = torch.tensor([ids], dtype=torch.long, device='cuda:0')
        with torch.inference_mode():
            y = model.generate(input_ids=x, attention_mask=torch.ones_like(x), generation_config=config)
        base.require(y[0, :len(ids)].tolist() == ids, 'generation prefix mismatch')
        tokens = y[0, len(ids):].tolist()
        output = tokenizer.decode(tokens, skip_special_tokens=True)
        ended = bool(tokens) and tokens[-1] in eos
        status = 'empty' if not output.strip() else 'complete' if ended else 'truncated' if len(tokens) == LIMIT else 'unexpected_stop'
        base.write_new(RUN / f'{i:02d}.record.json', {'id': task['id'], 'output': output,
            'generated_token_ids': tokens, 'eos_token_ids': eos, 'status': status, 'seconds': time.monotonic()-start})
        print(i, task['id'], status, len(tokens), flush=True)
        base.require(status == 'complete', 'non-complete output; stop and preserve run')
    base.write_new(RUN / 'seal.json', {p.name: base.sha(p) for p in sorted(RUN.iterdir())})
    print('Development first turn completed; preserve the run for assistant verification.')


def verify():
    _, plan, tokenizer = check_prepared()
    seal = load(RUN / 'seal.json')
    base.require(set(seal) | {'seal.json'} == {p.name for p in RUN.iterdir()}, 'run file set differs')
    base.require(all(base.sha(RUN / n) == h for n, h in seal.items()), 'run seal mismatch')
    base.require(load(RUN / 'start.json')['manifest_sha256'] == base.sha(PACK / 'manifest.json'), 'manifest mismatch')
    eos = load(base.MODEL / 'generation_config.json')['eos_token_id']
    for i, task in enumerate(plan):
        attempt, row = load(RUN / f'{i:02d}.attempt.json'), load(RUN / f'{i:02d}.record.json')
        text, ids = base.render(tokenizer, task['messages'])
        base.require(attempt == {'task': task, 'rendered_prompt': text, 'input_token_ids': ids}, 'attempt mismatch')
        tokens = row['generated_token_ids']
        base.require(row['id'] == task['id'] and row['eos_token_ids'] == eos and 0 < len(tokens) <= LIMIT and
                     tokens[-1] in eos and not any(t in eos for t in tokens[:-1]), 'EOS/token mismatch')
        base.require(row['output'] == tokenizer.decode(tokens, skip_special_tokens=True) and
                     row['status'] == 'complete' and bool(row['output'].strip()), 'output differs')
    print(json.dumps({'records': len(plan), 'verified': True, 'seal_sha256': base.sha(RUN / 'seal.json')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('prepare', 'check', 'collect', 'verify'))
    stage = parser.parse_args().stage
    {'prepare': prepare, 'check': lambda: (check_prepared(), print('Prepared inputs verified.')),
     'collect': collect, 'verify': verify}[stage]()
