"""Val-only evidence drafts and separate explicit review; no candidate selection."""

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import html
import io
import json
import os
from pathlib import Path
import random
import time

import evidence_experiment as e
import classification_prompt_search as search

ROOT = e.PROJECT
CONFIG = ROOT / 'prompts/validation_evidence_audit_v1.json'
MODES = ['answer', 'refuse', 'conflict', 'unknown']
RATING_FIELDS = ['review_id', 'packet_sha256', 'semantic_mode', 'reason', 'reviewer',
                 'doc_id_1', 'quote_1', 'doc_id_2', 'quote_2']
DEFAULT_RUN = 'qwen2.5-3b-validation-evidence-audit-v1'
LIMITATION = ('Same-model evidence drafts are auxiliary diagnostics, not independent human gold. '
              'Verbatim citation validation checks text provenance only, not entailment or contradiction. '
              'No prompt candidate is selected; no diagnostic test or confirmation predictions are read.')


def render(row, config, tokenizer):
    body = '\n\n'.join(f'Document {i}:\n{doc}' for i, doc in enumerate(row['docs'], 1))
    body += '\n\nQuestion: ' + row['question'] + '\n\nEvidence audit JSON:'
    return tokenizer.apply_chat_template([
        {'role': 'system', 'content': config['instruction']},
        {'role': 'user', 'content': body}], tokenize=False, add_generation_prompt=True)


def sources(args):
    path = args.reference / 'data/instances_val.jsonl'
    manifest = e.read_json(args.reference / 'data/manifest.json')['splits']['val']
    if e.repro.digest_file(path) != manifest['sha256']:
        raise ValueError('Fixed validation data hash mismatch')
    full = e.repro.load_rows(path)
    groups = e.validate_rows(full, 'val')
    if len(full) != manifest['n_instances']:
        raise ValueError('Validation count mismatch')
    spec = e.repro.feature_spec(argparse.Namespace(model=args.model, template='P0'), full, path)
    if spec != e.read_json(args.reference / 'activations/meta_P0_val.json')['spec']:
        raise ValueError('Model/validation source differs from fixed extraction')
    rows = full
    if args.limit_questions is not None:
        if not 1 <= args.limit_questions <= len(groups):
            raise ValueError('Invalid smoke question count')
        keep = set(list(groups)[:args.limit_questions])
        rows = [r for r in full if r['original_id'] in keep]
    return rows, full, spec


def prior_methods(args, full, rows, tokenizer):
    """Check the original val outputs without loading any test artifact."""
    prior_protocol = e.read_json(args.prior / 'protocol.json')
    if prior_protocol['split'] != 'val' or prior_protocol['model'] != args.model:
        raise ValueError('Expected matched validation-only previous search')
    if prior_protocol['selected_ids'] != [r['id'] for r in full]:
        raise ValueError('Prior validation population changed')
    if (prior_protocol['legacy_validation_sha256'] != e.repro.digest_file(args.baseline)
            or prior_protocol['legacy_protocol_sha256'] != e.repro.digest_file(args.baseline.parents[2]/'protocol.json')):
        raise ValueError('Legacy control differs from the frozen previous search')
    checked = {'legacy_chat8': search.baseline(args, full, tokenizer)}
    config = prior_protocol['configuration']
    if config != e.read_json(search.PROMPTS):
        raise ValueError('Previous candidate instructions changed')
    for name in config['candidate_order']:
        path = args.prior / name / 'predictions.json'
        checked[name] = search.cached(path, dict(protocol_sha256=e.repro.digest_file(args.prior/'protocol.json'),
                                                 candidate=name, split='val'), full,
                                      config['instructions'][name], tokenizer)
        if len(checked[name]) != len(full):
            raise ValueError(f'Previous method incomplete: {name}')
    selected = {}
    for name, records in checked.items():
        for row, record in zip(full, records):
            # Legacy grid records predate per-output hashes; their complete file is
            # checked against the previous search protocol above, without changing it.
            if name != 'legacy_chat8' and record['raw_output_sha256'] != e.text_hash(record['raw_output']):
                raise ValueError('Previous raw output hash mismatch')
            if record['original_id'] != row['original_id']:
                raise ValueError('Previous question ID mismatch')
        lookup = {r['id']: r for r in records}
        selected[name] = [lookup[r['id']] for r in rows]
    return selected


