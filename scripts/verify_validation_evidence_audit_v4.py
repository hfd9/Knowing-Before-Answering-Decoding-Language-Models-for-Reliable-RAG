"""Read-only replay of completed v4 artifacts; optional separate summary JSON."""

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re

import validation_evidence_audit_v4 as v4


def independent_summary(rows, records, methods):
    modes=['answer','refuse','conflict','unknown']
    matrix={mode:dict.fromkeys(modes,0) for mode in modes[:3]}
    inferred={record['id']:record['draft']['semantic_mode'] for record in records}
    for row in rows:
        matrix[row['true_mode']][inferred[row['id']]]+=1
    previous={}
    for name, values in methods.items():
        previous[name]=dict(full_denominator=len(rows),
                            prior_label_counts=dict(Counter(x['pred_mode'] or 'invalid' for x in values)),
                            invalid_outputs=sum(x['pred_mode'] is None for x in values),
                            refuse_with_audit_answer=sum(x['pred_mode']=='refuse' and inferred[x['id']]=='answer' for x in values),
                            non_conflict_with_audit_conflict=sum(x['pred_mode']!='conflict' and inferred[x['id']]=='conflict' for x in values),
                            audit_unknown=sum(inferred[x['id']]=='unknown' for x in values))
    return dict(population=len(rows),semantic_mode_counts=dict(Counter(inferred.values())),
                published_vs_audit=matrix,prior_method_diagnostics=previous)


