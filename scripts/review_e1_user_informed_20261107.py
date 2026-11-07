"""Saved, history-exposed assistant judgments for the 48 E1-user answers; no model calls.

The declarations below are hand-authored after reading each entire input and output.
The script only attaches exact sentence and document offsets and formats those declarations.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import explanation_scope_e1_intake as intake
import explanation_scope_metrics as metrics

BASE = ROOT / 'docs/review/2026-11-07-e1-user-results-v1'
PACKET = BASE / 'public/packet.json'
SEALED = BASE / 'review-sealed'
COORDINATOR = BASE / 'coordinator/coordinator.json'

# (sentence index, role, judgment, cited document slots, atomic claim, reason)
# Whole-sentence spans are intentionally reused when a sentence contains multiple claims.
def c(n, role, verdict, docs, claim, reason):
    return (n, role, verdict, docs, claim, reason)

MISSING = 'No supplied assignment fixes the requested entity and field; the common rule permits separate fields.'
PICK_CONFLICT = 'Two different records concern the target field and there is no priority; the definite selection is not justified.'
ONE_RECORD = 'The specified target value is supported by the single target record, relative to supplied records.'
OTHER_FIELD = 'The cited value belongs to the other field; field independence does not determine the requested value.'
UNRESOLVED = 'The final sentence explicitly declines to determine one value despite the earlier unqualified opening.'
NO_CODE = 'The phrase may mean no supplied assignment or assert that no value exists; the next sentence scopes it to records.'

CLAIMS = {
'R001':[c(0,'target','unsupported',[1,2,3],'The requested omega code is VX-81061.',PICK_CONFLICT),c(1,'explanation','supported',[3],'Document 3 reports VX-81061 for the target.','The cited record states that value.')],
'R002':[c(0,'target','supported',[2,3,4,5],'The records do not assign the target omega code.',MISSING),c(1,'explanation','supported',[2,3,4,5],'The target has an alpha record but no omega assignment.',MISSING)],
'R003':[c(0,'target','ambiguous',[1,2,3,4,5],'No target omega code is assigned.',NO_CODE),c(1,'explanation','supported',[1,2,3,4,5],'Only an alpha assignment for the target is reported.',MISSING)],
'R004':[c(0,'target','unsupported',[1,2,3],'The target omega code is VX-81112.',PICK_CONFLICT),c(0,'explanation','contradicted',[2,3],'Documents 2 and 3 agree on VX-81112.','The two records give different omega values.'),c(0,'explanation','supported',[2,3],'Documents 2 and 3 are the target omega records.','Both cited records are target omega assignments.')],
'R005':[c(0,'target','ambiguous',[1,2,5],'The target omega code is VX-81022.','The opening asserts a value, but the final sentence explicitly withdraws a definitive answer.'),c(0,'explanation','supported',[1],'Document 1 reports VX-81022.','The record states that value.'),c(1,'explanation','supported',[2,3],'Document 2 reports VX-81021 and Document 3 gives the target alpha code.','Both described record contents match.'),c(2,'explanation','supported',[1,2,5],'The target omega records conflict and neither has priority.','Two unequal assignments and the no-priority rule are present.'),c(2,'target','supported',[1,2,5],'A single definitive target value cannot be determined.',UNRESOLVED)],
'R006':[c(0,'target','supported',[4],'The target alpha code is VX-81092.',ONE_RECORD)],
'R007':[c(0,'target','supported',[2],'The target omega code is VX-81060.',ONE_RECORD)],
'R008':[c(0,'target','unsupported',[1,2,3,5],'The target alpha code is VX-81121.',OTHER_FIELD),c(0,'explanation','supported',[3,5],'The target omega code is VX-81121 and the fields are independent.','The record and rule support these premises.'),c(0,'explanation','unsupported',[3,5],'The omega assignment and independence justify that alpha value.',OTHER_FIELD)],
'R009':[c(0,'target','unsupported',[1,2,5],'The target alpha code is VX-81120.',PICK_CONFLICT),c(0,'explanation','ambiguous',[1,2],'VX-81120 is consistent across Document 2.','The phrase compares only one document, leaving its intended comparison unclear.'),c(0,'explanation','supported',[1,2,5],'Document 1 gives an incompatible target value VX-81122.','The records assign different values to the same target field.')],
'R010':[c(0,'target','unsupported',[1,3,4,5],'The target alpha code is VX-81091.',OTHER_FIELD)],
'R011':[c(0,'target','ambiguous',[1,2,3,4,5],'No target omega code is assigned.',NO_CODE),c(1,'explanation','supported',[1,2,3,4,5],'The only target-specific assignment is its alpha code.',MISSING)],
'R012':[c(0,'target','unsupported',[1,2,4,5],'The target alpha code is VX-81032.',OTHER_FIELD),c(1,'explanation','contradicted',[2,4],'Document 2 directly states the target alpha value.','Document 2 states the omega value, and the fields are independent.')],
'R013':[c(0,'target','unsupported',[1,2,4,5],'The target omega code is VX-81080.',OTHER_FIELD)],
'R014':[c(0,'target','unsupported',[1,3,4,5],'The target alpha code is VX-81091.',OTHER_FIELD)],
'R015':[c(0,'target','unsupported',[1,3,4,5],'The target omega code is VX-81042.',OTHER_FIELD)],
'R016':[c(0,'target','supported',[2,3,4,5],'The records contain no target alpha assignment.',MISSING),c(1,'explanation','supported',[2,3,4,5],'The target-specific assignment is the omega code VX-81102.',MISSING),c(2,'explanation','ambiguous',[2,3,4,5],'No information exists about the target alpha code.','The intended missing value is absent, but the generic rule does say each field has one value.')],
'R017':[c(0,'target','supported',[1,2,3,5],'The target alpha value is not supplied.',MISSING),c(1,'explanation','supported',[1,2,3,5],'The other unit has conflicting alpha records and neither assigns the target alpha.','Both other-unit assignments concern the same field; the target is distinct.')],
'R018':[c(0,'target','unsupported',[3,4,5],'The target omega code is VX-81040.',PICK_CONFLICT),c(1,'explanation','supported',[5],'Document 5 reports VX-81040 for the target.','The stated document contains that assignment.')],
'R019':[c(0,'target','ambiguous',[1,2,3,4],'No target omega code is assigned.',NO_CODE),c(1,'explanation','supported',[1,2,3,4],'The target has an alpha record VX-81111.',MISSING)],
'R020':[c(0,'target','supported',[5],'A record gives target omega VX-81081.',ONE_RECORD),c(1,'explanation','contradicted',[4,5],'Documents 4 and 5 both assign VX-81081 to the target.','Document 4 is the rule rather than a value assignment.'),c(1,'explanation','supported',[2],'Document 2 assigns VX-81080 to the target.','Document 2 assigns the target alpha field that value.'),c(1,'explanation','contradicted',[2,4,5],'The target records conflict on the requested omega value.','The two target assignments are for independent fields.'),c(1,'target','ambiguous',[2,4,5],'A consistent value cannot be determined.','The final wording withdraws the opening based on an unsupported cross-field conflict; record support is not world-truth certification.')],
'R021':[c(0,'target','supported',[4],'The target omega code is VX-81041.',ONE_RECORD)],
'R022':[c(0,'target','supported',[1,2,3,5],'The target omega value is not supplied.',MISSING),c(1,'explanation','supported',[1,2,3,5],'The other unit has conflicting omega records and these do not supply the target value.','The two other-unit assignments conflict, while the target has only an alpha assignment.')],
'R023':[c(0,'target','unsupported',[2,3,4],'The target alpha code is VX-81100.',PICK_CONFLICT),c(1,'explanation','supported',[2,3,4],'Another record assigns the same target alpha field a conflicting VX-81101.','The two target alpha assignments are different.')],
'R024':[c(0,'explanation','ambiguous',[2,3,4,5],'There is no information about the target omega field.','No specific value is assigned, but the generic one-value rule is information about the field.'),c(1,'target','supported',[2,3,4,5],'The evidence is insufficient to determine the target value.',MISSING)],
'R025':[c(0,'target','supported',[1],'The target omega code is VX-81022.',ONE_RECORD)],
'R026':[c(0,'target','ambiguous',[1,4,5],'The target omega code is VX-81082.','The initial answer is followed by an explicit no-definitive-value conclusion.'),c(0,'explanation','supported',[1],'Document 1 reports VX-81082.','The record states that value.'),c(1,'explanation','supported',[1,5],'Document 5 assigns an incompatible VX-81081.','Both records are for the same target field with different values.'),c(2,'target','supported',[1,4,5],'The conflicting records do not determine one definitive target value.',UNRESOLVED)],
'R027':[c(0,'target','unsupported',[2,3,4],'The target omega code is VX-81052.',PICK_CONFLICT),c(0,'explanation','contradicted',[2,3,4],'The chosen record contradicts no other information.','Document 3 assigns a different value to the same target field.')],
'R028':[c(0,'target','unsupported',[1,2,4,5],'The target omega code is VX-81080.',OTHER_FIELD)],
'R029':[c(0,'target','ambiguous',[1,2,3,4],'No target alpha code is assigned.',NO_CODE),c(1,'explanation','supported',[1,2,3,4],'The target has an omega record but no alpha assignment.',MISSING)],
'R030':[c(0,'target','supported',[2],'The target alpha code is VX-81010.',ONE_RECORD),c(1,'explanation','supported',[2],'Document 2 states the target alpha assignment.','The record explicitly gives this assignment.')],
'R031':[c(0,'target','ambiguous',[1,2,3,4],'No target alpha code is assigned.',NO_CODE),c(1,'explanation','supported',[1,2,3,4],'The target has an omega record and no target alpha assignment.',MISSING)],
'R032':[c(0,'target','supported',[5],'The target alpha code is VX-81031.',ONE_RECORD),c(1,'explanation','supported',[2,5],'Document 5 gives alpha VX-81031 and Document 2 gives omega VX-81032.','Both document contents are correctly described.'),c(1,'explanation','contradicted',[2,4,5],'Those alpha and omega assignments conflict.','The common rule makes the two fields independent.'),c(2,'explanation','supported',[1,2,4,5],'Only Document 5 assigns the target alpha value.','The remaining assignments do not assign target alpha.')],
'R033':[c(0,'target','unsupported',[1,2,3],'The target alpha code is VX-81010.',PICK_CONFLICT),c(0,'explanation','supported',[2],'Document 2 reports VX-81010.','Document 2 contains that assignment.'),c(0,'explanation','contradicted',[1,2,3],'Document 2 is the most recent and preferred record.','All records share one snapshot and none has priority.')],
'R034':[c(0,'target','ambiguous',[1,4,5],'The target alpha code is VX-81030.','The opening is followed by an explicit no-definitive-value conclusion.'),c(1,'explanation','supported',[1,4,5],'Document 5 gives an incompatible target alpha value VX-81031.','The two target-field assignments disagree.'),c(2,'target','supported',[1,4,5],'A single definitive target value cannot be determined.',UNRESOLVED)],
'R035':[c(0,'target','unsupported',[1,2,4,5],'The target alpha code is VX-81032.',OTHER_FIELD),c(1,'explanation','contradicted',[2,4],'Document 2 directly states the target alpha value.','Document 2 reports the omega value, not alpha.')],
'R036':[c(0,'target','supported',[3],'The target omega code is VX-81051.',ONE_RECORD),c(0,'explanation','supported',[3],'Document 3 states this target assignment.','The cited record contains the value.')],
'R037':[c(0,'target','unsupported',[1,2,5],'The target alpha code is VX-81071.',PICK_CONFLICT),c(0,'explanation','ambiguous',[1,2],'VX-81071 is consistent across Document 2.','The phrase compares only one document, leaving its intended comparison unclear.'),c(0,'explanation','supported',[1,2,5],'Document 1 gives an incompatible target value VX-81072.','The two records assign different values to the same target field.')],
'R038':[c(0,'target','ambiguous',[1,2,3,4],'No target omega code is assigned.',NO_CODE),c(1,'explanation','supported',[1,2,3,4],'The target has an alpha assignment VX-81062.',MISSING)],
'R039':[c(0,'target','supported',[1,2,3,5],'The target omega value is not supplied.',MISSING),c(1,'explanation','contradicted',[1,2,5],'Documents 1 and 2 conflict about the other unit omega field.','Document 1 assigns omega while Document 2 assigns independent alpha.'),c(1,'explanation','supported',[1,2,3,5],'Neither record supplies the target omega value.','The records concern another unit.')],
'R040':[c(0,'target','unsupported',[1,2,3,5],'The target alpha code is VX-81121.',OTHER_FIELD),c(0,'explanation','contradicted',[3,5],'Document 3 directly states this target alpha value.','Document 3 assigns the target omega field, not alpha.')],
'R041':[c(0,'target','supported',[1,3,4,5],'The records lack a specific target omega value.',MISSING),c(1,'explanation','ambiguous',[1,3,4,5],'The documents describe the two codes as alpha and do not specify omega codes.','The sentence itself mentions an omega value for the other unit; whether its final denial is target-scoped is unclear.')],
'R042':[c(0,'target','unsupported',[3,4,5],'The target alpha code is VX-81090.',PICK_CONFLICT),c(1,'explanation','contradicted',[4,5],'Document 4 explicitly states VX-81090.','Document 4 reports VX-81092; VX-81090 is in Document 5.')],
'R043':[c(0,'target','supported',[1],'The target alpha code is VX-81122.',ONE_RECORD)],
'R044':[c(0,'target','supported',[3],'The target alpha code is VX-81100.',ONE_RECORD),c(1,'explanation','supported',[3],'Document 3 states this target assignment.','The cited record contains the value.')],
'R045':[c(0,'target','ambiguous',[2,3,4,5],'No target alpha code is assigned.',NO_CODE),c(1,'explanation','supported',[2,3,4,5],'The target has an omega record VX-81102.',MISSING)],
'R046':[c(0,'target','supported',[1],'The target alpha code is VX-81072.',ONE_RECORD)],
'R047':[c(0,'target','supported',[1,2,3,5],'The target alpha value is not supplied.',MISSING),c(1,'explanation','contradicted',[1,2,5],'Documents 1 and 2 conflict about the other unit alpha field.','Document 1 assigns alpha and Document 2 assigns independent omega.'),c(1,'explanation','supported',[1,2,3,5],'Neither document specifies the target alpha value.','The cited assignments concern the other unit.')],
'R048':[c(0,'target','supported',[2],'The target omega code is VX-81110.',ONE_RECORD),c(0,'explanation','supported',[2],'Document 2 states this target assignment.','The cited record contains the value.')],
}


def sentences(answer):
    return [(m.start(), m.end(), m.group()) for m in re.finditer(r'\S.*?(?:[.!?](?=\s|$)|$)', answer)]


def build_review():
    packet=json.loads(PACKET.read_text(encoding='utf-8'))
    items=intake.validate_packet(packet)
    if set(CLAIMS)!=set(items):
        raise ValueError('hand-authored claim inventory must cover all 48 IDs')
    rows=[]
    for iid in sorted(items):
        item=items[iid]
        spans=sentences(item['answer'])
        specs=CLAIMS[iid]
        if {entry[0] for entry in specs} != set(range(len(spans))):
            raise ValueError('sentence coverage mismatch: '+iid)
        claims=[]
        for n,(sentence,role,judgment,slots,claim,reason) in enumerate(specs,1):
            start,end,quote=spans[sentence]
            refs=[{'document_index':i,'start':0,'end':len(item['documents'][i-1]),
                   'quote':item['documents'][i-1]} for i in slots]
            claims.append({'claim_id':f'C{n:02d}','claim':claim,'role':role,'judgment':judgment,
                'reason':reason,'output_citation':{'start':start,'end':end,'quote':quote},
                'document_support':refs if judgment=='supported' else [],
                'counterevidence':refs if judgment in ('contradicted','unsupported','ambiguous') else []})
        rows.append({'item_id':iid,'review_status':'reviewed','full_answer_reviewed':True,'claims':claims})
    review={'reviewer_id':'E1-USER-INFORMED-ASSISTANT-20261107',
            'history_exposure':'declared_exposed',
            'exposure_description':'Coordinator assistant has read project history, design conditions, prior findings, and all 48 outputs; not an independent or blinded reviewer.',
            'items':rows}
    intake.validate_review(review,items)
    return review


# Hand-authored final-stance decisions, not automated inference from keywords.
UNRESOLVED_NO_CODE={'R003','R011','R019','R029','R031','R038','R045'}
MISSING_CLEAR={'R002','R016','R017','R022','R024','R039','R041','R047'}
CT_RECOGNIZED={'R005','R009','R023','R026','R034','R037'}
FINAL_WITHDRAWN={'R005','R020','R026','R034'}
OVERBROAD_UNCLEAR={'R016','R024','R041'}


def build_conversion(conservative=False):
    packet_raw,packet=intake.read_json(PACKET)
    _,review,_,receipt,reviewed=intake.verify_sealed_review(packet_raw,packet,SEALED)
    # The coordinator file is read only after validating the raw review seal.
    _,coordinator=intake.read_json(COORDINATOR)
    _,export_seal=intake.read_json(BASE/'coordinator/export-seal.json')
    template=intake.validate_coordinator(packet,coordinator,export_seal)
    items=[]
    for row in template['rows']:
        iid=row['source_item_id']; condition=row['condition']
        raw=reviewed[iid]['claims']
        explanation=[a['judgment'] for a in raw if a['role']=='explanation' and a['judgment']!='not_applicable']
        if not explanation:
            explanation_present='no'; whole='not_applicable'
        else:
            explanation_present='yes'
            whole=next((v for v in ('contradicted','unsupported','ambiguous') if v in explanation),'supported')
        no_value=iid in UNRESOLVED_NO_CODE or iid in MISSING_CLEAR or (iid in FINAL_WITHDRAWN and not conservative)
        given='unknown' if conservative and iid in FINAL_WITHDRAWN else ('no' if no_value else 'yes')
        fields={key:None for key in metrics.FIELDS}
        fields.update({'gives_unretracted_target_value':given,
                       'provides_substantive_explanation':explanation_present,
                       'whole_explanation_support':whole,
                       'overbroad_missing_information_claim':'unknown' if iid in OVERBROAD_UNCLEAR else 'no'})
        if condition in ('I0','IU'):
            if iid in UNRESOLVED_NO_CODE:w='unknown'
            elif iid in MISSING_CLEAR:w='yes'
            else:w='no'
            fields.update({'withholds_target_with_support':w,'unsupported_target_conflict':'no'})
            reason='Narrow target-conflict assertion is absent; W follows the recorded final stance and preserves ambiguous no-assignment wording.'
        elif condition=='S':
            fields['grounded_target_answer']=('unknown' if conservative else 'no') if iid=='R020' else 'yes'
            reason=('S uses record-relative support; R020 both initially supplies a value and later denies a consistent value, so final stance is unclear.'
                    if conservative else 'S uses record-relative support; R020 ends by withdrawing a definitive value after an unsupported conflict explanation.')
        else:
            fields['recognizes_target_conflict']='yes' if iid in CT_RECOGNIZED else 'no'
            fields['unresolved_target_side_selection']=('unknown' if conservative else 'no') if iid in FINAL_WITHDRAWN else 'yes'
            reason=('CT recognizes conflict only when explicitly described; an initial value followed by no definitive value leaves final selection unclear.'
                    if conservative else 'CT recognizes conflict only when explicitly described; a clear final no-definitive-value conclusion retracts an initial selection.')
        items.append({'item_id':iid,'claim_ids':[a['claim_id'] for a in raw],
                      'rationale':reason,'fields':fields})
    return {'converter_id':'E1-USER-INFORMED-ASSISTANT-20261107','history_exposure':'declared_exposed',
            'exposure_description':'Same coordinating assistant; has seen design, conditions, mapping, prior findings and all 48 outputs. This is informed manual conversion, not an independent review.',
            'sealed_review_sha256':receipt['review_bytes_sha256'],'items':items}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',choices=('review','conversion','conversion-v2'),required=True)
    args=parser.parse_args()
    value=build_review() if args.stage=='review' else build_conversion(conservative=args.stage=='conversion-v2')
    print(json.dumps(value,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