def protocol(args, rows, source_spec, config):
    files = [Path(__file__), CONFIG, ROOT/'scripts/run_validation_evidence_audit.sh',
             ROOT/'scripts/run_validation_evidence_audit_review.sh',
             ROOT/'scripts/classification_prompt_search.py', search.PROMPTS,
             ROOT/'scripts/evidence_experiment.py', ROOT/'scripts/small_repro.py',
             ROOT/'scripts/prompt_baseline.py', ROOT/'scripts/analyze_prompt_baseline.py',
             ROOT/'code/prompts.py']
    prior_paths = [args.prior/'protocol.json', args.baseline,
                   args.baseline.parents[2]/'protocol.json']
    prior_paths += [args.prior/n/'predictions.json' for n in e.read_json(search.PROMPTS)['candidate_order']]
    return dict(schema_version=1, task=config['task'], model=args.model, split='val',
                selected_ids=[r['id'] for r in rows], source_spec=source_spec, configuration=config,
                smoke=args.limit_questions is not None,
                code_and_prompt_sha256={str(p.relative_to(ROOT)): e.repro.digest_file(p) for p in files},
                prior_source_sha256={str(p): e.repro.digest_file(p) for p in prior_paths},
                generation_config_sha256=e.repro.digest_file(Path(args.model)/'generation_config.json'),
                runtime_versions={n: e.version(n) for n in ['torch', 'transformers', 'numpy']},
                generation=dict(dtype='bfloat16', attention='sdpa', do_sample=False, num_beams=1,
                                use_cache=True, logits_to_keep=1, max_new_tokens=config['max_new_tokens']),
                parser='strict_json_exact_schema_exact_quote_v1; invalid or truncated drafts stay unknown',
                review='seed42 shuffled IDs; blind page contains question and all five docs only; ratings start unknown',
                selection='none; diagnosis only; original candidate thresholds remain unchanged',
                limitation=LIMITATION)


def parse_draft(raw, docs, truncated=False):
    unknown = dict(status='invalid', semantic_mode='unknown', proposal=None, errors=[])
    if truncated:
        return dict(unknown, errors=['output_limit_without_eos'])
    def bad(message):
        return dict(unknown, errors=[message])
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate JSON key')
            result[key] = value
        return result
    try:
        value = json.loads(raw, object_pairs_hook=unique)
    except (ValueError, TypeError):
        return bad('invalid_json')
    required = {'semantic_mode', 'required_facts', 'missing_facts', 'reason', 'citations'}
    if not isinstance(value, dict) or set(value) != required:
        return bad('unexpected_schema')
    if value['semantic_mode'] not in MODES:
        return bad('invalid_semantic_mode')
    if any(not isinstance(value[k], str) for k in ['required_facts', 'missing_facts', 'reason']):
        return bad('text_field_type')
    if not value['reason'].strip() or not value['required_facts'].strip():
        return bad('missing_reason_or_required_facts')
    if not isinstance(value['citations'], list):
        return bad('citations_type')
    for citation in value['citations']:
        if (not isinstance(citation, dict) or set(citation) != {'doc_id', 'quote'}
                or type(citation['doc_id']) is not int or not 1 <= citation['doc_id'] <= 5
                or not isinstance(citation['quote'], str) or not citation['quote'].strip()
                or citation['quote'] not in docs[citation['doc_id']-1]):
            return bad('unverifiable_quote')
    mode = value['semantic_mode']
    if mode == 'answer' and (not value['citations'] or value['missing_facts'].strip()):
        return bad('answer_requires_citation_and_no_missing_fact')
    if mode == 'refuse' and not value['missing_facts'].strip():
        return bad('refuse_requires_missing_fact')
    if mode == 'conflict' and len({c['doc_id'] for c in value['citations']}) < 2:
        return bad('conflict_requires_two_cited_documents')
    return dict(status='valid_structure', semantic_mode=mode, proposal=value, errors=[])


