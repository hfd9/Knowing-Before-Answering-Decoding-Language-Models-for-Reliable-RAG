"""Continue the constrained audit with enough budget for completed analysis."""

import argparse
import json
import os
from pathlib import Path

import validation_evidence_audit_v3 as v3

audit, e, ROOT = v3.audit, v3.e, v3.ROOT
CONFIG = ROOT/'prompts/validation_evidence_audit_v4.json'
DEFAULT_RUN = 'qwen2.5-3b-validation-evidence-audit-v4'


def protocol(args, rows, source_spec, config):
    result = v3.protocol(args,rows,source_spec,config)
    result['schema_version'] = 4
    result['revision_reason'] = ('v3 constrained decisions all completed; 8/9 analyses hit 256 tokens. '
                                 'Increase analysis budget to 1024; retain complete analysis and 6/9 gate.')
    result['generation'].update(rationale_budget=config['rationale_max_new_tokens'],
                                decision_budget=config['decision_max_new_tokens'],
                                total_maximum_new_tokens=config['max_new_tokens'])
    for path in [Path(__file__),CONFIG,ROOT/'scripts/run_validation_evidence_audit_v4.sh',
                 ROOT/'scripts/run_validation_evidence_audit_v4_review.sh']:
        result['code_and_prompt_sha256'][str(path.relative_to(ROOT))] = e.repro.digest_file(path)
    return result


