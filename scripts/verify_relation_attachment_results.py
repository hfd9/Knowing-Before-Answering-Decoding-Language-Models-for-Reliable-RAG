"""Independent counts, citations, primary arithmetic and raw-token replay; no model."""
from collections import Counter
import csv
from datetime import datetime,timedelta
from fractions import Fraction
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
P='docs/records/2026-10-23-relation-attachment-results'
RUN='runs/qwen2.5-3b-relation-attachment-v1'


def read(p):
    return json.loads((ROOT/p).read_text())


def digest(p):
    return hashlib.sha256((ROOT/p).read_bytes()).hexdigest()


def check(ok,message):
    if not ok:
        raise ValueError(message)


def csv_rows(p):
    with (ROOT/p).open(newline='') as f:
        return list(csv.DictReader(f))


def main():
    report=read(P+'.json')
    for p,h in {**read(P+'-preserved.json'),**report['source_sha256']}.items():
        check(digest(p)==h,'Source changed: '+p)
    expected=read(P+'-source-run-hashes.json')
    actual={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (ROOT/RUN).rglob('*') if p.is_file() and p.name!='.run.lock'}
    check(actual==expected,'Original run changed')
    manual=read(P+'-manual.json');seal=read(P+'-judgment-seal.json')
    check(digest(P+'-manual.json')==seal['manual_sha256'],'Manual judgment seal differs')
    fields=manual['field_order']
    m={r['item_id']:r for r in manual['ratings']}
    packet={r['item_id']:r for r in read(RUN+'/behavior_review/packet.json')['items']}
    mapping=read(RUN+'/coordinator/behavior_mapping.json')
    expanded={r['item_id']:r for r in read(P+'-ratings.json')['ratings']}
    cells=csv_rows(P+'-cells.csv');by_id={r['id']:r for r in cells}
    material={r['id']:r for r in read(RUN+'/materials/inputs.json')}
    records=read(RUN+'/predictions.json')['records']
    pred={r['id']:r for r in records}
    check(len(cells)==len(by_id)==len(m)==len(expanded)==len(pred)==len(material)==48,'Incomplete48')
    def citation(text,c):
        check(c['quote']==text[c['start']:c['end']]
              and c['text_sha256']==hashlib.sha256(text.encode()).hexdigest(),'Citation mismatch')
    input_refs=0
    for key,row in by_id.items():
        item=packet[mapping[key]];hand=m[mapping[key]];rating=expanded[mapping[key]]
        check(row['question']==item['question']==material[key]['question']
              and item['documents']==material[key]['docs']
              and row['raw_output']==item['answer']==pred[key]['raw_output'],'Input/output join differs')
        check(row['condition']==material[key]['condition'] and row['variant']==material[key]['variant'],'Metadata differs')
        for i,f in enumerate(fields):
            value={'Y':'yes','N':'no','U':'unknown'}[hand['codes'][i]]
            check(row[f]==rating[f]==value,'Handwritten field differs')
        check([c['document_index'] for c in rating['input_citations']]==hand['input_document_indices'],'Input references changed')
        for c in rating['input_citations']:
            citation(item['documents'][c['document_index']-1],c);input_refs+=1
        check(len(rating['output_citations'])==1,'Missing full output citation')
        citation(item['answer'],rating['output_citations'][0])
    def verify_group(rows,summary):
        check(len(rows)==summary['rows'],'Group denominator differs')
        for f in fields:
            c=Counter(r[f] for r in rows);n=len(rows);got=summary['fields'][f]
            check((got['eligible'],got['yes'],got['no'],got['unknown'])==(n,c['yes'],c['no'],c['unknown']), 'Group counts differ')
            check(got['point']==(c['yes']/n if n and not c['unknown'] else None),'Group point differs')
            check(got['identification_lower']==c['yes']/n
                  and got['identification_upper']==(c['yes']+c['unknown'])/n,'Identification bounds differ')
    verify_group(cells,report['all'])
    for condition in ['TQ','OQ','TA','OA']:
        verify_group([r for r in cells if r['condition']==condition],report['by_condition'][condition])
    verify_group([r for r in cells if r['condition']!='TQ'],report['all_insufficient'])
    pair_rows=csv_rows(P+'-primary-pairs.csv');scenes=csv_rows(P+'-scenarios.csv')
    check(len(pair_rows)==12 and len(scenes)==6,'Wrong primary denominator')
    bounds={'yes':(1,1),'no':(0,0),'unknown':(0,1)}
    all_lows=[];all_highs=[];all_points=[]
    for scene in scenes:
        low=[];high=[];point=[]
        for v in ['v1','v2']:
            sid=scene['scenario'];a=by_id[f'{sid}_TA_{v}'];b=by_id[f'{sid}_OA_{v}']
            field='adopts_displayed_candidate_as_requested_target_value'
            al,ah=bounds[a[field]];bl,bh=bounds[b[field]]
            p=next(x for x in pair_rows if x['scenario']==sid and x['variant']==v)
            check(p['TA_id']==a['id'] and p['OA_id']==b['id'],'Pair endpoint differs')
            check(float(p['identification_lower'])==al-bh and float(p['identification_upper'])==ah-bl,'Pair bounds differ')
            low.append(al-bh);high.append(ah-bl)
            value=None if 'unknown' in [a[field],b[field]] else al-bl
            check((p['difference_point']=='' if value is None else float(p['difference_point'])==value),'Pair point differs')
            point.append(value)
        lo=Fraction(sum(low),2);hi=Fraction(sum(high),2)
        po=Fraction(sum(point),2) if all(x is not None for x in point) else None
        check(float(scene['identification_lower'])==float(lo) and float(scene['identification_upper'])==float(hi),'Scene bounds differ')
        check((scene['primary_point']=='' if po is None else float(scene['primary_point'])==float(po)),'Scene point differs')
        all_lows.append(lo);all_highs.append(hi);all_points.append(po)
    check(report['primary']['identification_lower']==float(sum(all_lows)/6)
          and report['primary']['identification_upper']==float(sum(all_highs)/6),'Overall bounds differ')
    overall=float(sum(all_points)/6) if all(x is not None for x in all_points) else None
    check(report['primary']['point']==overall,'Overall point differs')
    for note in report['posthoc_qualitative_notes']:
        citation(packet[note['item_id']]['answer'],note['output_citation'])
    check(Counter(n['kind'] for n in report['posthoc_qualitative_notes'])==report['posthoc_note_counts'],'Note count differs')
    unknown=sum(r[f]=='unknown' for r in cells for f in fields)
    check(unknown==report['unknown_fields']==46 and report['determinate_fields']==194,'Field certainty differs')
    protocol=read(RUN+'/protocol.json')
    from transformers import AutoTokenizer
    tok=AutoTokenizer.from_pretrained(protocol['model'],local_files_only=True)
    for r in records:
        check(tok.decode(r['generated_token_ids'],skip_special_tokens=True)==r['raw_output'],'Raw token decode differs')
    check(sum(r['generated_tokens'] for r in records)==2073
          and sum(r['input_tokens'] for r in records)==12816,'Token totals differ')
    first=datetime.fromisoformat(records[0]['completed_at'])-timedelta(seconds=records[0]['elapsed_seconds'])
    last=datetime.fromisoformat(records[-1]['completed_at'])
    check(report['timing']['generation_elapsed_seconds_sum']==sum(r['elapsed_seconds'] for r in records)
          and report['timing']['approximate_first_inference_to_last_record_seconds']==(last-first).total_seconds(),'Timing differs')
    print(json.dumps(dict(status='independent_numeric_citation_and_raw_token_verification_passed',
        independent_semantic_review=False,rows=48,fields=240,input_citations=input_refs,
        full_output_citations=48,unknown_fields=unknown,primary_pairs=12,scenarios=6,
        primary_difference=overall,maximum_count_and_primary_error=0,posthoc_conflict_notes=3,
        raw_outputs_decoded=48,preserved_old_paths=len(read(P+'-preserved.json')),source_run_files=len(actual),
        new_gpu_calls=0,new_fits=0,implementation_sha256=digest('scripts/verify_relation_attachment_results.py')),
        ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
