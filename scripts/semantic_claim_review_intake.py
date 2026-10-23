"""Validate saved55 reviewer forms and preserve provenance; no inference, scoring or approval."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SPEC='prompts/semantic_claim_review_intake_v1.json'
INPUT_FIELDS=['target_interpretation','answerability','candidate_answer','document_support',
              'missing_link','ambiguity','conflicting_propositions']
ENDPOINTS=['gives_specific_target_answer','target_claim_supported','withholding_matches_gap',
           'explanation_all_claims_supported','full_answer_claim_coverage_confirmed']
PARENT_FIELDS=['document_support','counterevidence','missing_link','ambiguity','judgment']
EXPOSURE_FIELDS=['prior_project_history_exposure','prior_author_ratings_exposure',
                 'prior_outputs_or_probe_results_exposure','coordinator_material_exposure',
                 'instructions_or_hidden_context_exposure']
JUDGMENTS={'supported','contradicted','unsupported','ambiguous','not_applicable'}


def require(ok,message):
    if not ok:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text())


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def encoded(value):
    return json.dumps(value,ensure_ascii=False,indent=2)+'\n'


def string(value,label):
    require(isinstance(value,str) and bool(value.strip()),'Required text: '+label)


def timestamp(value):
    string(value,'timestamp')
    result=datetime.fromisoformat(value.replace('Z','+00:00'))
    require(result.utcoffset() is not None,'Timestamp must include timezone')
    return result


def indexed(rows,expected,label):
    require(isinstance(rows,list) and all(isinstance(r,dict) for r in rows),'Invalid '+label)
    ids=[r.get('item_id') for r in rows]
    require(all(isinstance(k,str) for k in ids) and len(ids)==len(set(ids)) and set(ids)==set(expected),
            label+' must cover each supplied item exactly once')
    return {r['item_id']:r for r in rows}


def citation(value,text,document_index=None):
    require(isinstance(value,dict),'Citation must be an object')
    start,end=value.get('start'),value.get('end');quote=value.get('quote')
    require(type(start) is int and type(end) is int and 0<=start<end<=len(text),'Citation offset invalid')
    require(isinstance(quote,str) and quote.strip() and text[start:end]==quote,'Citation text mismatch')
    expected=hashlib.sha256(text.encode()).hexdigest()
    require('text_sha256' not in value or value['text_sha256']==expected,'Citation hash mismatch')
    result=dict(start=start,end=end,quote=quote,text_sha256=expected)
    if document_index is not None:
        require(value.get('document_index')==document_index and type(value.get('document_index')) is int,
                'Citation document slot invalid')
        result['document_index']=document_index
    return result


def document_citations(values,documents,required=False):
    require(isinstance(values,list) and (not required or bool(values)),'Evidence citations required')
    result=[]
    for value in values:
        require(isinstance(value,dict),'Document citation must be an object')
        slot=value.get('document_index')
        require(type(slot) is int and 1<=slot<=len(documents),'Invalid document slot')
        result.append(citation(value,documents[slot-1],slot))
    return result


def validate_inputs(form,items):
    rows=indexed(form.get('items'),items,'Input form');normalized={}
    for iid,row in rows.items():
        if row.get('status')=='unreviewed':
            require(all(row.get(k) is None for k in INPUT_FIELDS),'Unreviewed input has a score')
            continue
        require(row.get('status')=='reviewed','Invalid input review status')
        require(row.get('answerability') in {'answerable','insufficient','conflict','ambiguous'},'Invalid input mode')
        for key in ['target_interpretation','missing_link','ambiguity']:
            string(row.get(key),key)
        answer=row.get('candidate_answer')
        require(answer is None or isinstance(answer,str) and answer.strip(),'Invalid candidate answer')
        if row['answerability']=='answerable':
            string(answer,'answerable candidate')
        conflicts=row.get('conflicting_propositions')
        require(isinstance(conflicts,list) and all(isinstance(v,str) and v.strip() for v in conflicts),
                'Conflict propositions must be a list')
        if row['answerability']=='conflict':
            require(len({s.strip().casefold() for s in conflicts})>=2,'Conflict requires at least two distinct propositions')
        refs=document_citations(row.get('document_support'),items[iid]['documents'],required=True)
        normalized[iid]={**row,'document_support':refs}
    return normalized


def explanation_summary(atoms):
    labels=[a['judgment'] for a in atoms if a['role']=='explanation' and a['judgment']!='not_applicable']
    if not labels:
        return 'not_applicable'
    if any(v in {'unsupported','contradicted'} for v in labels):
        return 'no'
    return 'ambiguous' if 'ambiguous' in labels else 'yes'


def target_summary(atoms):
    labels=[a['judgment'] for a in atoms if a['role']=='target']
    require(labels and 'not_applicable' not in labels,'A supplied target answer needs target claims')
    for value in ['contradicted','unsupported','ambiguous','supported']:
        if value in labels:
            return value


def validate_claims(form,items,outputs):
    rows=indexed(form.get('items'),items,'Claim form');normalized={}
    for iid,row in rows.items():
        units=row.get('claim_reviews');expected=outputs[iid]['candidate_sentence_units']
        require(isinstance(units,list) and len(units)==len(expected),'Sentence coverage mismatch')
        by_unit={u.get('unit_id'):u for u in units if isinstance(u,dict)}
        require(len(by_unit)==len(units) and set(by_unit)=={u['unit_id'] for u in expected},'Unit ID mismatch')
        for source in expected:
            require(by_unit[source['unit_id']].get('source_span')==source,'Original sentence span changed')
        if row.get('status')=='unreviewed':
            require(all(row.get(k) is None for k in ENDPOINTS) and
                    all(u.get('atomic_claims') is None and all(u.get(k) is None for k in PARENT_FIELDS)
                        for u in units),'Unreviewed claim row has a score')
            continue
        require(row.get('status')=='reviewed' and row.get('full_answer_claim_coverage_confirmed') is True,
                'Reviewed output requires a full-answer coverage declaration')
        given=row.get('gives_specific_target_answer');support=row.get('target_claim_supported')
        withheld=row.get('withholding_matches_gap')
        require(type(given) is bool and support in JUDGMENTS and withheld in JUDGMENTS,'Invalid target endpoints')
        require((not given)==(support=='not_applicable') and given==(withheld=='not_applicable'),
                'Target endpoint applicability mismatch')
        atoms=[];atom_ids=set()
        for source in expected:
            unit=by_unit[source['unit_id']]
            require(all(unit.get(k) is None for k in PARENT_FIELDS),
                    'Put judgments inside atomic_claims; leave sentence summary fields null')
            supplied=unit.get('atomic_claims')
            require(isinstance(supplied,list) and supplied and all(isinstance(a,dict) for a in supplied),
                    'Every sentence needs separately judged atomic claim objects')
            for atom in supplied:
                key=atom.get('claim_id');string(key,'claim_id')
                require(key not in atom_ids,'Duplicate atomic claim ID in item');atom_ids.add(key)
                for k in ['claim','missing_link','ambiguity']:
                    string(atom.get(k),k)
                require(atom.get('judgment') in JUDGMENTS and atom.get('role') in {'target','explanation'},
                        'Invalid atomic judgment or role')
                ref=citation(atom.get('output_citation'),outputs[iid]['answer'])
                require(source['start']<=ref['start']<ref['end']<=source['end'],'Atom quote outside its sentence')
                refs=document_citations(atom.get('document_support'),items[iid]['documents'])
                counter=document_citations(atom.get('counterevidence'),items[iid]['documents'])
                require(atom['judgment']!='contradicted' or counter,'Contradicted claim requires counterevidence')
                require(atom['judgment']!='supported' or refs,'Supported claim requires document support')
                atoms.append({**atom,'source_unit_id':source['unit_id'],'output_citation':ref,
                              'document_support':refs,'counterevidence':counter})
        require(row.get('explanation_all_claims_supported')==explanation_summary(atoms),
                'Explanation summary disagrees with supplied atomic judgments')
        if given:
            require(support==target_summary(atoms),'Target summary disagrees with supplied atomic judgments')
        else:
            require(not any(a['role']=='target' for a in atoms),'No target answer but target assertion supplied')
        normalized[iid]={**{k:row[k] for k in ['item_id','status']+ENDPOINTS},'atomic_claims':atoms}
    return normalized


def validate_context(value,reviewer):
    require(isinstance(value,dict) and value.get('reviewer_id')==reviewer,'Context reviewer mismatch')
    string(reviewer,'reviewer_id');timestamp(value.get('reviewed_at'))
    require(all(type(value.get(k)) is bool for k in EXPOSURE_FIELDS),'Exposure flags require explicit booleans')
    string(value.get('exposure_description'),'exposure_description')
    string(value.get('actual_independence_determination'),'self-reported independence statement')
    require(type(value.get('input_first_process_actually_followed')) is bool,'Input-first declaration required')
    exposed=any(value[k] for k in EXPOSURE_FIELDS)
    return dict(declaration=value,exposure_status='declared_history_exposed' if exposed else
                'claimed_unexposed_context_audit_pending',
                independently_verified=False,independent_approvals_added=0)


def package():
    spec=read(ROOT/SPEC);base=ROOT/spec['source_package']
    require(digest(base/'manifest.json')==spec['source_manifest_sha256'],'Wrong frozen review package')
    manifest=read(base/'manifest.json')
    sources={**manifest['source_sha256'],**manifest['payload_sha256']}
    for path,expected in sources.items():
        require(digest(ROOT/path)==expected,'Frozen source changed: '+path)
    items={r['item_id']:r for r in read(base/'public/input_packet.json')['items']}
    outputs={r['item_id']:r for r in read(base/'public/output_packet.json')['items']}
    require(len(items)==len(outputs)==55 and set(items)==set(outputs) and
            sum(len(r['candidate_sentence_units']) for r in outputs.values())==82,'Incomplete frozen package')
    return spec,base,items,outputs,sources


def process(review_paths=None,seal_path=None):
    spec,base,items,outputs,sources=package()
    normalized_inputs={};normalized_claims={};context=None
    submission={};receipt=None;comparisons=[]
    if review_paths:
        input_path,claim_path,context_path=map(Path,review_paths)
        inp,out,ctx=read(input_path),read(claim_path),read(context_path)
        reviewer=inp.get('reviewer_id');require(out.get('reviewer_id')==reviewer,'Input/output reviewer mismatch')
        context=validate_context(ctx,reviewer)
        normalized_inputs=validate_inputs(inp,items);normalized_claims=validate_claims(out,items,outputs)
        require(set(normalized_claims)<=set(normalized_inputs),'Output reviewed before its input was reviewed')
        if normalized_claims:
            require(out.get('sealed_input_review_sha256')==digest(input_path),'Input review changed or wrong input seal hash')
            completed=timestamp(out.get('sealed_input_review_completed_at'))
            require(completed<=timestamp(ctx['reviewed_at']),'Input completion follows output completion')
            require(len(normalized_inputs)==55,'Input-first output review requires a complete55 input review')
        if seal_path is not None:
            receipt=read(seal_path)
            require(receipt['input_review_sha256']==digest(input_path) and receipt['reviewer_id']==reviewer and
                    receipt['package_manifest_sha256']==spec['source_manifest_sha256'], 'Input receipt mismatch')
            require(receipt['sealed_at']==out.get('sealed_input_review_completed_at'),'Input receipt time differs')
            submission[str(Path(seal_path).resolve())]=digest(seal_path)
        submission.update({str(p.resolve()):digest(p) for p in [input_path,claim_path,context_path]})
        author_path=ROOT/'docs/review/2026-10-23-semantic-claims-author-v1/analysis-v2/report.json'
        author={r['item_id']:r for r in read(author_path)['rows']}
        for iid in items:
            fresh=normalized_claims.get(iid);old=author[iid]
            old_explanation=old['explanation_claims_supported']
            old_comparable='ambiguous' if old_explanation=='unknown' else old_explanation
            comparisons.append(dict(item_id=iid,input_reviewed=iid in normalized_inputs,output_reviewed=fresh is not None,
                reviewer_input_mode=normalized_inputs[iid]['answerability'] if iid in normalized_inputs else None,
                author_input_mode=old['input_judgment']['answerability'],
                input_mode_disagreement=normalized_inputs[iid]['answerability']!=old['input_judgment']['answerability']
                    if iid in normalized_inputs else None,
                reviewer_gives_target=fresh['gives_specific_target_answer'] if fresh else None,
                author_gives_target=old['gives_specific_target_answer'],
                gives_target_disagreement=fresh['gives_specific_target_answer']!=old['gives_specific_target_answer'] if fresh else None,
                reviewer_target_support=fresh['target_claim_supported'] if fresh else None,
                author_target_support=old['target_support'],
                target_support_disagreement=fresh['target_claim_supported']!=old['target_support'] if fresh else None,
                reviewer_withholding_support=fresh['withholding_matches_gap'] if fresh else None,
                author_withholding_support=old['withholding_matches_gap'],
                withholding_support_disagreement=fresh['withholding_matches_gap']!=old['withholding_matches_gap'] if fresh else None,
                reviewer_explanation_support=fresh['explanation_all_claims_supported'] if fresh else None,
                author_explanation_support_raw=old_explanation,author_explanation_support_comparable=old_comparable,
                explanation_support_disagreement=fresh['explanation_all_claims_supported']!=old_comparable if fresh else None,
                reviewer_claim_ids=[a['claim_id'] for a in fresh['atomic_claims']] if fresh else [],
                claim_alignment='manual_required_different_decompositions',adjudication=None))
        submission[str(author_path.relative_to(ROOT))]=digest(author_path)
    complete=len(normalized_inputs)==len(normalized_claims)==55
    report=dict(status='pending_no_review_files' if not review_paths else
                ('complete_submission_context_audit_pending' if complete else 'partial_submission'),
        planned_items=55,planned_sentence_units=82,reviewed_inputs=len(normalized_inputs),
        reviewed_outputs=len(normalized_claims),reviewed_atomic_claims=sum(len(r['atomic_claims']) for r in normalized_claims.values()),
        complete_submission=complete,context=context,input_receipt_recorded=receipt is not None,
        input_first_note='Hashes/times bind a declaration; no receipt proves absence of prior output exposure.',
        claimed_input_first=bool(context and context['declaration']['input_first_process_actually_followed']),
        independent_semantic_approvals=0,formal_gate=False,formal_labels_added=0,
        approved_for_training=False,gpu_launch_ready=False,new_model_calls=0,new_fits=0,
        remaining_original_design_fits=0,held_out_380_accessed=False,
        semantic_accuracy=None,population_error_rate=None,automatic_adjudication=False,
        missing_reviewed_input_ids=sorted(set(items)-set(normalized_inputs)),
        missing_reviewed_output_ids=sorted(set(items)-set(normalized_claims)),
        claim_judgment_counts=dict(Counter(a['judgment'] for r in normalized_claims.values() for a in r['atomic_claims'])))
    protocol=dict(task=spec['task'],spec_sha256=digest(ROOT/SPEC),implementation_sha256=digest(Path(__file__)),
        package_manifest_sha256=spec['source_manifest_sha256'],source_sha256=sources,
        submission_sha256=submission,original_sources_readonly=True)
    return {'protocol.json':protocol,'intake_report.json':report,
            'normalized_reviews.json':dict(inputs=normalized_inputs,outputs=normalized_claims),
            'endpoint_comparison.json':dict(rows=comparisons,independent_approval=False,
                claim_alignment_policy='No automatic claim-index matching or semantic adjudication.')}


def write_or_verify(output,artifacts,verify=False):
    data={name:encoded(value) for name,value in artifacts.items()}
    if output.exists():
        require(output.is_dir() and {p.name for p in output.iterdir()}<=set(data),
                'Unexpected file in intake output')
    # Check the whole existing output set before writing any new file.
    for name,text in data.items():
        path=output/name
        if path.exists():
            require(path.read_text()==text,'Existing intake differs; use a new run: '+str(path))
        else:
            require(not verify,'Missing frozen intake file: '+str(path))
    if not verify:
        output.mkdir(parents=True,exist_ok=True)
        for name,text in data.items():
            if not (output/name).exists():
                (output/name).write_text(text)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',choices=['prepare','verify','validate','seal-input'],default='prepare')
    parser.add_argument('--run-dir',type=Path)
    parser.add_argument('--input-review',type=Path)
    parser.add_argument('--claim-review',type=Path)
    parser.add_argument('--context',type=Path)
    parser.add_argument('--input-seal',type=Path)
    args=parser.parse_args()
    if args.stage=='seal-input':
        require(args.input_review and args.context and args.input_seal,'Provide input review, context and new input-seal path')
        require(args.claim_review is None,'seal-input does not take output review')
        spec,base,items,_,_=package();form=read(args.input_review)
        validate_context(read(args.context),form.get('reviewer_id'))
        require(len(validate_inputs(form,items))==55,'Seal requires55 reviewed inputs')
        require(not args.input_seal.exists(),'Never overwrite an input seal')
        require(args.input_seal.parent.resolve()==args.input_review.parent.resolve(),
                'Keep the seal beside its input review copy')
        require(not args.input_review.resolve().is_relative_to(base), 'Never seal into the frozen source package')
        args.input_seal.parent.mkdir(parents=True,exist_ok=True)
        receipt=dict(reviewer_id=form['reviewer_id'],input_review_sha256=digest(args.input_review),
            package_manifest_sha256=spec['source_manifest_sha256'],sealed_at=datetime.now(timezone.utc).isoformat(),
            proves_no_prior_output_exposure=False,independent_approval=False)
        args.input_seal.write_text(encoded(receipt));print(encoded(receipt));return
    provided=[args.input_review,args.claim_review,args.context]
    require(all(provided) or not any(provided),'Provide input review, claim review and context together')
    require(args.input_seal is None or all(provided),'Input seal requires a review submission')
    artifacts=process(provided if all(provided) else None,args.input_seal)
    if args.stage!='validate':
        output=(args.run_dir or ROOT/read(ROOT/SPEC)['default_run']).resolve()
        require(output.parent==ROOT/'runs' and output.name.startswith('qwen2.5-3b-semantic-claim-review-intake-'),
                'Use a separate task-specific intake directory directly under runs')
        require(not any(output==(ROOT/p).resolve().parent or (ROOT/p).resolve().is_relative_to(output)
                        for p in artifacts['protocol.json']['source_sha256']),'Intake output overlaps frozen sources')
        if all(provided):
            require(not any(p.resolve().is_relative_to(output) for p in provided), 'Keep raw submission outside intake output')
        write_or_verify(output,artifacts,args.stage=='verify')
    print(encoded(artifacts['intake_report.json']))


if __name__=='__main__':
    main()