def frozen_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_text(encoding='utf-8') != text:
            raise ValueError(f'Prepared review packet changed: {path}')
    else:
        path.write_text(text, encoding='utf-8')


def csv_text(rows, fields):
    out = io.StringIO(newline='')
    writer = csv.DictWriter(out, fieldnames=fields, lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


def prepare_review(args, rows, protocol_hash):
    shuffled = list(rows)
    random.Random(42).shuffle(shuffled)
    mapping = {f'V{i:04d}': row['id'] for i, row in enumerate(shuffled, 1)}
    packet = dict(protocol_sha256=protocol_hash, mapping=mapping,
                  input_sha256={key: e.text_hash(json.dumps([row['question'], row['docs']], ensure_ascii=False))
                                for key, row in zip(mapping, shuffled)})
    e.freeze(args.run_dir/'review/coordinator/packet.json', packet)
    packet_hash = e.repro.digest_file(args.run_dir/'review/coordinator/packet.json')
    template = [dict.fromkeys(RATING_FIELDS, '') for _ in shuffled]
    for rating, key in zip(template, mapping):
        rating.update(review_id=key, packet_sha256=packet_hash, semantic_mode='unknown')
    frozen_text(args.run_dir/'review/public/ratings_template.csv', csv_text(template, RATING_FIELDS))
    esc = html.escape
    sections = []
    for key, row in zip(mapping, shuffled):
        docs = ''.join(f'<details><summary>Document {i}</summary><pre>{esc(doc)}</pre></details>'
                       for i, doc in enumerate(row['docs'], 1))
        sections.append(f'<article id="{key}"><h2>{key}</h2><p>{esc(row["question"])}</p>{docs}</article>')
    page = '<!doctype html><meta charset="utf-8"><title>Validation evidence review</title>'
    page += '<style>body{max-width:1000px;margin:30px auto;font:16px sans-serif}article{border-top:1px solid #aaa;padding:20px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere}summary{cursor:pointer;padding:8px}</style>'
    page += '<h1>Validation evidence review</h1><p>Read the question and all five documents. Edit a COPY of ratings_template.csv. Do not use outside knowledge. answer: all premises supported; refuse: necessary facts missing; conflict: explicit incompatible claims about the same entity/time/property; unknown: uncertain. Record reason, reviewer, and exact quotes with document numbers. answer needs at least one quote, conflict two from distinct documents. Quote checks establish provenance only. Keep the full review population, including unknown.</p>'
    frozen_text(args.run_dir/'review/public/evidence_blind.html', page + ''.join(sections))
    return mapping, packet_hash


def load_ratings(path, mapping, packet_hash, rows):
    lookup = {r['id']: r for r in rows}
    with path.open(newline='', encoding='utf-8-sig') as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != RATING_FIELDS:
            raise ValueError('Rating columns changed')
        ratings = list(reader)
    if len(ratings) != len(mapping) or {r['review_id'] for r in ratings} != set(mapping):
        raise ValueError('Ratings must contain each review ID once, including unknown')
    result = {}
    for rating in ratings:
        if None in rating or any(v is None for v in rating.values()):
            raise ValueError('Malformed rating row')
        key = rating['review_id']
        if rating['packet_sha256'] != packet_hash or rating['semantic_mode'] not in MODES:
            raise ValueError('Rating packet/mode mismatch')
        mode = rating['semantic_mode']
        if mode != 'unknown' and (not rating['reviewer'].strip() or not rating['reason'].strip()):
            raise ValueError('Determined rating requires reviewer and reason')
        citations = []
        for n in (1, 2):
            number, quote = rating[f'doc_id_{n}'], rating[f'quote_{n}']
            if number or quote:
                if number not in {'1', '2', '3', '4', '5'} or not quote.strip():
                    raise ValueError('Rating citation is incomplete')
                if quote not in lookup[mapping[key]]['docs'][int(number)-1]:
                    raise ValueError('Rating quote is absent from cited document')
                citations.append(number)
        if mode == 'answer' and not citations:
            raise ValueError('answer rating requires supporting quote')
        if mode == 'conflict' and len(set(citations)) < 2:
            raise ValueError('conflict rating requires quotes from two documents')
        result[mapping[key]] = rating
    return result


def cached(path, spec, rows, config, tokenizer):
    if not path.exists():
        return []
    value = e.read_json(path)
    records = value['records']
    if value['spec'] != spec or len(records) > len(rows):
        raise ValueError('Checkpoint settings/count changed; use a new run_dir')
    for row, record in zip(rows, records):
        if (record['id'], record['original_id']) != (row['id'], row['original_id']):
            raise ValueError('Checkpoint identity/order mismatch')
        text = render(row, config, tokenizer)
        if record['prompt_sha256'] != e.text_hash(text) or record['raw_output_sha256'] != e.text_hash(record['raw_output']):
            raise ValueError('Checkpoint prompt/output hash mismatch')
        if type(record['generated_tokens']) is not int or not 0 <= record['generated_tokens'] <= config['max_new_tokens']:
            raise ValueError('Checkpoint output budget mismatch')
        if type(record['hit_output_limit']) is not bool or (record['hit_output_limit'] and record['generated_tokens'] != config['max_new_tokens']):
            raise ValueError('Checkpoint truncation metadata mismatch')
        if record['input_tokens'] != len(e.encode(tokenizer, text, 'chat')['input_ids']):
            raise ValueError('Checkpoint input token count mismatch')
        if record['draft'] != parse_draft(record['raw_output'], row['docs'], record['hit_output_limit']):
            raise ValueError('Checkpoint draft parsing mismatch')
    return records


def generate(model, tokenizer, row, config):
    import torch
    from transformers import GenerationConfig
    text = render(row, config, tokenizer)
    inputs = e.encode(tokenizer, text, 'chat', return_tensors='pt').to(model.device)
    length = inputs.input_ids.shape[1]
    budget = config['max_new_tokens']
    if length + budget > model.config.max_position_embeddings:
        raise ValueError('Context overflow; no document was truncated')
    eos = model.generation_config.eos_token_id or tokenizer.eos_token_id
    generation = GenerationConfig(max_new_tokens=budget, do_sample=False, num_beams=1, use_cache=True,
                                  eos_token_id=eos, bos_token_id=model.generation_config.bos_token_id,
                                  pad_token_id=tokenizer.pad_token_id if tokenizer.pad_token_id is not None else tokenizer.eos_token_id)
    torch.cuda.reset_peak_memory_stats()
    torch.cuda.synchronize()
    start = time.monotonic()
    with torch.inference_mode():
        output = model.generate(**inputs, generation_config=generation, logits_to_keep=1)
    tokens = output[0, length:]
    raw = tokenizer.decode(tokens, skip_special_tokens=True)
    torch.cuda.synchronize()
    eos_ids = eos if isinstance(eos, list) else [eos]
    hit = len(tokens) == budget and int(tokens[-1]) not in eos_ids
    return dict(id=row['id'], original_id=row['original_id'], raw_output=raw,
                raw_output_sha256=e.text_hash(raw), prompt_sha256=e.text_hash(text),
                input_tokens=length, generated_tokens=len(tokens), hit_output_limit=hit,
                elapsed_seconds=time.monotonic()-start, peak_allocated_gib=torch.cuda.max_memory_allocated()/2**30,
                completed_at=datetime.now(timezone.utc).isoformat(), draft=parse_draft(raw, row['docs'], hit))


def infer(args, rows, config, tokenizer, spec):
    path = args.run_dir/'drafts/predictions.json'
    records = cached(path, spec, rows, config, tokenizer)
    if len(records) == len(rows):
        return records
    search.assert_gpu_idle()
    model = e.load_model(args.model)
    try:
        for row in rows[len(records):]:
            try:
                record = generate(model, tokenizer, row, config)
                e.repro.write_json(path, dict(spec=spec, records=records+[record]))
                records.append(record)
                e.repro.write_json(args.run_dir/'progress.json', dict(status='running',
                                  saved_outputs=len(records), target_outputs=len(rows), last_saved_id=row['id'],
                                  protocol_sha256=spec['protocol_sha256']))
                print(f'audit [{len(records)}/{len(rows)}] {row["id"]} -> {record["draft"]["semantic_mode"]} ({record["draft"]["status"]})', flush=True)
            except Exception as error:
                saved = len(e.read_json(path)['records']) if path.exists() else 0
                e.repro.write_json(args.run_dir/'last_failure.json', dict(id=row['id'], error=str(error), saved_outputs=saved))
                raise
    finally:
        del model
    e.repro.write_json(args.run_dir/'progress.json', dict(status='generation_complete',
                      saved_outputs=len(records), target_outputs=len(rows), protocol_sha256=spec['protocol_sha256']))
    return records


def diagnostic_summary(rows, modes, methods):
    table = {published: dict.fromkeys(MODES, 0) for published in e.MODES}
    for row in rows:
        table[row['true_mode']][modes[row['id']]] += 1
    result = {}
    for name, records in methods.items():
        result[name] = dict(full_denominator=len(rows),
                            prior_label_counts=dict(Counter(r['pred_mode'] or 'invalid' for r in records)),
                            invalid_outputs=sum(r['pred_mode'] is None for r in records),
                            refuse_with_audit_answer=sum(r['pred_mode']=='refuse' and modes[r['id']]=='answer' for r in records),
                            non_conflict_with_audit_conflict=sum(r['pred_mode']!='conflict' and modes[r['id']]=='conflict' for r in records),
                            audit_unknown=sum(modes[r['id']]=='unknown' for r in records))
    return dict(population=len(rows), semantic_mode_counts=dict(Counter(modes.values())),
                published_vs_audit=table, prior_method_diagnostics=result)


def smoke_gate(records, target, config):
    if len(records) != target:
        raise ValueError('Technical smoke is incomplete')
    valid = sum(r['draft']['status'] == 'valid_structure' for r in records)
    if valid / target < config['smoke_minimum_structurally_valid_fraction']:
        raise ValueError(f'Technical smoke structure gate failed: {valid}/{target}. Inspect smoke reports before full inference; do not change this frozen run.')
    return dict(status='technical_structure_gate_passed', valid=valid, total=target,
                note='Structure and exact-quote provenance only; no semantic quality approval.')


def analyze(args, rows, records, methods, mapping, packet_hash, protocol_hash):
    if len(records) != len(rows):
        raise ValueError('Draft generation incomplete; resume inference')
    reverse = {value: key for key, value in mapping.items()}
    modes = {r['id']: r['draft']['semantic_mode'] for r in records}
    report = dict(status='draft_analysis_complete_separate_review_pending', protocol_sha256=protocol_hash,
                  split='val', selection='none', limitation=LIMITATION,
                  model_drafts=diagnostic_summary(rows, modes, methods),
                  draft_structure_counts=dict(Counter(r['draft']['status'] for r in records)),
                  draft_errors=dict(Counter(error for r in records for error in r['draft']['errors'])),
                  hit_output_limit_count=sum(r['hit_output_limit'] for r in records),
                  empty_output_count=sum(not r['raw_output'].strip() for r in records),
                  separate_review=None)
    if args.ratings:
        ratings = load_ratings(args.ratings, mapping, packet_hash, rows)
        report['separate_review'] = dict(ratings_path=str(args.ratings), sha256=e.repro.digest_file(args.ratings),
                                     provenance='Reviewer identities are recorded in CSV; the program does not certify human or independent scoring.',
                                     **diagnostic_summary(rows, {key:r['semantic_mode'] for key,r in ratings.items()}, methods))
        report['status'] = ('separate_review_complete' if all(r['semantic_mode']!='unknown' for r in ratings.values())
                            else 'separate_review_partial_or_ambiguous')
    entries = []
    for index, row in enumerate(rows):
        record = records[index]
        entry = dict(review_id=reverse[row['id']], id=row['id'], published_mode=row['true_mode'],
                     proposed_mode=modes[row['id']], draft_status=record['draft']['status'],
                     draft_errors=';'.join(record['draft']['errors']))
        for name, prior in methods.items():
            entry[name+'_label'] = prior[index]['pred_mode'] or 'invalid'
            entry[name+'_raw_output'] = prior[index]['raw_output']
        entries.append(entry)
    e.repro.write_json(args.run_dir/'reports/diagnosis.json', report)
    frozen_fields = list(entries[0])
    (args.run_dir/'reports/diagnostic_queue.csv').write_text(csv_text(entries, frozen_fields), encoding='utf-8')
    pages = ['<!doctype html><meta charset="utf-8"><title>Assisted validation diagnosis</title>',
             '<style>body{max-width:1000px;margin:30px auto;font:16px sans-serif}pre{white-space:pre-wrap;overflow-wrap:anywhere}article{border-top:1px solid #aaa}</style>',
             '<h1>Assisted validation diagnosis</h1><p>'+html.escape(LIMITATION)+'</p>']
    for row, record, entry in zip(rows, records, entries):
        pages += [f'<article><h2>{entry["review_id"]}</h2><p>{html.escape(row["question"])}</p>',
                  '<p>Draft: '+html.escape(json.dumps(record['draft'],ensure_ascii=False))+'</p>',
                  '<details><summary>Raw audit output</summary><pre>'+html.escape(record['raw_output'])+'</pre></details>']
        for i,doc in enumerate(row['docs'],1):
            pages.append(f'<details><summary>Document {i}</summary><pre>{html.escape(doc)}</pre></details>')
        for name in methods:
            pages.append('<p>'+html.escape(name+': '+entry[name+'_label'])+'</p><pre>'+html.escape(entry[name+'_raw_output'])+'</pre>')
        pages.append('</article>')
    (args.run_dir/'reports/assisted_review.html').write_text('\n'.join(pages),encoding='utf-8')
    lines = ['# 验证集证据诊断', '', LIMITATION, '', f'实例：{len(rows)}；状态：{report["status"]}。',
             '草稿语义分布：'+str(report['model_drafts']['semantic_mode_counts']),
             '结构检查：'+str(report['draft_structure_counts']),
             f'截断：{report["hit_output_limit_count"]}；空输出：{report["empty_output_count"]}。', '',
             '| 旧方法 | invalid输出 | refuse且草稿判充分 | 未判冲突且草稿判冲突 | 草稿未知 |',
             '| --- | ---: | ---: | ---: | ---: |']
    for name, counts in report['model_drafts']['prior_method_diagnostics'].items():
        lines.append(f'| {name} | {counts["invalid_outputs"]} | {counts["refuse_with_audit_answer"]} | {counts["non_conflict_with_audit_conflict"]} | {counts["audit_unknown"]} |')
    lines += ['', '以上为待复核的诊断计数，不把草稿判充分自动当成误拒。invalid保持原解析，原始输出在队列中供语义复核。',
              '盲审入口：../review/public/evidence_blind.html；辅助入口：assisted_review.html。',
              '复核评分仅在显式传入--ratings后单列统计；评审身份由CSV记录，程序不认证是否人类或独立。不自动导入草稿，不改发布标签或选择门槛。']
    (args.run_dir/'reports/diagnosis.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=['all','check','infer','analyze','smoke-gate'], default='all')
    parser.add_argument('--run_dir', type=Path, default=Path('runs')/DEFAULT_RUN)
    parser.add_argument('--reference', type=Path, default=Path('runs/qwen2.5-3b-small'))
    parser.add_argument('--prior', type=Path, default=Path('runs/qwen2.5-3b-classification-prompt-validation-v3'))
    parser.add_argument('--baseline', type=Path, default=Path('runs/qwen2.5-3b-classification-grid/chat8/val/predictions.json'))
    parser.add_argument('--model', default=os.environ.get('KBA_MODEL'))
    parser.add_argument('--limit_questions', type=int)
    parser.add_argument('--ratings', type=Path)
    args = parser.parse_args()
    if not args.model:
        parser.error('Use the shell entry or --model')
    args.model = str(Path(args.model).resolve())
    for name in ['run_dir','reference','prior','baseline']:
        setattr(args, name, e.resolve(getattr(args,name)))
    if args.ratings:
        args.ratings = e.resolve(args.ratings)
        if args.stage != 'analyze':
            parser.error('--ratings is supported only with --stage analyze')
    for protected in [args.reference,args.prior,args.baseline.parents[2],ROOT/'runs/qwen2.5-3b-free-answer-study', Path(args.model)]:
        if args.run_dir == protected or args.run_dir in protected.parents or protected in args.run_dir.parents:
            parser.error('run_dir must be separate from every protected source')
    if args.limit_questions is not None and args.run_dir.name == DEFAULT_RUN:
        parser.error('Smoke requires its own run_dir')
    if args.stage == 'smoke-gate' and args.limit_questions is None:
        parser.error('smoke-gate requires --limit_questions')
    config = e.read_json(CONFIG)
    if config['max_new_tokens'] != 512 or config['task'] != 'validation_evidence_diagnosis_only':
        raise ValueError('Unexpected audit configuration; create a new protocol for changes')
    rows, full, source_spec = sources(args)
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(args.model,local_files_only=True)
    methods = prior_methods(args, full, rows, tokenizer)
    with e.legacy.run_lock(args.run_dir):
        e.freeze(args.run_dir/'protocol.json', protocol(args,rows,source_spec,config))
        protocol_hash = e.repro.digest_file(args.run_dir/'protocol.json')
        mapping, packet_hash = prepare_review(args,rows,protocol_hash)
        spec = dict(protocol_sha256=protocol_hash,split='val',task=config['task'])
        records = cached(args.run_dir/'drafts/predictions.json',spec,rows,config,tokenizer)
        if args.stage == 'smoke-gate':
            result = smoke_gate(records,len(rows),config)
            e.repro.write_json(args.run_dir/'smoke_gate.json',result)
            print(json.dumps(result),flush=True)
            return
        if args.stage in ['all','check','infer']:
            lengths = [len(e.encode(tokenizer,render(row,config,tokenizer),'chat')['input_ids']) for row in rows]
            context = e.read_json(Path(args.model)/'config.json')['max_position_embeddings']
            if max(lengths)+config['max_new_tokens'] > context:
                raise ValueError('Context overflow; no documents truncated')
            # Planning assumptions, not a benchmark: every item uses its full output budget.
            budget_tokens = len(rows)*config['max_new_tokens']
            preflight = dict(status='cpu_preflight_passed',instances=len(rows),saved_outputs=len(records),
                             max_input_tokens=max(lengths),mean_input_tokens=sum(lengths)/len(lengths),
                             reserved_output_tokens=config['max_new_tokens'],context_tokens=context,
                             planning_minutes=[round(budget_tokens/100/60+3,1),round(budget_tokens/40/60+5,1)],
                             estimate_note='Planning assumes 40-100 generated tokens/sec and full 512-token outputs; not measured throughput or a duration guarantee. Add host contention overhead.',
                             launch_actor='user',limitation=LIMITATION)
            e.repro.write_json(args.run_dir/'preflight.json',preflight)
            print(json.dumps(preflight,ensure_ascii=False),flush=True)
        if args.stage == 'check':
            if not (args.run_dir/'progress.json').exists():
                e.repro.write_json(args.run_dir/'progress.json',dict(status='prepared_not_started',
                                  saved_outputs=len(records),target_outputs=len(rows),protocol_sha256=protocol_hash))
            return
        if args.stage in ['all','infer']:
            records = infer(args,rows,config,tokenizer,spec)
        if args.stage in ['all','analyze']:
            analyze(args,rows,records,methods,mapping,packet_hash,protocol_hash)
            e.repro.write_json(args.run_dir/'progress.json',dict(status='analysis_complete',
                              saved_outputs=len(records),target_outputs=len(rows),protocol_sha256=protocol_hash,
                              review_status=e.read_json(args.run_dir/'reports/diagnosis.json')['status']))
            print('Audit generation/diagnosis complete; explicit review remains separately recorded.',flush=True)


if __name__ == '__main__':
    main()
