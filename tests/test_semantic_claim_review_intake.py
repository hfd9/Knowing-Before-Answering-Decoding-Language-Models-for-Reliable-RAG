"""Synthetic provenance/citation adversarial checks; these fixtures are not reviewer evidence."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import semantic_claim_review_intake as intake


def ref(text,slot=None):
    r=dict(start=0,end=len(text),quote=text,text_sha256=hashlib.sha256(text.encode()).hexdigest())
    if slot is not None:
        r['document_index']=slot
    return r


def fixture(count=1):
    docs=['Unit T has code C-1.','Unit U has code C-2.','Each unit has one code.',
          'Archive page one.','No year is recorded.']
    answer='Unit T has code C-1. There is a conflict.'
    split=answer.index('There');sentences=[(0,split),(split,len(answer))]
    units=[dict(unit_id=f'U{n}',start=a,end=b,quote=answer[a:b],
                text_sha256=hashlib.sha256(answer.encode()).hexdigest()) for n,(a,b) in enumerate(sentences,1)]
    items={f'Q{n:03d}':dict(item_id=f'Q{n:03d}',question='What code is assigned to Unit T?',documents=docs)
           for n in range(1,count+1)}
    outputs={iid:dict(item_id=iid,answer=answer,candidate_sentence_units=units) for iid in items}
    input_rows=[];claim_rows=[]
    for iid in items:
        input_rows.append(dict(item_id=iid,status='reviewed',target_interpretation='The code of T',
            answerability='answerable',candidate_answer='C-1',document_support=[ref(docs[0],1)],
            missing_link='None under supplied text.',ambiguity='No ambiguity in this synthetic test.',
            conflicting_propositions=[]))
        review_units=[]
        for n,u in enumerate(units):
            anchor=dict(start=u['start'],end=u['end'],quote=u['quote'],text_sha256=u['text_sha256'])
            atom=dict(claim_id=f'C{n+1}',claim='Synthetic supported code' if n==0 else 'Synthetic conflict assertion',
                judgment='supported' if n==0 else 'unsupported',role='target' if n==0 else 'explanation',
                output_citation=anchor,document_support=[ref(docs[0],1)] if n==0 else [],
                counterevidence=[],missing_link='No missing link.' if n==0 else 'No incompatible code pair.',
                ambiguity='Synthetic fixture only, not actual semantic evidence.')
            review_units.append(dict(unit_id=u['unit_id'],source_span=u,atomic_claims=[atom],
                                     **{k:None for k in intake.PARENT_FIELDS}))
        claim_rows.append(dict(item_id=iid,status='reviewed',gives_specific_target_answer=True,
            target_claim_supported='supported',withholding_matches_gap='not_applicable',
            explanation_all_claims_supported='no',full_answer_claim_coverage_confirmed=True,
            claim_reviews=review_units))
    inp=dict(reviewer_id='synthetic_fixture_not_reviewer',items=input_rows)
    out=dict(reviewer_id=inp['reviewer_id'],sealed_input_review_sha256='placeholder',
             sealed_input_review_completed_at='2026-01-01T00:00:00+00:00',items=claim_rows)
    context=dict(reviewer_id=inp['reviewer_id'],reviewed_at='2026-01-02T00:00:00+00:00',
        **{k:True for k in intake.EXPOSURE_FIELDS},exposure_description='Synthetic test fixture, not independent evidence.',
        input_first_process_actually_followed=False,actual_independence_determination='Synthetic exposed fixture only.')
    return items,outputs,inp,out,context


class IntakeTests(unittest.TestCase):
    def test_supplied_blank_templates_remain_unreviewed(self):
        base=ROOT/'docs/review/2026-10-23-semantic-claims-v1/public'
        items={r['item_id']:r for r in intake.read(base/'input_packet.json')['items']}
        outputs={r['item_id']:r for r in intake.read(base/'output_packet.json')['items']}
        self.assertEqual(intake.validate_inputs(intake.read(base/'input_review_template.json'),items),{})
        self.assertEqual(intake.validate_claims(intake.read(base/'claim_review_template.json'),items,outputs),{})

    def test_target_and_explanation_can_have_different_support(self):
        items,outputs,inp,out,_=fixture()
        self.assertEqual(len(intake.validate_inputs(inp,items)),1)
        result=intake.validate_claims(out,items,outputs)['Q001']
        self.assertEqual(result['target_claim_supported'],'supported')
        self.assertEqual(result['explanation_all_claims_supported'],'no')
        self.assertEqual(len(result['atomic_claims']),2)

    def test_duplicate_missing_and_extra_ids_rejected(self):
        items,outputs,inp,out,_=fixture()
        for mutate in [lambda r:r['items'].clear(),lambda r:r['items'].append(copy.deepcopy(r['items'][0])),
                       lambda r:r['items'][0].update(item_id='other')]:
            value=copy.deepcopy(inp);mutate(value)
            with self.assertRaises(ValueError):intake.validate_inputs(value,items)
            value=copy.deepcopy(out);mutate(value)
            with self.assertRaises(ValueError):intake.validate_claims(value,items,outputs)

    def test_wrong_quotes_offsets_hashes_and_boolean_slots_rejected(self):
        items,_,inp,_,_=fixture()
        for values in [dict(quote='invented'),dict(end=1),dict(start=True),dict(document_index=True),
                       dict(text_sha256='wrong')]:
            value=copy.deepcopy(inp);value['items'][0]['document_support'][0].update(values)
            with self.assertRaises(ValueError):intake.validate_inputs(value,items)

    def test_conflict_requires_two_propositions_and_ambiguity_is_preserved(self):
        items,_,inp,_,_=fixture();value=copy.deepcopy(inp)
        value['items'][0].update(answerability='conflict',conflicting_propositions=['one'])
        with self.assertRaisesRegex(ValueError,'two distinct propositions'):intake.validate_inputs(value,items)
        value['items'][0]['conflicting_propositions']=['one',' ONE ']
        with self.assertRaisesRegex(ValueError,'two distinct propositions'):intake.validate_inputs(value,items)
        value['items'][0].update(answerability='ambiguous',candidate_answer=None,conflicting_propositions=[])
        self.assertEqual(intake.validate_inputs(value,items)['Q001']['answerability'],'ambiguous')

    def test_incomplete_rows_cannot_hide_filled_scores(self):
        items,outputs,inp,out,_=fixture()
        inp['items'][0]['status']='unreviewed'
        out['items'][0]['status']='unreviewed'
        with self.assertRaisesRegex(ValueError,'Unreviewed input'):intake.validate_inputs(inp,items)
        with self.assertRaisesRegex(ValueError,'Unreviewed claim'):intake.validate_claims(out,items,outputs)

    def test_parent_summary_and_omitted_sentence_rejected(self):
        items,outputs,_,out,_=fixture()
        value=copy.deepcopy(out);value['items'][0]['claim_reviews'][0]['judgment']='supported'
        with self.assertRaisesRegex(ValueError,'atomic_claims'):intake.validate_claims(value,items,outputs)
        value=copy.deepcopy(out);value['items'][0]['claim_reviews'].pop()
        with self.assertRaisesRegex(ValueError,'Sentence coverage'):intake.validate_claims(value,items,outputs)
        value=copy.deepcopy(out);value['items'][0]['claim_reviews'][0]['atomic_claims']=['a sentence']
        with self.assertRaisesRegex(ValueError,'atomic claim objects'):intake.validate_claims(value,items,outputs)

    def test_duplicate_claim_ids_and_quote_outside_unit_rejected(self):
        items,outputs,_,out,_=fixture();value=copy.deepcopy(out)
        value['items'][0]['claim_reviews'][1]['atomic_claims'][0]['claim_id']='C1'
        with self.assertRaisesRegex(ValueError,'Duplicate atomic'):intake.validate_claims(value,items,outputs)
        value=copy.deepcopy(out)
        value['items'][0]['claim_reviews'][1]['atomic_claims'][0]['output_citation']=value['items'][0]['claim_reviews'][0]['atomic_claims'][0]['output_citation']
        with self.assertRaisesRegex(ValueError,'outside its sentence'):intake.validate_claims(value,items,outputs)

    def test_counterevidence_and_summary_consistency_required(self):
        items,outputs,_,out,_=fixture();value=copy.deepcopy(out)
        value['items'][0]['claim_reviews'][1]['atomic_claims'][0]['judgment']='contradicted'
        with self.assertRaisesRegex(ValueError,'counterevidence'):intake.validate_claims(value,items,outputs)
        for field,val in [('explanation_all_claims_supported','yes'),('target_claim_supported','unsupported'),
                          ('withholding_matches_gap','supported'),('full_answer_claim_coverage_confirmed',False)]:
            value=copy.deepcopy(out);value['items'][0][field]=val
            with self.assertRaises(ValueError):intake.validate_claims(value,items,outputs)

    def test_context_declaration_never_becomes_verified_independence(self):
        _,_,inp,_,ctx=fixture()
        result=intake.validate_context(ctx,inp['reviewer_id'])
        self.assertEqual(result['exposure_status'],'declared_history_exposed')
        for k in intake.EXPOSURE_FIELDS:ctx[k]=False
        ctx['actual_independence_determination']='I claim independent status.'
        result=intake.validate_context(ctx,inp['reviewer_id'])
        self.assertEqual(result['exposure_status'],'claimed_unexposed_context_audit_pending')
        self.assertFalse(result['independently_verified']);self.assertEqual(result['independent_approvals_added'],0)
        ctx[intake.EXPOSURE_FIELDS[0]]=None
        with self.assertRaisesRegex(ValueError,'booleans'):intake.validate_context(ctx,inp['reviewer_id'])

    def test_input_hash_and_time_and_complete_submission_no_approval(self):
        items,outputs,inp,out,ctx=fixture(55)
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);ip,op,cp=[folder/n for n in ['input.json','claims.json','context.json']]
            ip.write_text(intake.encoded(inp));out['sealed_input_review_sha256']=intake.digest(ip)
            op.write_text(intake.encoded(out));cp.write_text(intake.encoded(ctx))
            fake=(dict(task='synthetic test',source_manifest_sha256='test_only'),folder,items,outputs,{})
            with patch.object(intake,'package',return_value=fake):
                result=intake.process([ip,op,cp])
                report=result['intake_report.json']
                self.assertTrue(report['complete_submission']);self.assertEqual(report['reviewed_atomic_claims'],110)
                self.assertFalse(report['gpu_launch_ready']);self.assertEqual(report['independent_semantic_approvals'],0)
                self.assertTrue(all(r['adjudication'] is None for r in result['endpoint_comparison.json']['rows']))
                compared={r['item_id']:r for r in result['endpoint_comparison.json']['rows']}
                self.assertEqual(compared['Q008']['author_explanation_support_raw'],'unknown')
                self.assertEqual(compared['Q008']['author_explanation_support_comparable'],'ambiguous')
                self.assertTrue(compared['Q008']['explanation_support_disagreement'])
                out['sealed_input_review_sha256']='changed';op.write_text(intake.encoded(out))
                with self.assertRaisesRegex(ValueError,'Input review changed'):intake.process([ip,op,cp])
                out['sealed_input_review_sha256']=intake.digest(ip)
                out['sealed_input_review_completed_at']='2026-01-03T00:00:00+00:00';op.write_text(intake.encoded(out))
                with self.assertRaisesRegex(ValueError,'follows output'):intake.process([ip,op,cp])

    def test_write_preflight_and_verify_do_not_mutate_existing_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);intake.write_or_verify(folder,{'one.json':dict(value=1)})
            before=(folder/'one.json').read_bytes()
            with self.assertRaises(ValueError):intake.write_or_verify(folder,{'one.json':dict(value=2),'two.json':{}})
            self.assertEqual((folder/'one.json').read_bytes(),before);self.assertFalse((folder/'two.json').exists())
            intake.write_or_verify(folder,{'one.json':dict(value=1)},verify=True)
            (folder/'extra.json').write_text('{}')
            with self.assertRaisesRegex(ValueError,'Unexpected file'):intake.write_or_verify(folder,{'one.json':dict(value=1)},verify=True)

    def test_real_pending_package_retains55_and_all_null_rates(self):
        result=intake.process();report=result['intake_report.json']
        self.assertEqual(report['status'],'pending_no_review_files')
        self.assertEqual(report['planned_items'],55);self.assertEqual(len(report['missing_reviewed_input_ids']),55)
        self.assertEqual(report['reviewed_atomic_claims'],0);self.assertIsNone(report['semantic_accuracy'])
        self.assertIsNone(report['population_error_rate']);self.assertEqual(result['normalized_reviews.json'],dict(inputs={},outputs={}))
        self.assertFalse(report['formal_gate']);self.assertFalse(report['gpu_launch_ready'])

    def test_input_seal_command_binds_bytes_without_claiming_independence(self):
        items,outputs,inp,_,ctx=fixture(55)
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);ip=folder/'input.json';cp=folder/'context.json';sp=folder/'seal.json'
            ip.write_text(intake.encoded(inp));cp.write_text(intake.encoded(ctx))
            fake=(dict(task='synthetic test',source_manifest_sha256='test_only'),folder/'frozen',items,outputs,{})
            argv=['intake','--stage','seal-input','--input-review',str(ip),'--context',str(cp),'--input-seal',str(sp)]
            import io
            with patch.object(intake,'package',return_value=fake),patch.object(sys,'argv',argv),patch('sys.stdout',new_callable=io.StringIO):
                intake.main();seal=intake.read(sp)
                self.assertEqual(seal['input_review_sha256'],intake.digest(ip))
                self.assertFalse(seal['proves_no_prior_output_exposure']);self.assertFalse(seal['independent_approval'])
                with self.assertRaisesRegex(ValueError,'Never overwrite'):intake.main()

    def test_cli_refuses_old_collection_output_path(self):
        folder=ROOT/'runs/qwen2.5-3b-relation-attachment-v1'
        before={p.name for p in folder.iterdir()}
        with patch.object(sys,'argv',['intake','--run-dir',str(folder)]):
            with self.assertRaisesRegex(ValueError,'task-specific'):intake.main()
        self.assertEqual(before,{p.name for p in folder.iterdir()})


if __name__=='__main__':
    unittest.main()
