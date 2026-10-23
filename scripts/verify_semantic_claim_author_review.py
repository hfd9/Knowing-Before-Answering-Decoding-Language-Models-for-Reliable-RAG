"""Independent arithmetic/reference replay of the saved author review, not a semantic reviewer."""
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/review/2026-10-23-semantic-claims-author-v1'
PACKAGE=ROOT/'docs/review/2026-10-23-semantic-claims-v1'


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(ok,message):
    if not ok:
        raise ValueError(message)


def combine(values):
    if not values:
        return 'not_applicable'
    if any(v in ['unsupported','contradicted'] for v in values):
        return 'no'
    return 'unknown' if any(v=='ambiguous' for v in values) else 'yes'


def main():
    report=read(BASE/'analysis-v2/report.json')
    for name,expected in report['source_sha256'].items():
        check(sha(ROOT/name)==expected,'Frozen source hash mismatch: '+name)
    source_inputs=read(PACKAGE/'public/input_packet.json')['items']
    inputs={i['item_id']:i for i in source_inputs}
    outputs={i['item_id']:i for i in read(PACKAGE/'public/output_packet.json')['items']}
    input_manual=read(BASE/'input-manual.json')
    input_rows={r[0]:r for r in input_manual['rows']}
    raw={}
    for path in sorted(BASE.glob('output-manual-part*.json')):
        for key,row in read(path)['items'].items():
            check(key not in raw,'Duplicate manual item');raw[key]=row
    amendments={a['claim_id']:a for a in read(BASE/'judgment-addendum.json')['amendments']}
    rows={r['item_id']:r for r in report['rows']}
    claims={c['claim_id']:c for c in report['claims']}
    check(len(rows)==len(raw)==len(inputs)==len(input_rows)==55 and len(claims)==155,'Wrong review size')
    check(set(rows)==set(raw)==set(inputs)==set(input_rows),'Review ID mismatch')
    evidence_count=0;covered_units=set();expected_labels=[]
    for iid,manual in raw.items():
        row=rows[iid];inp=inputs[iid];out=outputs[iid]
        expected_input=dict(zip(input_manual['field_order'],input_rows[iid]))
        check(row['input_judgment']==expected_input,'Input judgment mismatch')
        check(row['answer']==out['answer'] and row['question']==inp['question'],'Raw text mismatch')
        target=manual['target']
        check([row[k] for k in ['gives_specific_target_answer','target_support','withholding_matches_gap']]==target,
              'Handwritten target endpoint mismatch')
        item_claims=[]
        for n,original in enumerate(manual['claims'],1):
            unit_number,anchor,proposition,label,docs,gap,ambiguity,role=original
            cid=f'{iid}_C{n:02d}'
            if cid in amendments:
                a=amendments[cid];check(label==a['old_judgment'],'Old amendment value mismatch')
                label,gap,ambiguity=a['new_judgment'],a['missing_link'],a['ambiguity']
            c=claims[cid]
            check([c[k] for k in ['claim','judgment','role','missing_link','ambiguity']]==
                  [proposition,label,role,gap,ambiguity],'Manual claim mismatch: '+cid)
            ref=c['output_reference'];text=out['answer']
            unit=out['candidate_sentence_units'][unit_number-1]
            check(ref['quote']==anchor==text[ref['start']:ref['end']] and
                  ref['text_sha256']==hashlib.sha256(text.encode()).hexdigest() and
                  unit['start']<=ref['start']<ref['end']<=unit['end'],'Claim span mismatch')
            check([r['document_index'] for r in c['document_support']]==docs,'Evidence list mismatch')
            for ref in c['document_support']:
                doc=inp['documents'][ref['document_index']-1]
                check(doc[ref['start']:ref['end']]==ref['quote'] and
                      ref['text_sha256']==hashlib.sha256(doc.encode()).hexdigest(),'Document citation mismatch')
                evidence_count+=1
            covered_units.add((iid,unit['unit_id']));expected_labels.append(label);item_claims.append(c)
        check(row['claim_count']==len(item_claims),'Item claim count mismatch')
        check(row['all_claims_supported']==combine([c['judgment'] for c in item_claims]),'All-claim reduction mismatch')
        check(row['explanation_claims_supported']==combine([c['judgment'] for c in item_claims if c['role']!='target']),
              'Explanation reduction mismatch')
    check(len(covered_units)==82,'Sentence unit coverage mismatch')
    check(dict(Counter(expected_labels))==report['claim_judgment_counts'],'Claim counts mismatch')
    check(dict(Counter(r[1] for r in input_rows.values()))==report['input_judgment_counts'],'Input counts mismatch')
    check(dict(Counter(r['target_support'] for r in rows.values()))==report['target_support_counts'],'Target counts mismatch')
    for group,summary in report['groups'].items():
        selected=[r for r in rows.values() if r['source_group']==group]
        check(summary['items']==len(selected) and summary['target_given']==sum(r['gives_specific_target_answer'] for r in selected),
              'Group size mismatch')
        for field in ['target_support','all_claims_supported','explanation_claims_supported']:
            check(summary[field]==dict(Counter(r[field] for r in selected)),'Group field mismatch')
    for filename,key in [('rows.csv','item_id'),('claims.csv','claim_id')]:
        with (BASE/'analysis-v2'/filename).open(newline='') as f:
            saved=list(csv.DictReader(f))
        originals=rows if key=='item_id' else claims
        check(len(saved)==len(originals) and len({r[key] for r in saved})==len(saved),'CSV set mismatch')
        for r in saved:
            for name,value in r.items():
                original=originals[r[key]][name]
                expected=json.dumps(original,ensure_ascii=False) if isinstance(original,(list,dict)) else str(original)
                check(value==expected,'CSV content mismatch')
    manifest=read(PACKAGE/'manifest.json')
    check(all(sha(ROOT/p)==h for p,h in manifest['payload_sha256'].items()),'Original public/coordinator package changed')
    check(report['independent_semantic_approvals']==0 and report['formal_gate'] is False and
          report['new_fits']==report['new_model_calls']==report['formal_labels_added']==0,
          'Review boundary changed')
    verification=dict(status='author_review_arithmetic_and_reference_verified_not_independent_semantic_approval',
        verifier_sha256=sha(Path(__file__)),current_report_sha256=sha(BASE/'analysis-v2/report.json'),
        source_files_unchanged=len(report['source_sha256']),items=55,claim_instances=155,
        sentence_units_covered=82,document_slots=275,document_citation_instances=evidence_count,
        claim_counts=report['claim_judgment_counts'],input_counts=report['input_judgment_counts'],
        original_package_payloads_unchanged=len(manifest['payload_sha256']),judgment_addenda=1,
        independent_semantic_approvals=0,new_model_calls=0,new_fits=0,held_out_380_accessed=False,
        checks=['manual155 plus explicit addendum','raw55 questions/answers','82 sentence coverage',
                'output and document citations','55 target endpoints','group reductions','CSV exact fields',
                'all sealed source hashes','original independent package unchanged'])
    print(json.dumps(verification,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
