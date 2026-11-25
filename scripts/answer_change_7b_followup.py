"""User-operated, exposed-data second turn with two independent date branches."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import time

import answer_change_7b_development as first

ROOT = first.ROOT
PACK = ROOT / 'docs/review/2026-11-25-answer-change-7b-followup-v1'
RUN = ROOT / 'runs/answer-change-7b-followup-v1'
DAYS = ('2024-12-31', '2025-01-01')
LIMIT = 512


def followup(case, day):
    first.require(day in DAYS, 'unsupported date')
    event = 'work' if case.startswith('ssa-') else 'gift' if case.startswith('spouse-') else None
    first.require(event is not None, 'unsupported case')
    return f'The {event} date is {day}. Please answer the original question for that date and cite evidence IDs.'


def source_rows():
    seal = json.loads((first.RUN / 'seal.json').read_text())
    first.require(set(seal) | {'seal.json'} == {p.name for p in first.RUN.iterdir()}, 'first run file set changed')
    first.require(all(first.sha(first.RUN / n) == h for n, h in seal.items()), 'first run seal changed')
    eos = json.loads((first.MODEL / 'generation_config.json').read_text())['eos_token_id']
    eos = eos if isinstance(eos, list) else [eos]
    rows = []
    for i in range(8):
        attempt = json.loads((first.RUN / f'{i:02d}.attempt.json').read_text())
        row = json.loads((first.RUN / f'{i:02d}.record.json').read_text())
        first.require(row['id'] == attempt['task']['id'] and row['status'] == 'complete', 'first record invalid')
        first.require(row['eos_token_ids'] == eos and row['generated_token_ids'][-1] in eos, 'first EOS mismatch')
        rows.append((attempt, row))
    return rows


def make_plan(rows):
    first.require(len(rows) == 8, 'expected 8 first-turn records')
    result = []
    for attempt, row in rows:
        task = attempt['task']
        for day in DAYS:
            messages = task['messages'] + [{'role': 'assistant', 'content': row['output']},
                                           {'role': 'user', 'content': followup(task['case'], day)}]
            result.append({'id': f'{task["id"]}/{day}', 'case': task['case'], 'route': task['route'],
                           'day': day, 'kind': 'unsolicited_date', 'messages': messages,
                           'first_input_ids': attempt['input_token_ids'],
                           'first_generated_ids': row['generated_token_ids']})
    return result


def render_checked(tokenizer, task, context):
    text, ids = first.render(tokenizer, task['messages'])
    prefix = task['first_input_ids'] + task['first_generated_ids']
    first.require(ids[:len(prefix)] == prefix, 'first-turn token history mismatch')
    first.require(len(ids) + LIMIT <= context, 'context exceeded')
    return text, ids


def prepare():
    meta, _, tokenizer = first.check_prepared()
    first.verify()
    plan = make_plan(source_rows())
    lengths = {t['id']: len(render_checked(tokenizer, t, meta['context'])[1]) for t in plan}
    manifest = {'status': 'prepared_not_started', 'purpose': 'exposed unsolicited-date stress test',
                'operator': 'user', 'first_seal_sha256': first.sha(first.RUN / 'seal.json'),
                'first_manifest_sha256': first.sha(first.PACK / 'manifest.json'),
                'first_code_sha256': first.sha(Path(first.__file__)),
                'code_sha256': first.sha(Path(__file__)),
                'plan_sha256': hashlib.sha256(first.encode(plan)).hexdigest(),
                'input_tokens': lengths, 'max_new_tokens': LIMIT, 'context': meta['context'],
                'first_model_files_sha256': meta['model_sha256'], 'first_environment_versions': meta['versions']}
    PACK.mkdir(parents=True, exist_ok=True)
    first.write_new(PACK / 'plan.json', plan)
    first.write_new(PACK / 'manifest.json', manifest)
    print(json.dumps({'items': len(plan), 'input_token_range': [min(lengths.values()), max(lengths.values())],
                      'status': manifest['status']}))


def check_prepared():
    meta = json.loads((PACK / 'manifest.json').read_text())
    plan = json.loads((PACK / 'plan.json').read_text())
    first.require(meta['code_sha256'] == first.sha(Path(__file__)) and
                  meta['first_code_sha256'] == first.sha(Path(first.__file__)), 'implementation changed')
    first.require(meta['first_seal_sha256'] == first.sha(first.RUN / 'seal.json') and
                  meta['first_manifest_sha256'] == first.sha(first.PACK / 'manifest.json'), 'first run binding changed')
    old_meta, _, tokenizer = first.check_prepared()
    first.require(old_meta['model_sha256'] == meta['first_model_files_sha256'] and
                  old_meta['versions'] == meta['first_environment_versions'], 'model or environment changed')
    first.require(plan == make_plan(source_rows()) and
                  hashlib.sha256(first.encode(plan)).hexdigest() == meta['plan_sha256'], 'plan changed')
    first.require(meta['operator'] == 'user' and meta['max_new_tokens'] == LIMIT and
                  meta['context'] == old_meta['context'], 'contract changed')
    first.require({t['id']: len(render_checked(tokenizer, t, meta['context'])[1]) for t in plan}
                  == meta['input_tokens'], 'input token lengths changed')
    return meta, plan, tokenizer


def collect():
    import torch
    from transformers import AutoModelForCausalLM, GenerationConfig
    first.require(os.environ.get('ANSWER_CHANGE_USER_EXECUTED') == '1', 'user execution flag required')
    meta, plan, tokenizer = check_prepared()
    first.require(not RUN.exists(), 'run exists; preserve it for review')
    first.require(torch.cuda.is_available() and torch.cuda.device_count() == 1 and torch.cuda.is_bf16_supported(),
                  'one visible CUDA device with bf16 support required')
    free, total = torch.cuda.mem_get_info(0)
    first.require(free >= 18 * 1024**3, 'less than 18 GiB free GPU memory')
    RUN.mkdir(parents=True, mode=0o700)
    first.write_new(RUN / 'start.json', {'manifest_sha256': first.sha(PACK / 'manifest.json'),
        'started_utc': datetime.now(timezone.utc).isoformat(), 'device_name': torch.cuda.get_device_name(0),
        'free_bytes': free, 'total_bytes': total, 'visible_devices': 1})
    model = AutoModelForCausalLM.from_pretrained(str(first.MODEL), local_files_only=True,
              dtype=torch.bfloat16, device_map={'': 0}, attn_implementation='sdpa').eval()
    eos = model.generation_config.eos_token_id
    eos = eos if isinstance(eos, list) else [eos]
    expected = json.loads((first.MODEL / 'generation_config.json').read_text())['eos_token_id']
    first.require(eos == expected and all(type(x) is int for x in eos), 'model EOS differs')
    config = GenerationConfig(max_new_tokens=LIMIT, do_sample=False, num_beams=1, use_cache=True,
             eos_token_id=eos, pad_token_id=tokenizer.pad_token_id,
             bos_token_id=model.generation_config.bos_token_id)
    for i, task in enumerate(plan):
        text, ids = render_checked(tokenizer, task, meta['context'])
        first.write_new(RUN / f'{i:02d}.attempt.json', {'task': task, 'rendered_prompt': text,
                                                       'input_token_ids': ids})
        start = time.monotonic()
        x = torch.tensor([ids], dtype=torch.long, device='cuda:0')
        with torch.inference_mode():
            y = model.generate(input_ids=x, attention_mask=torch.ones_like(x), generation_config=config)
        first.require(y[0, :len(ids)].tolist() == ids, 'generation prefix mismatch')
        tokens = y[0, len(ids):].tolist()
        output = tokenizer.decode(tokens, skip_special_tokens=True)
        ended = bool(tokens) and tokens[-1] in eos
        status = 'empty' if not output.strip() else 'complete' if ended else 'truncated' if len(tokens) == LIMIT else 'unexpected_stop'
        first.write_new(RUN / f'{i:02d}.record.json', {'id': task['id'], 'output': output,
            'generated_token_ids': tokens, 'eos_token_ids': eos, 'status': status, 'seconds': time.monotonic()-start})
        print(i, task['id'], status, len(tokens), flush=True)
        first.require(status == 'complete', 'non-complete output; stop and preserve run')
    first.write_new(RUN / 'seal.json', {p.name: first.sha(p) for p in sorted(RUN.iterdir())})
    print('Development follow-up completed; preserve the run for assistant verification.')


def verify():
    meta, plan, tokenizer = check_prepared()
    seal = json.loads((RUN / 'seal.json').read_text())
    first.require(set(seal) | {'seal.json'} == {p.name for p in RUN.iterdir()}, 'run file set differs')
    first.require(all(first.sha(RUN / n) == h for n, h in seal.items()), 'run seal mismatch')
    first.require(json.loads((RUN / 'start.json').read_text())['manifest_sha256'] == first.sha(PACK / 'manifest.json'),
                  'manifest mismatch')
    eos = json.loads((first.MODEL / 'generation_config.json').read_text())['eos_token_id']
    for i, task in enumerate(plan):
        attempt = json.loads((RUN / f'{i:02d}.attempt.json').read_text())
        row = json.loads((RUN / f'{i:02d}.record.json').read_text())
        text, ids = render_checked(tokenizer, task, meta['context'])
        first.require(attempt == {'task': task, 'rendered_prompt': text, 'input_token_ids': ids}, 'attempt mismatch')
        tokens = row['generated_token_ids']
        first.require(row['id'] == task['id'] and row['eos_token_ids'] == eos and 0 < len(tokens) <= LIMIT and
                      tokens[-1] in eos and not any(t in eos for t in tokens[:-1]), 'EOS/token mismatch')
        first.require(row['output'] == tokenizer.decode(tokens, skip_special_tokens=True) and
                      row['status'] == 'complete' and bool(row['output'].strip()), 'output differs')
    print(json.dumps({'records': len(plan), 'verified': True, 'seal_sha256': first.sha(RUN / 'seal.json')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('prepare', 'check', 'collect', 'verify'))
    stage = parser.parse_args().stage
    {'prepare': prepare, 'check': lambda: (check_prepared(), print('Prepared inputs verified.')),
     'collect': collect, 'verify': verify}[stage]()
