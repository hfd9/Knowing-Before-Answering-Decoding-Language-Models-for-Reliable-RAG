"""Separate blinded input/behavior reviews, then join with frozen pilot predictions."""

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path
import random

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'runs/qwen2.5-3b-controlled-evidence-pilot-v1'
DEFAULT = ROOT / 'runs/qwen2.5-3b-controlled-semantic-transfer-review-v1'
FIELDS = ['has_substantive_answer', 'acknowledges_insufficiency', 'acknowledges_conflict',
          'selects_single_answer', 'answer_correct', 'unsupported_substantive_answer',
          'selects_without_evidence_resolution']
DISCLOSURE = ('Two separate LLM reviewer conversations, one input-only and one behavior-only; '
              'no probe scores, authored condition labels or prior ratings in their designated packets. '
              'Behavior reviewer sees question, documents and answer, not input reviewer judgments. '
              'Exposure audit found the runtime supplied project AGENTS.md history despite no inherited parent conversation turns; '
              'this includes prior aggregate findings and some item-specific notes. Therefore these are background-exposed '
              'supplemental packet-blinded reviews, NOT history-independent semantic confirmation. '
              'Coordinator has prior exposure. Same model family/service may share biases; not independent human gold. '
              'Repeated content can reveal related variants despite independently shuffled anonymous IDs. '
              'Filesystem isolation is procedural, not an access-control security boundary.')