def preflight(args, rows, config, tokenizer, records):
    first, second, grammar = [], [], []
    rationale_budget, decision_budget = config['rationale_max_new_tokens'], config['decision_max_new_tokens']
    for row in rows:
        first.append(len(e.encode(tokenizer,v3.render(row,config,tokenizer),'chat')['input_ids']))
        second.append(len(e.encode(tokenizer,v3.render_decision(row,config,tokenizer,''),'chat')['input_ids'])+rationale_budget+8)
        grammar.append(v3.DecisionGrammar(tokenizer,v3.citation_spans(row['docs']),v3.eos_ids(tokenizer)).maximum_tokens)
    context = e.read_json(Path(args.model)/'config.json')['max_position_embeddings']
    if max(first)+rationale_budget > context or max(second)+decision_budget > context:
        raise ValueError('V4 context overflow; no document truncated')
    if max(grammar) > decision_budget:
        raise ValueError('V4 decision budget insufficient')
    total = rationale_budget+decision_budget
    return dict(status='cpu_preflight_passed',instances=len(rows),saved_outputs=len(records),
                max_input_tokens=max(first),decision_input_upper_bound=max(second),
                decision_grammar_max_tokens=max(grammar),context_tokens=context,
                budgets=dict(rationale=rationale_budget,decision=decision_budget,total=total),
                planning_minutes=[round(len(rows)*total/25/60+5,1),round(len(rows)*total/12/60+10,1)],
                estimate_note='Full 1152-token cap at 12-25 tokens/sec; conservative capacity planning, not expected output length. V4 not benchmarked.',
                launch_actor='user',limitation=audit.LIMITATION)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',choices=['all','check','infer','analyze','smoke-gate'],default='all')
    parser.add_argument('--run_dir',type=Path,default=Path('runs')/DEFAULT_RUN)
    parser.add_argument('--reference',type=Path,default=Path('runs/qwen2.5-3b-small'))
    parser.add_argument('--prior',type=Path,default=Path('runs/qwen2.5-3b-classification-prompt-validation-v3'))
    parser.add_argument('--baseline',type=Path,default=Path('runs/qwen2.5-3b-classification-grid/chat8/val/predictions.json'))
    parser.add_argument('--model',default=os.environ.get('KBA_MODEL'))
    parser.add_argument('--limit_questions',type=int)
    parser.add_argument('--ratings',type=Path)
    args=parser.parse_args()
    if not args.model:
        parser.error('Use the shell entry or --model')
    args.model=str(Path(args.model).resolve())
    for name in ['run_dir','reference','prior','baseline']:
        setattr(args,name,e.resolve(getattr(args,name)))
    if args.ratings:
        args.ratings=e.resolve(args.ratings)
        if args.stage!='analyze':
            parser.error('--ratings requires --stage analyze')
    for protected in [args.reference,args.prior,args.baseline.parents[2],ROOT/'runs/qwen2.5-3b-free-answer-study',Path(args.model)]:
        if args.run_dir==protected or args.run_dir in protected.parents or protected in args.run_dir.parents:
            parser.error('run_dir must be separate from every protected source')
    if args.limit_questions is not None and args.run_dir.name==DEFAULT_RUN:
        parser.error('Smoke requires its own run_dir')
    if args.stage=='smoke-gate' and args.limit_questions is None:
        parser.error('smoke-gate requires --limit_questions')
    config=e.read_json(CONFIG)
    if (config['rationale_max_new_tokens'],config['decision_max_new_tokens'],config['max_new_tokens'])!=(1024,128,1152):
        raise ValueError('Unexpected v4 budgets')
    rows,full,source_spec=audit.sources(args)
    from transformers import AutoTokenizer
    tokenizer=AutoTokenizer.from_pretrained(args.model,local_files_only=True)
    methods=audit.prior_methods(args,full,rows,tokenizer)
    with e.legacy.run_lock(args.run_dir):
        e.freeze(args.run_dir/'protocol.json',protocol(args,rows,source_spec,config))
        digest=e.repro.digest_file(args.run_dir/'protocol.json')
        mapping,packet_hash=audit.prepare_review(args,rows,digest)
        spec=dict(protocol_sha256=digest,split='val',task=config['task'])
        records=v3.cached(args.run_dir/'drafts/predictions.json',spec,rows,config,tokenizer)
        if args.stage=='smoke-gate':
            gate=audit.smoke_gate(records,len(rows),config)
            e.repro.write_json(args.run_dir/'smoke_gate.json',gate)
            print(json.dumps(gate),flush=True)
            return
        if args.stage in ['all','check','infer']:
            check=preflight(args,rows,config,tokenizer,records)
            e.repro.write_json(args.run_dir/'preflight.json',check)
            print(json.dumps(check),flush=True)
        if args.stage=='check':
            if not (args.run_dir/'progress.json').exists():
                e.repro.write_json(args.run_dir/'progress.json',dict(status='prepared_not_started',saved_outputs=len(records),target_outputs=len(rows),protocol_sha256=digest))
            return
        if args.stage in ['all','infer']:
            audit.generate,audit.cached=v3.generate,v3.cached
            records=audit.infer(args,rows,config,tokenizer,spec)
        if args.stage in ['all','analyze']:
            display=[dict(r,raw_output='Analysis (unconstrained):\n'+r['rationale']+'\n\nDecision (constrained):\n'+r['raw_output']) for r in records]
            audit.analyze(args,rows,display,methods,mapping,packet_hash,digest)
            report=e.read_json(args.run_dir/'reports/diagnosis.json')
            report['output_method']='v4 completed analysis (1024-token cap) + v3 constrained verdict/source IDs'
            report['rationale_truncation_count']=sum(r['rationale_token_ids'][-1] not in v3.eos_ids(tokenizer) for r in records)
            report['valid_definite_decisions']=sum(r['draft']['status']=='valid_structure' and r['draft']['semantic_mode']!='unknown' for r in records)
            report['valid_unknown_decisions']=sum(r['draft']['status']=='valid_structure' and r['draft']['semantic_mode']=='unknown' for r in records)
            e.repro.write_json(args.run_dir/'reports/diagnosis.json',report)
            e.repro.write_json(args.run_dir/'progress.json',dict(status='analysis_complete',saved_outputs=len(records),target_outputs=len(rows),protocol_sha256=digest,review_status=report['status']))
            print('V4 generation/diagnosis complete; source checks do not certify semantics.',flush=True)


if __name__=='__main__':
    main()
