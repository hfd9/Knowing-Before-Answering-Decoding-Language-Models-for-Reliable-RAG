"""Prepare, collect, and verify an exposed-material 7B development check.

The only live GPU action is `collect`, intended for the user to run. Existing
partial runs are never resumed or overwritten. No reference is sent to a model.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'docs/review/2026-11-25-role-assignment-holdout-v1/public.json'
PACK = ROOT / 'docs/review/2026-11-25-answer-change-7b-development-v1'
MODEL = Path('/large_disk/wf/研究代码/RAG/OpenDecoder/checkpoint/Qwen2.5-7B-Instruct')
RUN = ROOT / 'runs/answer-change-7b-development-v1'
IDS = ('ssa-S0', 'ssa-D0', 'spouse-S0', 'spouse-D0')
LIMIT = 512
SYSTEM = ('Use only the supplied excerpts and facts. Cite evidence IDs. Do not invent '
          'evidence or facts. If evidence is insufficient, say so.')
DIRECT = ('Answer the user question using the supplied evidence and possible dates. '
          'Explain and cite the evidence for your answer. If there is no unconditional '
          'unique conclusion, respond usefully as allowed by the question.')
BY_VERSION = ('First state the applicable dates, conclusion for the case, and supporting '
              'evidence IDs separately for each relevant version in the possible date '
              'range. Then compare those conclusions and answer the user question. '
              'If a version or scope is missing or unclear, say so rather than guessing.')
RESPONSE = ('If a unique answer depends on the missing event date, you may either ask '
            'for the date or provide complete date-conditional conclusions.')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def encode(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n').encode()


def write_new(path, value):
    with path.open('xb') as stream:
        stream.write(encode(value))
        stream.flush()
        os.fsync(stream.fileno())


def tasks(public):
    cases = {c['id']: c for c in public['cases']}
    require(all(x in cases for x in IDS), 'missing exposed case')
    result = []
    for case_id in IDS:
        case = cases[case_id]
        profile = public['profiles'][case['profile']]
        claims = profile['scope_claims']
        require(claims['source'] in profile['evidence'], 'scope source missing')
        require(all(c['quote'] in profile['evidence'][claims['source']] for c in claims['claims']),
                'scope quote differs from excerpt')
        evidence = '\n'.join(f'[{tag}] {text}' for tag, text in sorted(profile['evidence'].items()))
        statements = '\n'.join('- ' + c['statement'] for c in claims['claims'])
        common = (f'Question: {profile["question"]}\n\n[F1] Case facts: {case["facts"]}\n\n'
                  f'Evidence:\n{evidence}\n\n'
                  f'Author-prepared scope statements (derived from [{claims["source"]}]):\n{statements}\n\n'
                  f'{RESPONSE}')
        for route, instruction in (('direct', DIRECT), ('by_version', BY_VERSION)):
            messages = [{'role': 'system', 'content': SYSTEM},
                        {'role': 'user', 'content': common + '\n\n' + instruction}]
            result.append({'id': f'{case_id}/{route}', 'case': case_id, 'route': route,
                           'messages': messages})
    return result


def load_tokenizer():
    from transformers import AutoTokenizer
    return AutoTokenizer.from_pretrained(str(MODEL), local_files_only=True)


def render(tokenizer, messages):
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    ids = tokenizer(text, add_special_tokens=False)['input_ids']
    return text, ids


def model_files():
    index = json.loads((MODEL / 'model.safetensors.index.json').read_text())
    names = sorted(set(index['weight_map'].values()))
    require(len(names) == 4 and all(Path(n).name == n for n in names), 'unexpected 7B shards')
    names += ['config.json', 'generation_config.json', 'model.safetensors.index.json',
              'tokenizer.json', 'tokenizer_config.json']
    require(all((MODEL / name).is_file() for name in names), 'model file missing')
    return names


def prepare():
    from importlib.metadata import version
    tokenizer = load_tokenizer()
    public = json.loads(SOURCE.read_text())
    plan = tasks(public)
    context = json.loads((MODEL / 'config.json').read_text())['max_position_embeddings']
    lengths = {item['id']: len(render(tokenizer, item['messages'])[1]) for item in plan}
    require(max(lengths.values()) + LIMIT <= context, 'model context too short')
    meta = {'status': 'prepared_not_started', 'purpose': 'exposed development only',
            'model': str(MODEL), 'model_sha256': {n: sha(MODEL / n) for n in model_files()},
            'code_sha256': sha(Path(__file__)), 'source_sha256': sha(SOURCE),
            'versions': {n: version(n) for n in ('torch', 'transformers', 'tokenizers', 'accelerate', 'safetensors')},
            'limit': LIMIT, 'context': context, 'input_tokens': lengths,
            'plan_sha256': hashlib.sha256(encode(plan)).hexdigest(),
            'operator': 'user', 'gpu_inference_performed': False}
    PACK.mkdir(parents=True, exist_ok=True)
    write_new(PACK / 'plan.json', plan)
    write_new(PACK / 'manifest.json', meta)
    print(json.dumps({'items': len(plan), 'input_token_range': [min(lengths.values()), max(lengths.values())],
                      'limit': LIMIT, 'status': meta['status']}, ensure_ascii=False))


def check_prepared():
    from importlib.metadata import version
    meta = json.loads((PACK / 'manifest.json').read_text())
    plan = json.loads((PACK / 'plan.json').read_text())
    require(meta['code_sha256'] == sha(Path(__file__)) and meta['source_sha256'] == sha(SOURCE),
            'implementation or source changed')
    require(plan == tasks(json.loads(SOURCE.read_text())) and meta['plan_sha256'] == hashlib.sha256(encode(plan)).hexdigest(),
            'plan changed')
    require(meta['limit'] == LIMIT and meta['operator'] == 'user' and meta['model'] == str(MODEL), 'contract changed')
    require({n: sha(MODEL / n) for n in model_files()} == meta['model_sha256'], 'model file hash changed')
    require({n: version(n) for n in meta['versions']} == meta['versions'], 'Python dependency version changed')
    tokenizer = load_tokenizer()
    require({item['id']: len(render(tokenizer, item['messages'])[1]) for item in plan} == meta['input_tokens'],
            'rendered input length changed')
    return meta, plan, tokenizer


def collect():
    import torch
    from transformers import AutoModelForCausalLM, GenerationConfig
    require(os.environ.get('ANSWER_CHANGE_USER_EXECUTED') == '1', 'user execution flag required')
    meta, plan, tokenizer = check_prepared()
    require(not RUN.exists(), 'run exists; preserve it and ask assistant to inspect')
    require(torch.cuda.is_available() and torch.cuda.device_count() == 1 and torch.cuda.is_bf16_supported(),
            'one visible CUDA device with bf16 support required')
    free, total = torch.cuda.mem_get_info(0)
    require(free >= 18 * 1024**3, 'less than 18 GiB free GPU memory')
    RUN.mkdir(parents=True, mode=0o700)
    write_new(RUN / 'start.json', {'manifest_sha256': sha(PACK / 'manifest.json'),
                                  'started_utc': datetime.now(timezone.utc).isoformat(),
                                  'device_name': torch.cuda.get_device_name(0),
                                  'free_bytes': free, 'total_bytes': total, 'visible_devices': 1})
    model = AutoModelForCausalLM.from_pretrained(str(MODEL), local_files_only=True,
             torch_dtype=torch.bfloat16, device_map={'': 0}, attn_implementation='sdpa').eval()
    eos = model.generation_config.eos_token_id
    eos = eos if isinstance(eos, list) else [eos]
    require(all(type(e) is int for e in eos), 'bad model EOS')
    config = GenerationConfig(max_new_tokens=LIMIT, do_sample=False, num_beams=1, use_cache=True,
             eos_token_id=eos, pad_token_id=tokenizer.pad_token_id,
             bos_token_id=model.generation_config.bos_token_id)
    for index, task in enumerate(plan):
        text, ids = render(tokenizer, task['messages'])
        require(len(ids) + LIMIT <= meta['context'], 'context exceeded')
        write_new(RUN / f'{index:02d}.attempt.json', {'task': task, 'rendered_prompt': text,
                                                     'input_token_ids': ids})
        start = time.monotonic()
        x = torch.tensor([ids], dtype=torch.long, device='cuda:0')
        with torch.inference_mode():
            y = model.generate(input_ids=x, attention_mask=torch.ones_like(x), generation_config=config)
        require(y[0, :len(ids)].tolist() == ids, 'generation prefix mismatch')
        tokens = y[0, len(ids):].tolist()
        output = tokenizer.decode(tokens, skip_special_tokens=True)
        ended = bool(tokens) and tokens[-1] in eos
        status = 'empty' if not output.strip() else 'complete' if ended else 'truncated' if len(tokens) == LIMIT else 'unexpected_stop'
        write_new(RUN / f'{index:02d}.record.json', {'id': task['id'], 'output': output,
                  'generated_token_ids': tokens, 'eos_token_ids': eos, 'status': status,
                  'seconds': time.monotonic() - start})
        print(index, task['id'], status, len(tokens), flush=True)
        require(status == 'complete', 'non-complete output; stop and preserve run')
    write_new(RUN / 'seal.json', {p.name: sha(p) for p in sorted(RUN.iterdir())})
    print('Development collection completed. Preserve the run for assistant verification.')


def verify():
    meta, plan, tokenizer = check_prepared()
    seal = json.loads((RUN / 'seal.json').read_text())
    require(set(seal) | {'seal.json'} == {p.name for p in RUN.iterdir()}, 'run file set differs')
    require(all(sha(RUN / name) == digest for name, digest in seal.items()), 'run seal mismatch')
    require(json.loads((RUN / 'start.json').read_text())['manifest_sha256'] == sha(PACK / 'manifest.json'),
            'manifest mismatch')
    for index, task in enumerate(plan):
        attempt = json.loads((RUN / f'{index:02d}.attempt.json').read_text())
        row = json.loads((RUN / f'{index:02d}.record.json').read_text())
        text, ids = render(tokenizer, task['messages'])
        require(attempt == {'task': task, 'rendered_prompt': text, 'input_token_ids': ids}, 'attempt mismatch')
        tokens = row['generated_token_ids']
        require(row['id'] == task['id'] and 0 < len(tokens) <= LIMIT and
                tokens[-1] in row['eos_token_ids'] and not any(t in row['eos_token_ids'] for t in tokens[:-1]),
                'record token or EOS mismatch')
        require(row['output'] == tokenizer.decode(tokens, skip_special_tokens=True) and
                row['status'] == 'complete' and bool(row['output'].strip()), 'output differs')
    print(json.dumps({'records': len(plan), 'verified': True, 'seal_sha256': sha(RUN / 'seal.json')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('prepare', 'check', 'collect', 'verify'))
    args = parser.parse_args()
    {'prepare': prepare, 'check': lambda: (check_prepared(), print('Prepared inputs verified.')),
     'collect': collect, 'verify': verify}[args.stage]()