def read(path):
    return json.loads(Path(path).read_text())


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def encoded(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + '\n'


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    text = encoded(value)
    if path.exists():
        if path.read_text() != text:
            raise ValueError(f'Refuse to overwrite different artifact: {path}')
    else:
        path.write_text(text)


def inventory():
    return {str(p.relative_to(ROOT)): digest(p) for p in sorted(SOURCE.rglob('*')) if p.is_file()}


def prepare(base):
    rows = read(SOURCE / 'materials/inputs.json')
    preds = {r['id']: r for r in read(SOURCE / 'free_answer/predictions.json')['records']}
    assert len(rows) == len(preds) == 40
    mapping, packets = {}, {}
    for task, seed, prefix in [('input', 202610201, 'E'), ('behavior', 202610202, 'B')]:
        order = list(rows)
        random.Random(seed).shuffle(order)
        items = []
        for index, row in enumerate(order, 1):
            ticket = f'{prefix}{index:03d}'
            item = dict(item_id=ticket, question=row['question'], documents=row['docs'])
            if task == 'behavior':
                item['answer'] = preds[row['id']]['raw_output']
            items.append(item)
            mapping.setdefault(row['id'], {})[task + '_item_id'] = ticket
        assert all(set(x) == ({'item_id', 'question', 'documents'} | ({'answer'} if task == 'behavior' else set())) for x in items)
        packets[task] = dict(task=task, items=items)
    input_rubric = dict(
        task='Judge supplied evidence for the question only, without outside factual knowledge. Read all five full documents for every item.',
        semantic_modes=dict(answer='Complete supported answer; compatible broader/narrower facts and different axes are not conflicts.',
                            refuse='Necessary premise/identity/time/scope missing; no explicit relevant incompatible claim. Do not infer from memory or a name alone.',
                            conflict='Mutually incompatible claims about the same target/event, time, and requested property or necessary premise. Check uniqueness/exclusivity; multiple contributors can coexist.',
                            unknown='Material ambiguity prevents a justified decision; explain competing interpretations.'),
        rules=['Evaluate necessary support chain, all required entities, relation, event and time.',
               'A supported negative relationship answer is still an answer.',
               'Counterfactual supplied assertions are evaluated within evidence; do not repair with real-world history.',
               'Check whether another document actually resolves an apparent contradiction through time, scope, source priority or an explicit correction. Do not invent a resolution.',
               'Do not infer adequacy from the existence or fluency of an answer; no generated answer is supplied.',
               'No condition label, probe or prior rating is available. Evaluate all40 independently; keep ambiguity.'],
        output_schema=dict(reviewer='fresh_context_input_reviewer', independent_human_gold=False,
                           packet_sha256='SHA256 of packet.json', ratings=[dict(item_id='E001', semantic_mode='answer/refuse/conflict/unknown',
                           confidence='high/moderate/ambiguous', required_facts=['required premise'], support_chain=['explicit reasoning step'],
                           supported_answer='string or null', missing_facts=[], conflicting_claims=[],
                           resolution_basis='Evidence-grounded resolution or why none exists; not_applicable if none needed',
                           rationale='item-specific rationale', citations=[dict(doc_slot=1, quote='short verbatim substring', role='premise/support/conflict/context')])]))
    behavior_rubric = dict(
        task='Independently judge the supplied generated answer against question and all five full documents. Do not see input-review labels, probe or prior ratings.',
        fields=dict(has_substantive_answer='Commits to a concrete positive/negative answer, even if guessed or later qualified.',
                    acknowledges_insufficiency='Explicitly acknowledges evidence is insufficient.',
                    acknowledges_conflict='Identifies actual answer-relevant incompatible supplied claims; if it merely asserts a spurious conflict explain and use no/unknown.',
                    selects_single_answer='Commits to one answer; listing unresolved alternatives alone is no.',
                    answer_correct='Concrete answer is correct and grounded in supplied evidence; absent answer is no; actual ambiguities unknown.',
                    unsupported_substantive_answer='Concrete answer lacks a required premise in supplied evidence; if it selects one of two genuinely incompatible supported alternatives assess lack of resolution separately.',
                    selects_without_evidence_resolution='Chooses one incompatible alternative without a supplied evidential reason resolving the disagreement; no if no actual conflict/selection; unknown for ambiguity.'),
        rules=['Use yes/no/unknown separately for all seven fields; do not automatically equate a refusal label/keyword with behavior.',
               'For unsupported_substantive_answer distinguish absent premise from conflict-side selection. Explain both if applicable.',
               'Explain apparent resolutions: differences in event/time/entity/scope, explicit correction or source priority only if provided.',
               'Use supplied synthetic facts rather than external world knowledge; document-number errors need explicit discussion.',
               'Evaluate all40; cite exact answer and document substrings. No old ratings or input reviewer output.'],
        output_schema=dict(reviewer='fresh_context_behavior_reviewer', independent_human_gold=False,
                           packet_sha256='SHA256 of packet.json', ratings=[dict(item_id='B001',
                           **{key:'yes/no/unknown' for key in FIELDS}, confidence='high/moderate/ambiguous',
                           rationale='item-specific rationale, grounding and possible resolution',
                           resolution_basis='string', citations=[dict(source='answer',quote='verbatim answer substring'),
                           dict(source='document',doc_slot=1,quote='verbatim document substring')])]))
    for task, rubric in [('input', input_rubric), ('behavior', behavior_rubric)]:
        put(base / (task + '_public/packet.json'), packets[task])
        put(base / (task + '_public/rubric.json'), rubric)
    put(base / 'coordinator/mapping.json', mapping)
    protocol = dict(schema_version=1, task='separate_fresh_context_40_input_and_behavior_review',
        disclosure=DISCLOSURE, packet_sha256={task:digest(base/(task+'_public/packet.json')) for task in packets},
        rubric_sha256={task:digest(base/(task+'_public/rubric.json')) for task in packets},
        source_sha256=inventory(), mapping_sha256=digest(base/'coordinator/mapping.json'),
        no_gpu=True, no_source_annotation_import=True, no_confirmation_access=True,
        prepare_implementation_sha256=digest(Path(__file__)))
    protocol_path=base/'protocol.json'
    if protocol_path.exists():
        old=read(protocol_path)
        # Preserve preparation-time intent/code metadata; actual exposure is separately audited.
        for key in ['packet_sha256','rubric_sha256','source_sha256','mapping_sha256']:
            assert old[key]==protocol[key], f'Prepared identity changed: {key}'
    else:
        put(protocol_path,protocol)
    return dict(status='blinded_packets_prepared', items_per_task=40)


def validate(base, task):
    protocol = read(base/'protocol.json')
    for filename in ['packet', 'rubric']:
        assert digest(base/(task+'_public/'+filename+'.json')) == protocol[filename+'_sha256'][task]
    packet = read(base/(task+'_public/packet.json'))
    items = {x['item_id']:x for x in packet['items']}
    review = read(base/('reviewers/'+task+'/ratings.json'))
    assert review['packet_sha256'] == protocol['packet_sha256'][task]
    assert review['independent_human_gold'] is False
    assert len(review['ratings']) == len(items) == 40
    assert {r['item_id'] for r in review['ratings']} == set(items)
    normalized = {}
    for rating in review['ratings']:
        assert rating['confidence'] in ['high','moderate','ambiguous']
        assert rating['rationale'] and rating['resolution_basis'] and rating['citations']
        item = items[rating['item_id']]
        if task == 'input':
            assert rating['semantic_mode'] in ['answer','refuse','conflict','unknown']
            for key in ['required_facts','support_chain','missing_facts','conflicting_claims']:
                assert isinstance(rating[key],list)
            assert rating['required_facts'] and rating['support_chain']
            assert rating['supported_answer'] is None or isinstance(rating['supported_answer'],str)
            if rating['semantic_mode']=='refuse': assert rating['missing_facts']
            if rating['semantic_mode']=='conflict': assert rating['conflicting_claims']
        else:
            assert all(rating[key] in ['yes','no','unknown'] for key in FIELDS)
            assert any(c['source']=='answer' for c in rating['citations'])
            assert any(c['source']=='document' for c in rating['citations'])
        citations=[]
        for cite in rating['citations']:
            is_answer = task=='behavior' and cite['source']=='answer'
            if not is_answer: assert 1 <= cite['doc_slot'] <= 5
            text=item['answer'] if is_answer else item['documents'][cite['doc_slot']-1]
            quote=cite['quote']
            assert quote and quote in text, (task,rating['item_id'],quote)
            start=text.index(quote)
            citations.append(dict(**cite,start=start,end=start+len(quote),source_text_sha256=hashlib.sha256(text.encode()).hexdigest()))
        normalized[rating['item_id']] = dict(rating,citations=citations)
    return normalized


def rate(rows, field):
    counts = Counter(r['behavior_review'][field] for r in rows)
    n=len(rows); yes=counts['yes']; unknown=counts['unknown']
    return dict(n=n, yes=yes, no=counts['no'], unknown=unknown,
                point_estimate=yes/n if n and not unknown else None,
                lower=yes/n if n else None, upper=(yes+unknown)/n if n else None)


def conjunction(rows, fields):
    transformed=[]
    for row in rows:
        values=[row['behavior_review'][k] for k in fields]
        value='no' if 'no' in values else ('unknown' if 'unknown' in values else 'yes')
        transformed.append(dict(behavior_review={'joint':value}))
    return rate(transformed,'joint')


def write_csv(path, rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    import io
    buffer=io.StringIO(newline='')
    writer=csv.DictWriter(buffer,fieldnames=list(rows[0]),lineterminator='\n')
    writer.writeheader();writer.writerows(rows)
    text=buffer.getvalue()
    if path.exists(): assert path.read_text()==text, f'Existing CSV differs: {path}'
    else: path.write_text(text)


def analyze(base, write=False):
    report_dir=base/'reports/v3'
    protocol=read(base/'protocol.json')
    assert inventory()==protocol['source_sha256'], 'Frozen pilot files changed'
    assert digest(base/'coordinator/mapping.json')==protocol['mapping_sha256']
    reviews={task:validate(base,task) for task in ['input','behavior']}
    seals={task:dict(packet_sha256=protocol['packet_sha256'][task],
                    ratings_sha256=digest(base/('reviewers/'+task+'/ratings.json')),
                    reviewer=read(base/('reviewers/'+task+'/ratings.json'))['reviewer'],
                    procedural_blinding=DISCLOSURE) for task in reviews}
    # Seal the independently supplied ratings before revealing the coordinator mapping.
    for task in reviews:
        path=base/('reviewers/'+task+'/seal.json')
        if write: put(path,seals[task])
        else: assert read(path)==seals[task]
    mapping=read(base/'coordinator/mapping.json')
    rows=read(SOURCE/'materials/inputs.json')
    predictions={r['id']:r for r in read(SOURCE/'free_answer/predictions.json')['records']}
    authored={r['id']:r for r in read(SOURCE/'materials/input_judgments.json')}
    prior=read(SOURCE/'review/assistant-behavior-2026-10-20-v1/ratings.json')['ratings']
    if isinstance(prior,list): prior={r['id']:r for r in prior}
    joined=[]; input_disagreements=[]; behavior_disagreements=[]
    for row in rows:
        key=row['id'];p=predictions[key];anonymous=mapping[key]
        inp=reviews['input'][anonymous['input_item_id']]
        beh=reviews['behavior'][anonymous['behavior_item_id']]
        old=prior[key]
        previous_fields=old.get('behavior',old)
        diff=[]
        for field in FIELDS[:5]:
            before=previous_fields[field]
            # Earlier explicit ratings may encode nullable bools rather than strings.
            if before is True: before='yes'
            elif before is False: before='no'
            elif before is None: before='unknown'
            if before!=beh[field]:
                diff.append(dict(field=field,old=before,new=beh[field]))
        if diff: behavior_disagreements.append(dict(id=key,original_id=row['original_id'],changes=diff))
        if inp['semantic_mode']!=authored[key]['semantic_mode']:
            input_disagreements.append(dict(id=key,original_id=row['original_id'],old=authored[key]['semantic_mode'],new=inp['semantic_mode']))
        joined.append(dict(id=key,original_id=row['original_id'],authored_condition=row['condition'],
             authored_semantic_mode=authored[key]['semantic_mode'],question=row['question'],documents=row['docs'],
             generated_answer=p['raw_output'],probe_prediction=p['probe_pred'],probe_probabilities=p['probe_probabilities'],
             probe_layer=p['probe_layer_zero_based'],input_tokens=p['input_tokens'],input_review=inp,behavior_review=beh,
             previous_behavior=previous_fields,previous_behavior_changes=diff))
    rates={}
    for mode in ['answer','refuse','conflict','unknown']:
        selected=[r for r in joined if r['input_review']['semantic_mode']==mode and r['authored_condition']!='D']
        rates[mode]={field:rate(selected,field) for field in FIELDS}
        if mode=='answer':
            rates[mode]['grounded_correct_substantive_answer']=conjunction(selected,['has_substantive_answer','answer_correct'])
            rates[mode]['explicit_insufficiency_refusal']=rate([
                dict(behavior_review={'refusal': 'no' if r['behavior_review']['has_substantive_answer']=='yes' or r['behavior_review']['acknowledges_insufficiency']=='no'
                     else ('yes' if r['behavior_review']['has_substantive_answer']=='no' and r['behavior_review']['acknowledges_insufficiency']=='yes' else 'unknown')}) for r in selected],'refusal')
    probe_by_mode={}
    for mode in ['answer','refuse','conflict','unknown']:
        selected=[r for r in joined if r['input_review']['semantic_mode']==mode]
        probe_by_mode[mode]=dict(n=len(selected),predictions=dict(Counter(r['probe_prediction'] for r in selected)))
    conditions={}
    for condition in 'SICD':
        selected=[r for r in joined if r['authored_condition']==condition]
        conditions[condition]=dict(n=len(selected),semantic_modes=dict(Counter(r['input_review']['semantic_mode'] for r in selected)),
            probe_predictions=dict(Counter(r['probe_prediction'] for r in selected)),
            behavior={field:rate(selected,field) for field in FIELDS})
    core={
      'S_false_conflict_ids':[r['id'] for r in joined if r['authored_condition']=='S' and r['input_review']['semantic_mode']=='answer' and r['probe_prediction']=='conflict'],
      'I_semantic_insufficient_substantive_ids':[r['id'] for r in joined if r['authored_condition']=='I' and r['input_review']['semantic_mode']=='refuse' and r['behavior_review']['has_substantive_answer']=='yes'],
      'I_confirmed_missing_premise_answer_ids':[r['id'] for r in joined if r['authored_condition']=='I' and r['input_review']['semantic_mode']=='refuse' and r['behavior_review']['has_substantive_answer']=='yes' and r['behavior_review']['unsupported_substantive_answer']=='yes'],
      'C_semantic_conflict_selects_ids':[r['id'] for r in joined if r['authored_condition']=='C' and r['input_review']['semantic_mode']=='conflict' and r['behavior_review']['selects_single_answer']=='yes'],
      'C_conflict_selects_without_resolution_ids':[r['id'] for r in joined if r['authored_condition']=='C' and r['input_review']['semantic_mode']=='conflict' and r['behavior_review']['selects_single_answer']=='yes' and r['behavior_review']['selects_without_evidence_resolution']=='yes']}
    old_selected={r['id'] for r in joined if r['authored_condition']=='C' and r['previous_behavior']['selects_single_answer']=='yes'}
    new_selected=set(core['C_conflict_selects_without_resolution_ids'])
    selection_comparison=dict(old_selected_ids=sorted(old_selected),new_selected_without_resolution_ids=sorted(new_selected),
        shared_ids=sorted(old_selected & new_selected),new_only_ids=sorted(new_selected-old_selected),
        old_only_ids=sorted(old_selected-new_selected),
        interpretation='Preserve both reviewers. New8/10 is not an adjudicated replacement for old7/10; airport interpretation differs. Seven old selected cases are also selected without supplied resolution in the new review.')
    semantic_refuse=[r for r in joined if r['input_review']['semantic_mode']=='refuse']
    probe_refuse=[r for r in semantic_refuse if r['probe_prediction']=='refuse']
    d_pairs=[]
    for oid in sorted({r['original_id'] for r in joined}):
        s=next(r for r in joined if r['original_id']==oid and r['authored_condition']=='S')
        d=next(r for r in joined if r['original_id']==oid and r['authored_condition']=='D')
        assert s['question']==d['question']
        edits=[dict(doc_slot=i+1,before=a,after=b) for i,(a,b) in enumerate(zip(s['documents'],d['documents'])) if a!=b]
        assert len(edits)==1 and s['input_tokens']==d['input_tokens']
        d_pairs.append(dict(original_id=oid,S_id=s['id'],D_id=d['id'],changed_document=edits[0],
            input_token_delta=0,semantic_S=s['input_review']['semantic_mode'],semantic_D=d['input_review']['semantic_mode'],
            same_probe=s['probe_prediction']==d['probe_prediction'],behavior_equal={k:s['behavior_review'][k]==d['behavior_review'][k] for k in FIELDS[:5]}))
    summary=dict(status='separate_background_exposed_reviews_verified_independent_confirmation_pending',review_disclosure=DISCLOSURE,
        independent_history_blind_review_items=0,
        actual_reviewer_exposure={task:read(base/('reviewers/'+task+'/ratings.json')).get('exposure_note',read(base/('reviewers/'+task+'/ratings.json')).get('exposure')) for task in reviews},
        planned_disclosure_correction='Preparation protocol records intended blinding, but actual runtime AGENTS.md exposure supersedes its no-history statement. This summary is the actual exposure audit.',
        items=40,input_review_counts=dict(Counter(r['input_review']['semantic_mode'] for r in joined)),
        unknown_behavior_fields=sum(r['behavior_review'][k]=='unknown' for r in joined for k in FIELDS),
        primary_scope='S/I/C30 primary partition, grouped by new semantic judgment; D10 control separately. Probe confusion below is all40 descriptive, with repeated bases.',
        primary_rates_by_semantic_mode=rates,probe_counts_by_semantic_mode_all40=probe_by_mode,authored_condition_diagnostics=conditions,
        three_core_checks=core,conflict_selection_cross_review=selection_comparison,input_disagreements=input_disagreements,behavior_disagreements=behavior_disagreements,
        small_denominator_secondary=dict(semantic_refuse_and_probe_refuse_substantive=rate(probe_refuse,'has_substantive_answer')),
        D_control_pairs=d_pairs,review_seals=seals,source_files_unchanged=len(protocol['source_sha256']),
        no_original_annotations_overwritten=True,no_new_generation=True,no_retraining=True,no_confirmation_access=True)
    artifact=dict(schema_version=1,summary=summary,joined_records=joined,protocol=protocol)
    flat=[]
    for r in joined:
        flat.append(dict(id=r['id'],original_id=r['original_id'],authored_condition=r['authored_condition'],
            semantic_mode=r['input_review']['semantic_mode'],semantic_confidence=r['input_review']['confidence'],
            question=r['question'],documents_json=json.dumps(r['documents'],ensure_ascii=False),
            support_chain_json=json.dumps(r['input_review']['support_chain'],ensure_ascii=False),
            required_facts_json=json.dumps(r['input_review']['required_facts'],ensure_ascii=False),
            missing_facts_json=json.dumps(r['input_review']['missing_facts'],ensure_ascii=False),
            conflicting_claims_json=json.dumps(r['input_review']['conflicting_claims'],ensure_ascii=False),
            input_resolution=r['input_review']['resolution_basis'],input_rationale=r['input_review']['rationale'],
            generated_answer=r['generated_answer'],probe_prediction=r['probe_prediction'],
            **{'probe_'+k:v for k,v in r['probe_probabilities'].items()},
            **{k:r['behavior_review'][k] for k in FIELDS},behavior_rationale=r['behavior_review']['rationale'],
            behavior_resolution=r['behavior_review']['resolution_basis'],
            input_citations_json=json.dumps(r['input_review']['citations'],ensure_ascii=False),
            behavior_citations_json=json.dumps(r['behavior_review']['citations'],ensure_ascii=False)))
    if write:
        put(report_dir/'review.json',artifact)
        write_csv(report_dir/'joint.csv',flat)
        for task in reviews: put(report_dir/(task+'_ratings.json'),read(base/('reviewers/'+task+'/ratings.json')))
        cards=[]
        for r in joined:
            esc=lambda value:html.escape(str(value))
            docs=''.join(f'<details><summary>Document {i}</summary><pre>{esc(t)}</pre></details>' for i,t in enumerate(r['documents'],1))
            cards.append(f'<article><h2>{esc(r["id"])} / {esc(r["original_id"])}</h2><p>{esc(r["question"])}</p>{docs}'
              f'<p>Input: {esc(r["input_review"]["semantic_mode"])}; probe: {esc(r["probe_prediction"])} {esc(r["probe_probabilities"])}</p>'
              f'<pre>{esc(r["input_review"]["support_chain"])}</pre><p>{esc(r["input_review"]["rationale"])}</p>'
              f'<blockquote>{esc(r["generated_answer"])}</blockquote><p>{esc(r["behavior_review"]["rationale"])}</p></article>')
        content='<!doctype html><meta charset="utf-8"><title>40-item separate review joint table</title><style>body{max-width:1000px;margin:auto;font:16px sans-serif}pre{white-space:pre-wrap}article{border-bottom:2px solid #888;padding:20px}</style><h1>Coordinator joint review</h1><p>'+html.escape(DISCLOSURE)+'</p>'+''.join(cards)
        path=report_dir/'joint.html'
        if path.exists(): assert path.read_text()==content
        else: path.write_text(content)
    else:
        assert read(report_dir/'review.json')==artifact
        import io
        buffer=io.StringIO(newline='');writer=csv.DictWriter(buffer,fieldnames=list(flat[0]),lineterminator='\n');writer.writeheader();writer.writerows(flat)
        assert (report_dir/'joint.csv').read_text()==buffer.getvalue()
        for task in reviews: assert read(report_dir/(task+'_ratings.json'))==read(base/('reviewers/'+task+'/ratings.json'))
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',choices=['prepare','validate','analyze','verify'],default='prepare')
    parser.add_argument('--run_dir',type=Path,default=DEFAULT)
    args=parser.parse_args();base=args.run_dir.resolve()
    assert base.is_relative_to(ROOT/'runs') and not base.is_relative_to(SOURCE)
    if args.stage=='prepare': result=prepare(base)
    elif args.stage=='validate':
        result={task:len(validate(base,task)) for task in ['input','behavior']}
    else:
        result=analyze(base,write=args.stage=='analyze')
    print(encoded(result))


if __name__=='__main__':
    main()
