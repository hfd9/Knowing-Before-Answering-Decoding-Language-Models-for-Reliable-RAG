"""Val-only two-stage audit with constrained verdicts and exact source references."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import time

import validation_evidence_audit as audit
from evidence_decision_grammar import DecisionGrammar

e = audit.e
ROOT = audit.ROOT
CONFIG = ROOT/'prompts/validation_evidence_audit_v3.json'
DEFAULT_RUN = 'qwen2.5-3b-validation-evidence-audit-v3'


def citation_spans(docs):
    """Overlapping 24-word spans, step 16, with original character offsets."""
    spans = []
    for doc_id, doc in enumerate(docs, 1):
        words = list(re.finditer(r'\S+', doc))
        for number, first in enumerate(range(0, len(words), 16), 1):
            start = words[first].start()
            end = words[min(first+24, len(words))-1].end()
            spans.append(dict(span_id=f'D{doc_id}.S{number}', doc_id=doc_id,
                              start=start, end=end, quote=doc[start:end]))
            if first+24 >= len(words):
                break
    return spans


def messages(row, config):
    body = '\n\n'.join(f'Document {i}:\n{doc}' for i, doc in enumerate(row['docs'], 1))
    body += '\n\nCitation index (exact excerpts; original documents above remain authoritative):\n'
    body += '\n'.join(s['span_id']+': '+s['quote'] for s in citation_spans(row['docs']))
    body += '\n\nQuestion: '+row['question']
    body += ('\n\nAnalyze this exact question in at most 100 words. State all premises needed, '
             'which are supported or missing, and any explicitly incompatible relevant claims. '
             'Mention useful passage IDs. Do not output JSON in this analysis.')
    return [{'role':'system', 'content':config['instruction']}, {'role':'user', 'content':body}]


def render(row, config, tokenizer):
    return tokenizer.apply_chat_template(messages(row, config), tokenize=False, add_generation_prompt=True)


def render_decision(row, config, tokenizer, rationale):
    conversation = messages(row, config)
    conversation += [{'role':'assistant', 'content':rationale},
                     {'role':'user', 'content':config['decision_instruction']}]
    return tokenizer.apply_chat_template(conversation, tokenize=False, add_generation_prompt=True)


def parse_draft(raw, docs, truncated=False):
    invalid = dict(status='invalid', semantic_mode='unknown', proposal=None, errors=[])
    def bad(error):
        return dict(invalid, errors=[error])
    if truncated:
        return bad('output_limit_without_eos_or_complete_decision')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate key')
            result[key] = value
        return result
    try:
        value = json.loads(raw, object_pairs_hook=unique)
    except (ValueError, TypeError):
        return bad('invalid_json')
    if not isinstance(value, dict) or set(value) != {'semantic_mode','citation_ids'}:
        return bad('unexpected_schema')
    mode, ids = value['semantic_mode'], value['citation_ids']
    if not isinstance(mode, str) or mode not in audit.MODES:
        return bad('invalid_semantic_mode')
    if (not isinstance(ids, list) or any(not isinstance(x, str) for x in ids)
            or len(ids) != len(set(ids)) or len(ids) > 4):
        return bad('invalid_citation_ids')
    lookup = {s['span_id']:s for s in citation_spans(docs)}
    if any(key not in lookup for key in ids):
        return bad('unknown_citation_id')
    citations = [lookup[key] for key in ids]
    if mode == 'answer' and not citations:
        return bad('answer_requires_citation')
    if mode == 'conflict' and (len(citations) != 2 or len({s['doc_id'] for s in citations}) != 2):
        return bad('conflict_requires_two_documents')
    if mode in ['refuse','unknown'] and citations:
        return bad('nonanswer_citations_not_in_schema')
    return dict(status='valid_structure', semantic_mode=mode,
                proposal=dict(semantic_mode=mode, citations=citations), errors=[])


def eos_ids(tokenizer):
    # Qwen's chat EOS is tokenizer.eos_token_id; no remote dependency or model load.
    return [tokenizer.eos_token_id]


def cached(path, spec, rows, config, tokenizer):
    if not path.exists():
        return []
    data = e.read_json(path)
    if data['spec'] != spec or len(data['records']) > len(rows):
        raise ValueError('V3 cache settings/count changed; use a new run_dir')
    for row, record in zip(rows, data['records']):
        if (record['id'],record['original_id']) != (row['id'],row['original_id']):
            raise ValueError('V3 cache identity/order mismatch')
        for field in ['raw_output','rationale']:
            if e.text_hash(record[field]) != record[field+'_sha256']:
                raise ValueError('V3 cached model output hash mismatch')
        first = render(row,config,tokenizer)
        second = render_decision(row,config,tokenizer,record['rationale'])
        for field, text in [('prompt', first), ('decision_prompt', second)]:
            if record[field+'_sha256'] != e.text_hash(text):
                raise ValueError('V3 cached prompt hash mismatch')
        if record['input_tokens'] != len(e.encode(tokenizer,first,'chat')['input_ids']):
            raise ValueError('V3 input length mismatch')
        if record['decision_input_tokens'] != len(e.encode(tokenizer,second,'chat')['input_ids']):
            raise ValueError('V3 decision input length mismatch')
        all_tokens = []
        for stage, budget in [('rationale',config['rationale_max_new_tokens']),
                              ('decision',config['decision_max_new_tokens'])]:
            tokens = record[stage+'_token_ids']
            if (not isinstance(tokens,list) or any(type(t) is not int for t in tokens)
                    or not 0 < len(tokens) <= budget):
                raise ValueError('V3 stage token metadata invalid')
            expected = record['rationale' if stage == 'rationale' else 'raw_output']
            if tokenizer.decode(tokens,skip_special_tokens=True) != expected:
                raise ValueError('V3 output tokens do not decode to saved text')
            all_tokens.extend(tokens)
        grammar = DecisionGrammar(tokenizer,citation_spans(row['docs']),eos_ids(tokenizer))
        grammar.allowed(record['decision_token_ids'])  # Reject even a grammatically illegal saved prefix.
        limited = (record['rationale_token_ids'][-1] not in eos_ids(tokenizer)
                   or not grammar.complete(record['decision_token_ids']))
        if type(record['hit_output_limit']) is not bool or record['hit_output_limit'] != limited:
            raise ValueError('V3 stage completion metadata mismatch')
        if record['generated_tokens'] != len(all_tokens):
            raise ValueError('V3 generated token total mismatch')
        draft = parse_draft(record['raw_output'],row['docs'],limited)
        if not record['rationale'].strip():
            draft = dict(status='invalid',semantic_mode='unknown',proposal=None,errors=['empty_rationale'])
        if record['draft'] != draft:
            raise ValueError('V3 source reference/parser replay mismatch')
    return data['records']


def generate(model, tokenizer, row, config):
    import torch
    from transformers import GenerationConfig
    torch.cuda.reset_peak_memory_stats()
    torch.cuda.synchronize()
    start = time.monotonic()
    end_ids = eos_ids(tokenizer)
    def run(text, budget, grammar=None):
        inputs = e.encode(tokenizer,text,'chat',return_tensors='pt').to(model.device)
        size = inputs.input_ids.shape[1]
        if size+budget > model.config.max_position_embeddings:
            raise ValueError('V3 context overflow; no document truncated')
        generation = GenerationConfig(max_new_tokens=budget,do_sample=False,num_beams=1,use_cache=True,
                                      eos_token_id=end_ids,bos_token_id=model.generation_config.bos_token_id,
                                      pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id)
        extra = {'prefix_allowed_tokens_fn':grammar.callback(size)} if grammar else {}
        with torch.inference_mode():
            output = model.generate(**inputs,generation_config=generation,logits_to_keep=1,**extra)
        tokens = output[0,size:].tolist()
        return tokenizer.decode(tokens,skip_special_tokens=True),tokens,size
    first = render(row,config,tokenizer)
    rationale, first_tokens, first_size = run(first,config['rationale_max_new_tokens'])
    second = render_decision(row,config,tokenizer,rationale)
    grammar = DecisionGrammar(tokenizer,citation_spans(row['docs']),end_ids)
    raw, decision_tokens, second_size = run(second,config['decision_max_new_tokens'],grammar)
    limited = first_tokens[-1] not in end_ids or not grammar.complete(decision_tokens)
    draft = parse_draft(raw,row['docs'],limited)
    if not rationale.strip():
        draft = dict(status='invalid',semantic_mode='unknown',proposal=None,errors=['empty_rationale'])
    torch.cuda.synchronize()
    return dict(id=row['id'],original_id=row['original_id'],rationale=rationale,
                rationale_sha256=e.text_hash(rationale),rationale_token_ids=first_tokens,
                raw_output=raw,raw_output_sha256=e.text_hash(raw),decision_token_ids=decision_tokens,
                prompt_sha256=e.text_hash(first),decision_prompt_sha256=e.text_hash(second),
                input_tokens=first_size,decision_input_tokens=second_size,
                generated_tokens=len(first_tokens)+len(decision_tokens),hit_output_limit=limited,
                elapsed_seconds=time.monotonic()-start,peak_allocated_gib=torch.cuda.max_memory_allocated()/2**30,
                completed_at=datetime.now(timezone.utc).isoformat(),draft=draft)


def protocol(args, rows, source_spec, config):
    files = ['scripts/validation_evidence_audit_v3.py','scripts/evidence_decision_grammar.py',
             'scripts/run_validation_evidence_audit_v3.sh','scripts/run_validation_evidence_audit_v3_review.sh',
             'prompts/validation_evidence_audit_v3.json','scripts/validation_evidence_audit.py',
             'scripts/classification_prompt_search.py','scripts/evidence_experiment.py','scripts/small_repro.py',
             'scripts/prompt_baseline.py','scripts/analyze_prompt_baseline.py','code/prompts.py']
    files.append(str(audit.search.PROMPTS.relative_to(ROOT)))
    prior = [args.prior/'protocol.json',args.baseline,args.baseline.parents[2]/'protocol.json']
    prior += [args.prior/n/'predictions.json' for n in e.read_json(audit.search.PROMPTS)['candidate_order']]
    return dict(schema_version=3,task=config['task'],model=args.model,split='val',
                selected_ids=[r['id'] for r in rows],source_spec=source_spec,configuration=config,
                smoke=args.limit_questions is not None,
                code_and_prompt_sha256={p:e.repro.digest_file(ROOT/p) for p in files},
                prior_source_sha256={str(p):e.repro.digest_file(p) for p in prior},
                generation_config_sha256=e.repro.digest_file(Path(args.model)/'generation_config.json'),
                runtime_versions={n:e.version(n) for n in ['torch','transformers','numpy']},
                generation=dict(dtype='bfloat16',attention='sdpa',do_sample=False,num_beams=1,use_cache=True,
                                rationale_budget=256,decision_budget=128,total_maximum_new_tokens=384,
                                decision_constraint='prefix_allowed_tokens_fn token grammar; EOS only after full JSON'),
                parser='v3 exact decision schema and span IDs; token grammar replay; no JSON repair',
                citations='24-word windows, step16, original offsets; answer1-4, conflict2 distinct docs; provenance only',
                review='separate explicit ratings; same val technical smoke adapted after v1/v2 failure',
                selection='none; unknown permitted; structure gate does not certify semantics',limitation=audit.LIMITATION)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',choices=['all','check','infer','analyze','smoke-gate'],default='all')
    parser.add_argument('--run_dir',type=Path,default=Path('runs')/DEFAULT_RUN)
    parser.add_argument('--reference',type=Path,default=Path('runs/qwen2.5-3b-small'))
    parser.add_argument('--prior',type=Path,default=Path('runs/qwen2.5-3b-classification-prompt-validation-v3'))
    parser.add_argument('--baseline',type=Path,default=Path('runs/qwen2.5-3b-classification-grid/chat8/val/predictions.json'))
    parser.add_argument('--model',default=os.environ.get('KBA_MODEL'))
    parser.add_argument('--limit_questions',type=int)
    parser.add_argument('--ratings',type=Path)
    args = parser.parse_args()
    if not args.model:
        parser.error('Use the shell entry or --model')
    args.model = str(Path(args.model).resolve())
    for name in ['run_dir','reference','prior','baseline']:
        setattr(args,name,e.resolve(getattr(args,name)))
    if args.ratings:
        args.ratings = e.resolve(args.ratings)
        if args.stage != 'analyze':
            parser.error('--ratings requires --stage analyze')
    for protected in [args.reference,args.prior,args.baseline.parents[2],ROOT/'runs/qwen2.5-3b-free-answer-study',Path(args.model)]:
        if args.run_dir == protected or args.run_dir in protected.parents or protected in args.run_dir.parents:
            parser.error('run_dir must be separate from every protected source')
    if args.limit_questions is not None and args.run_dir.name == DEFAULT_RUN:
        parser.error('Smoke requires its own run_dir')
    if args.stage == 'smoke-gate' and args.limit_questions is None:
        parser.error('smoke-gate requires --limit_questions')
    config = e.read_json(CONFIG)
    if (config['rationale_max_new_tokens'],config['decision_max_new_tokens']) != (256,128):
        raise ValueError('Unexpected v3 budgets')
    rows, full, source_spec = audit.sources(args)
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(args.model,local_files_only=True)
    methods = audit.prior_methods(args,full,rows,tokenizer)
    with e.legacy.run_lock(args.run_dir):
        e.freeze(args.run_dir/'protocol.json',protocol(args,rows,source_spec,config))
        digest = e.repro.digest_file(args.run_dir/'protocol.json')
        mapping, packet_hash = audit.prepare_review(args,rows,digest)
        spec = dict(protocol_sha256=digest,split='val',task=config['task'])
        records = cached(args.run_dir/'drafts/predictions.json',spec,rows,config,tokenizer)
        if args.stage == 'smoke-gate':
            gate = audit.smoke_gate(records,len(rows),config)
            e.repro.write_json(args.run_dir/'smoke_gate.json',gate)
            print(json.dumps(gate),flush=True)
            return
        if args.stage in ['all','check','infer']:
            first_lengths, second_bounds, grammar_bounds = [], [], []
            for row in rows:
                first_lengths.append(len(e.encode(tokenizer,render(row,config,tokenizer),'chat')['input_ids']))
                # Rationale is bounded by 256 generated tokens. Add 8 for retokenization boundaries.
                second_bounds.append(len(e.encode(tokenizer,render_decision(row,config,tokenizer,''),'chat')['input_ids'])+264)
                grammar_bounds.append(DecisionGrammar(tokenizer,citation_spans(row['docs']),eos_ids(tokenizer)).maximum_tokens)
            context = e.read_json(Path(args.model)/'config.json')['max_position_embeddings']
            if max(first_lengths)+256 > context or max(second_bounds)+128 > context:
                raise ValueError('V3 context overflow; no evidence truncated')
            if max(grammar_bounds) > 128:
                raise ValueError('Decision budget cannot cover longest constrained output')
            # v1/v2 measured ~21.5 tokens/sec. Two prefills and new grammar add overhead.
            preflight = dict(status='cpu_preflight_passed',instances=len(rows),saved_outputs=len(records),
                             max_input_tokens=max(first_lengths),decision_input_upper_bound=max(second_bounds),
                             decision_grammar_max_tokens=max(grammar_bounds),context_tokens=context,
                             budgets=dict(rationale=256,decision=128,total=384),
                             planning_minutes=[round(len(rows)*384/25/60+5,1),round(len(rows)*384/12/60+10,1)],
                             estimate_note='12-25 tokens/sec planning, two prefills; v3 not benchmarked. Not a duration guarantee.',
                             launch_actor='user',limitation=audit.LIMITATION)
            e.repro.write_json(args.run_dir/'preflight.json',preflight)
            print(json.dumps(preflight),flush=True)
        if args.stage == 'check':
            if not (args.run_dir/'progress.json').exists():
                e.repro.write_json(args.run_dir/'progress.json',dict(status='prepared_not_started',saved_outputs=len(records),target_outputs=len(rows),protocol_sha256=digest))
            return
        if args.stage in ['all','infer']:
            # Reuse v1's atomic save/recovery and GPU guard without editing its frozen file.
            audit.generate, audit.cached = generate, cached
            records = audit.infer(args,rows,config,tokenizer,spec)
        if args.stage in ['all','analyze']:
            display = [dict(r,raw_output='Analysis (unconstrained):\n'+r['rationale']+'\n\nDecision (constrained):\n'+r['raw_output']) for r in records]
            audit.analyze(args,rows,display,methods,mapping,packet_hash,digest)
            report = e.read_json(args.run_dir/'reports/diagnosis.json')
            report['output_method'] = 'v3 constrained verdict + mechanically resolved original spans; separate free-text rationale'
            report['valid_definite_decisions'] = sum(r['draft']['status']=='valid_structure' and r['draft']['semantic_mode']!='unknown' for r in records)
            report['valid_unknown_decisions'] = sum(r['draft']['status']=='valid_structure' and r['draft']['semantic_mode']=='unknown' for r in records)
            e.repro.write_json(args.run_dir/'reports/diagnosis.json',report)
            e.repro.write_json(args.run_dir/'progress.json',dict(status='analysis_complete',saved_outputs=len(records),target_outputs=len(rows),protocol_sha256=digest,review_status=report['status']))
            print('V3 generation/diagnosis complete; source checks do not certify semantics.',flush=True)


if __name__ == '__main__':
    main()
