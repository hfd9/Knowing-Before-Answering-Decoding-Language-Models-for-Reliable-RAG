"""Verify real CPU records and score the fixed two-case engineering check."""
from collections import Counter
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'scripts'))
import query_determinacy_shared_structured_cpu as cpu

base, contract = cpu.base, cpu.contract


def read(path):
    return json.loads(path.read_bytes())


def audit():
    folder = cpu.RUN
    seal = (folder / 'seal.json').read_bytes()
    digest = base.sha(seal)
    if digest != (folder / 'seal.sha256').read_text().strip():
        raise ValueError('seal SHA mismatch')
    state = json.loads(seal)
    manifest, public = state['manifest'], state['public']
    if (manifest != read(folder / 'manifest.json') or public != read(base.PILOT_PUBLIC)
            or manifest['public_sha256'] != base.hash_file(base.PILOT_PUBLIC)):
        raise ValueError('manifest or public input mismatch')
    for path, expected in manifest['code_sha256'].items():
        if base.hash_file(ROOT / path) != expected:
            raise ValueError(f'implementation differs: {path}')

    tokenizer = base.load_tokenizer()
    eos = manifest['environment']['eos_token_ids']
    materials = {case['id']: contract.materials(case) for case in public['cases']}
    extraction, baselines, hashes, exports = {}, {}, {}, []
    schedule = base.slots(public)
    if len(state['records']) > len(schedule):
        raise ValueError('too many records')
    for key in ('manifest.json', 'seal.json', 'seal.sha256'):
        hashes[key] = base.hash_file(folder / key)
    for i, (choice, record) in enumerate(zip(schedule, state['records'])):
        case, question, kind, branch = choice
        cid = case['id']
        spans, sources = materials[cid]
        header = {'index': i, 'case': cid, 'question': question['id'] if question else None,
                  'kind': kind, 'branch': branch}
        path = folder / f'{i:04d}.record.json'
        if record != read(path) or any(record[key] != value for key, value in header.items()):
            raise ValueError('record file or schedule differs')
        hashes[path.name] = base.hash_file(path)
        slots = ('S1', 'S2') if kind == 'direct' else extraction.get(cid)
        exported = dict(header, status=record['status'])
        if kind in ('joint', 'branch') and slots is None:
            if record != dict(header, status='skipped_extract'):
                raise ValueError('missing extraction should skip downstream')
        else:
            if kind == 'branch':
                slots = (slots[branch],)
            if kind == 'extract':
                slots = ()
            prompt = contract.prompt(kind, case, question, slots, spans, sources)
            path = folder / f'{i:04d}.attempt.json'
            if read(path) != dict(header, prompt=prompt, source_slots=list(slots)):
                raise ValueError('attempt does not match public material and input binding')
            hashes[path.name] = base.hash_file(path)
            rendered, ids = base.tokenize(tokenizer, prompt)
            gen = record['generated_token_ids']
            raw = tokenizer.decode(gen, skip_special_tokens=True)
            status = base.output_status(raw, gen, eos)
            if (record['source_slots'] != list(slots) or record['prompt'] != prompt
                    or record['rendered_prompt'] != rendered or record['input_token_ids'] != ids
                    or record['output'] != raw or record['status'] != status or any(t in eos for t in gen[:-1])):
                raise ValueError('real token/prompt decode mismatch')
            exported.update(output=raw, input_tokens=len(ids), output_tokens=len(gen),
                            eos=bool(gen and gen[-1] in eos), seconds=record['elapsed_seconds'])
            if status == 'complete' and kind == 'extract':
                result = contract.extract_candidates(raw, case['domain'])
                bound = contract.bind(result['values'], sources)
                if record['extraction'] != result or record['bound_source_slots'] != (list(bound) if bound else None):
                    raise ValueError('extraction differs')
                extraction[cid] = bound
                exported.update(extraction=result, bound_source_slots=bound)
                if case['domain'] == 'integer':
                    baselines[cid] = {}
                    for q in case['questions']:
                        selected = contract.numeric_comparison(q['text'], bound, sources)
                        baselines[cid][q['id']] = contract.ensure_worlds(selected, sources) if selected is not None else None
            elif status == 'complete':
                accepted = contract.responses(slots, tuple(spans))
                canonical = tokenizer(raw, add_special_tokens=False)['input_ids']
                if (raw not in accepted or gen[:-1] != canonical
                        or record['worlds'] != contract.ensure_worlds(accepted[raw], sources)):
                    raise ValueError('constrained output differs')
                exported['worlds'] = record['worlds']
        exports.append(exported)

    if state['numeric_baseline'] != baselines:
        raise ValueError('numeric baseline differs')
    # References are connected only after reconstructing actual outputs and baseline.
    ref_raw = cpu.REFERENCE.read_bytes()
    if base.sha(ref_raw) != manifest['reference_sha256']:
        raise ValueError('reference SHA mismatch')
    reference = json.loads(ref_raw)['cases']
    reports, totals = [], {}
    for method in ('direct', 'joint', 'branch', 'numeric_baseline'):
        totals[method] = Counter(planned=0, readable=0, resolved=0, final_correct=0, worlds_correct=0,
                                 correct_and_supported=0, unsupported_split_choice=0)
    for case in public['cases']:
        cid = case['id']
        ref = reference[cid]
        spans, _ = materials[cid]
        expected_ids = {w['value']: {key for key, span in spans.items()
                                     if span['text'] in (w['source_quote'], w.get('rule_quote'))} for w in ref['worlds']}
        if any(len(labels) != (2 if case['domain'] == 'identifier' else 1) for labels in expected_ids.values()):
            raise ValueError('author evidence does not uniquely match public spans')
        for question in case['questions']:
            qid = question['id']
            qref = ref['questions'][qid]
            values = {world['value']: label for world, label in zip(ref['worlds'], qref['world_answers'])}
            report = {'case': cid, 'question': qid, 'reference': qref, 'methods': {}}
            for method, count in totals.items():
                if method == 'numeric_baseline':
                    if case['domain'] != 'integer':
                        continue
                    worlds = baselines.get(cid, {}).get(qid)
                    readable = worlds is not None
                else:
                    relevant = [row for row in exports if row['case'] == cid and row['question'] == qid and row['kind'] == method]
                    worlds = [world for row in relevant for world in row.get('worlds', ())]
                    readable = len(worlds) == 2
                final = contract.final(worlds) if readable else None
                checked = []
                for world in worlds or ():
                    value = world['value']
                    correct = world['answer'] == values[value]
                    evidence = 'supports' if correct else 'contradicts'
                    if set(world['evidence_ids']) != expected_ids[value]:
                        evidence = 'missing_or_wrong'
                    checked.append(dict(world, correct=correct, evidence_status=evidence))
                worlds_correct = readable and all(w['correct'] for w in checked)
                supported = bool(worlds_correct and final == qref['final'] and all(w['evidence_status'] == 'supports' for w in checked))
                split = qref['final'] == 'U' and final in ('Y', 'N')
                report['methods'][method] = {'readable': readable, 'final': final, 'worlds': checked,
                                             'correct_and_supported': supported, 'unsupported_split_choice': split}
                count.update(planned=1, readable=int(readable), resolved=int(final is not None),
                             final_correct=int(final == qref['final']), worlds_correct=int(worlds_correct),
                             correct_and_supported=int(supported), unsupported_split_choice=int(split))
            reports.append(report)
    return {'seal_sha256': digest, 'source_sha256': hashes,
            'slot_counts': Counter(row['status'] for row in exports),
            'model_calls': sum('output' in row for row in exports),
            'call_seconds': sum(row.get('seconds', 0) for row in exports),
            'totals': totals, 'questions': reports, 'records': exports}


if __name__ == '__main__':
    print(json.dumps(audit(), ensure_ascii=False, sort_keys=True, indent=2))