def verify(run_dir, tokenizer):
    e,audit,v3=v4.e,v4.audit,v4.v3
    protocol=e.read_json(run_dir/'protocol.json')
    config=e.read_json(v4.CONFIG)
    args=argparse.Namespace(run_dir=run_dir,reference=v4.ROOT/'runs/qwen2.5-3b-small',
                            prior=v4.ROOT/'runs/qwen2.5-3b-classification-prompt-validation-v3',
                            baseline=v4.ROOT/'runs/qwen2.5-3b-classification-grid/chat8/val/predictions.json',
                            model=protocol['model'],limit_questions=3 if protocol['smoke'] else None)
    rows,full,source=audit.sources(args)
    assert v4.protocol(args,rows,source,config)==protocol,'Protocol/source/code/runtime mismatch'
    for path,digest in protocol['prior_source_sha256'].items():
        assert e.repro.digest_file(Path(path))==digest,'Prior output hash mismatch'
    methods=audit.prior_methods(args,full,rows,tokenizer)
    protocol_hash=e.repro.digest_file(run_dir/'protocol.json')
    spec=dict(protocol_sha256=protocol_hash,split='val',task=config['task'])
    prediction_path=run_dir/'drafts/predictions.json'
    original_hash=e.repro.digest_file(prediction_path)
    records=v3.cached(prediction_path,spec,rows,config,tokenizer)
    assert len(records)==len(rows),'Incomplete generation'
    saved=e.read_json(run_dir/'reports/diagnosis.json')
    independent=independent_summary(rows,records,methods)
    assert independent==saved['model_drafts'],'Independent report counts differ'
    structures=dict(Counter(x['draft']['status'] for x in records))
    errors=dict(Counter(error for x in records for error in x['draft']['errors']))
    assert structures==saved['draft_structure_counts']
    assert errors==saved['draft_errors']
    assert sum(x['hit_output_limit'] for x in records)==saved['hit_output_limit_count']
    assert sum(not x['raw_output'].strip() for x in records)==saved['empty_output_count']
    assert sum(x['rationale_token_ids'][-1] not in v3.eos_ids(tokenizer) for x in records)==saved['rationale_truncation_count']
    assert sum(x['draft']['status']=='valid_structure' and x['draft']['semantic_mode']!='unknown' for x in records)==saved['valid_definite_decisions']
    assert sum(x['draft']['status']=='valid_structure' and x['draft']['semantic_mode']=='unknown' for x in records)==saved['valid_unknown_decisions']
    state=e.read_json(run_dir/'progress.json')
    assert state['status']=='analysis_complete' and state['saved_outputs']==len(rows)
    assert state['protocol_sha256']==protocol_hash
    if protocol['smoke']:
        assert audit.smoke_gate(records,len(rows),config)==e.read_json(run_dir/'smoke_gate.json')
    matrix=independent['published_vs_audit']
    correct=sum(matrix[mode][mode] for mode in ['answer','refuse','conflict'])
    f1=[]
    for mode in ['answer','refuse','conflict']:
        tp=matrix[mode][mode]
        support=sum(matrix[mode].values())
        predicted=sum(row[mode] for row in matrix.values())
        f1.append(2*tp/(support+predicted) if support+predicted else 0.)
    bad_reason_ids=[]
    unmentioned_selected=[]
    complete_decisions=0
    for row,record in zip(rows,records):
        spans=v3.citation_spans(row['docs'])
        known={span['span_id'] for span in spans}
        mentioned=set(re.findall(r'\bD\d+\.S\d+\b',record['rationale']))
        nonexistent=sorted(mentioned-known)
        if nonexistent:
            bad_reason_ids.append(dict(id=row['id'],ids=nonexistent))
        decision=json.loads(record['raw_output'])
        if set(decision['citation_ids'])-mentioned:
            unmentioned_selected.append(row['id'])
        grammar=v3.DecisionGrammar(tokenizer,spans,v3.eos_ids(tokenizer))
        complete_decisions+=grammar.complete(record['decision_token_ids']) and record['decision_token_ids'][-1] in v3.eos_ids(tokenizer)
    assert e.repro.digest_file(prediction_path)==original_hash,'Predictions changed during verification'
    seconds=sum(x['elapsed_seconds'] for x in records)
    tokens=sum(x['generated_tokens'] for x in records)
    return dict(run_dir=str(run_dir.relative_to(v4.ROOT)),protocol_sha256=protocol_hash,
                predictions_sha256=original_hash,instances=len(rows),verified_code_prompt_files=len(protocol['code_and_prompt_sha256']),
                progress=state,counts=independent,structure_counts=structures,errors=errors,
                valid_definite_decisions=saved['valid_definite_decisions'],valid_unknown_decisions=saved['valid_unknown_decisions'],
                complete_constrained_decisions_with_eos=complete_decisions,
                rationale_truncations=saved['rationale_truncation_count'],
                publication_label_agreement=dict(correct=correct,total=len(rows),fraction=correct/len(rows),macro_f1=sum(f1)/3,
                    note='Agreement with published construction labels, unknown in full denominator; not semantic gold accuracy or candidate selection.'),
                literal_rationale_id_diagnostic=dict(records_with_nonexistent_ids=len(bad_reason_ids),items=bad_reason_ids,
                    records_with_selected_ids_not_mentioned_in_rationale=len(unmentioned_selected),
                    ids=unmentioned_selected,note='Literal ID provenance diagnostic; not a semantic correctness judgment.'),
                first_saved_utc=records[0]['completed_at'],last_saved_utc=records[-1]['completed_at'],
                summed_generation_seconds=seconds,generated_tokens=tokens,tokens_per_recorded_second=tokens/seconds,
                review_complete=saved['separate_review'] is not None),records


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,help='Optional new summary; never inside a run directory')
    args=parser.parse_args()
    base=v4.ROOT/'runs/qwen2.5-3b-validation-evidence-audit-v4'
    smoke=v4.ROOT/'runs/qwen2.5-3b-validation-evidence-audit-smoke-v4'
    if args.output:
        args.output=v4.e.resolve(args.output)
        if args.output==v4.ROOT/'runs' or v4.ROOT/'runs' in args.output.parents:
            parser.error('Summary output must be outside runs/')
        if args.output.exists():
            parser.error('Refuse to overwrite existing summary')
    from transformers import AutoTokenizer
    model=v4.e.read_json(base/'protocol.json')['model']
    tokenizer=AutoTokenizer.from_pretrained(model,local_files_only=True)
    full_result,full_records=verify(base,tokenizer)
    smoke_result,smoke_records=verify(smoke,tokenizer)
    fields=['rationale','raw_output','rationale_token_ids','decision_token_ids','prompt_sha256','decision_prompt_sha256']
    identical=all(all(a[field]==b[field] for field in fields) for a,b in zip(smoke_records,full_records[:9]))
    result=dict(verified_at_utc=datetime.now(timezone.utc).isoformat(),formal=full_result,smoke=smoke_result,
                smoke_matches_first_nine_formal_model_outputs=identical,
                boundary='Technical replay and literal diagnostics only; no new GPU or independent semantic scoring.')
    if args.output:
        v4.e.repro.write_json(args.output,result)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
