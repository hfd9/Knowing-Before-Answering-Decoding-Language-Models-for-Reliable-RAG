"""CPU-only, real-model check of the constrained two-case interface."""
import argparse
import json
from pathlib import Path
import time

import query_determinacy_shared_live as base
import query_determinacy_shared_structured as contract

ROOT = base.ROOT
RUN = ROOT / 'runs/qwen2.5-3b-query-determinacy-structured-cpu-v1'
REFERENCE = base.PILOT_PUBLIC.with_name('reference.json')
EXTRACT_LIMIT = 64


class CpuModel:
    def __init__(self, threads, eos):
        import torch
        from transformers import AutoModelForCausalLM, GenerationConfig

        torch.set_num_threads(threads)
        self.torch = torch
        self.config_class = GenerationConfig
        self.eos = eos
        self.tokenizer = base.load_tokenizer()
        self.model = AutoModelForCausalLM.from_pretrained(
            str(base.MODEL), local_files_only=True, dtype=torch.float32,
            device_map={'': 'cpu'}, attn_implementation='sdpa').eval()
        self.model.requires_grad_(False)
        self.grammars = {}

    def __call__(self, prompt, slots, evidence_ids):
        rendered, ids = base.tokenize(self.tokenizer, prompt)
        args = {}
        finish_limit = EXTRACT_LIMIT
        if slots:
            key = slots, evidence_ids
            if key not in self.grammars:
                self.grammars[key] = contract.token_prefixes(
                    self.tokenizer, contract.responses(*key), self.eos)
            prefixes = self.grammars[key]
            finish_limit = max(map(len, prefixes)) + 1

            def allowed_tokens(_batch, tokens):
                return prefixes[tuple(tokens[len(ids):].tolist())]

            args['prefix_allowed_tokens_fn'] = allowed_tokens
        if len(ids) + finish_limit > self.model.config.max_position_embeddings:
            raise ValueError('prompt exceeds model context')
        cfg = self.config_class(max_new_tokens=finish_limit, do_sample=False, num_beams=1,
                                use_cache=True, eos_token_id=self.eos,
                                pad_token_id=self.tokenizer.pad_token_id,
                                bos_token_id=self.model.generation_config.bos_token_id)
        x = self.torch.tensor([ids], dtype=self.torch.long, device='cpu')
        started = time.monotonic()
        with self.torch.inference_mode():
            generated = self.model.generate(input_ids=x, attention_mask=self.torch.ones_like(x),
                                            generation_config=cfg, logits_to_keep=1, **args)
        if generated[0, :len(ids)].tolist() != ids:
            raise ValueError('model changed input prefix')
        tokens = generated[0, len(ids):].tolist()
        raw = self.tokenizer.decode(tokens, skip_special_tokens=True)
        return {'prompt': prompt, 'rendered_prompt': rendered, 'input_token_ids': ids, 'generated_token_ids': tokens,
                'output': raw, 'status': base.output_status(raw, tokens, self.eos),
                'elapsed_seconds': time.monotonic() - started}


def collect(path, threads):
    if threads < 1:
        raise ValueError('threads must be positive')
    raw = base.PILOT_PUBLIC.read_bytes()
    public = json.loads(raw)
    if [case['id'] for case in base.validate_public(public)] != base.PILOT_CASES:
        raise ValueError('expected the two known engineering cases')
    old_release = json.loads(base.RELEASE.read_bytes())
    if base.sha(raw) != old_release['files_sha256'][str(base.PILOT_PUBLIC.relative_to(ROOT))]:
        raise ValueError('two-case public input differs from prior release')
    environment = base.environment_snapshot()
    if environment != old_release['environment']:
        raise ValueError('model or package environment differs from the previous pilot')
    inputs = {case['id']: contract.materials(case) for case in public['cases']}
    path.mkdir(mode=0o700)
    dependencies = (Path(__file__), Path(contract.__file__), Path(contract.lines.__file__),
                    Path(contract.lines.extract.__file__), Path(base.__file__))
    manifest = {'schema': 'structured_cpu_engineering_v1', 'environment': environment, 'device': 'cpu',
                'dtype': 'float32', 'threads': threads, 'slots': len(base.slots(public)),
                'public_sha256': base.sha(raw), 'reference_sha256': old_release['scoring_reference_sha256'],
                'code_sha256': {str(p.resolve().relative_to(ROOT)): base.hash_file(p) for p in dependencies}}
    base.write_new(path / 'manifest.json', base.encode(manifest))
    backend = CpuModel(threads, environment['eos_token_ids'])
    records, extracted, baselines = [], {}, {}
    for i, (case, question, kind, branch) in enumerate(base.slots(public)):
        cid = case['id']
        spans, sources = inputs[cid]
        slots = ('S1', 'S2') if kind == 'direct' else extracted.get(cid)
        evidence_ids = tuple(spans)
        record = {'index': i, 'case': cid, 'question': question['id'] if question else None,
                  'kind': kind, 'branch': branch}
        if kind in ('joint', 'branch') and slots is None:
            record['status'] = 'skipped_extract'
        else:
            if kind == 'branch':
                slots = (slots[branch],)
            if kind == 'extract':
                slots = ()
            prompt = contract.prompt(kind, case, question, slots, spans, sources)
            base.write_new(path / f'{i:04d}.attempt.json', base.encode(dict(record, prompt=prompt, source_slots=slots)))
            record.update(backend(prompt, slots, evidence_ids))
            record['source_slots'] = slots
            if record['status'] == 'complete':
                if kind == 'extract':
                    candidate = contract.extract_candidates(record['output'], case['domain'])
                    extracted[cid] = contract.bind(candidate['values'], sources)
                    record.update(extraction=candidate, bound_source_slots=extracted[cid])
                    if case['domain'] == 'integer':
                        baselines[cid] = {}
                        for q in case['questions']:
                            selected = contract.numeric_comparison(q['text'], extracted[cid], sources)
                            baselines[cid][q['id']] = contract.ensure_worlds(selected, sources) if selected is not None else None
                else:
                    selected = contract.responses(slots, evidence_ids)[record['output']]
                    record['worlds'] = contract.ensure_worlds(selected, sources)
        base.write_new(path / f'{i:04d}.record.json', base.encode(record))
        records.append(record)
        print(f'{i+1}/{manifest["slots"]} {cid} {kind} {record["status"]}', flush=True)
        if record['status'] not in ('complete', 'skipped_extract'):
            break
    snapshot = {'manifest': manifest, 'public': public, 'records': records, 'numeric_baseline': baselines}
    encoded = base.encode(snapshot)
    base.write_new(path / 'seal.json', encoded)
    digest = base.sha(encoded)
    base.write_new(path / 'seal.sha256', (digest + '\n').encode())
    return digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--threads', type=int, default=12)
    args = parser.parse_args()
    print(collect(RUN, args.threads))


if __name__ == '__main__':
    main()
