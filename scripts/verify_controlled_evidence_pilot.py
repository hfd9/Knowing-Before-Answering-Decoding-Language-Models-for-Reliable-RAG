"""CPU-only, read-only replay of controlled pilot materials, outputs and reports."""

import argparse
from pathlib import Path
import tempfile

import controlled_evidence_pilot as p


def verify(base,prepared_only=False):
    e,m=p.e,p.m
    protocol=e.read_json(base/'protocol.json')
    p.require(protocol['task']=='controlled_evidence_development_pilot','Wrong experiment')
    for path,sha in protocol['implementation_sha256'].items():
        p.require(m.digest(p.ROOT/path)==sha,f'Frozen implementation changed: {path}')
    for path,sha in protocol['probe_source_sha256'].items():
        p.require(m.digest(p.ROOT/path)==sha,f'Probe source changed: {path}')
    spec,rows,judgments,provenance=m.build()
    if protocol['smoke']:
        rows=[r for r in rows if r['original_id']==spec['smoke_base']]
        ids={r['id'] for r in rows}
        judgments=[j for j in judgments if j['id'] in ids]
        provenance=[v for v in provenance if v['original_id']==spec['smoke_base']]
    materials=m.material_artifacts(rows,judgments,provenance)
    for name,text in materials.items():
        p.require((base/'materials'/name).read_bytes()==text.encode(),f'Material differs: {name}')
    seal=e.read_json(base/'materials/review_seal.json')
    p.require(seal['protocol_sha256']==m.digest(base/'protocol.json') and
              seal['inputs_sha256']==m.digest(base/'materials/inputs.json') and
              seal['judgments_sha256']==m.digest(base/'materials/input_judgments.json') and
              seal['reviewed_inputs']==len(rows) and seal['document_slots']==5*len(rows) and
              seal['independent_gold'] is False,'Input review seal differs')
    args=argparse.Namespace(run_dir=base,model=protocol['model'],smoke=protocol['smoke'],annotations=None)
    probe,hashes,old=p.probe_resources(args.model)
    p.require(p.make_protocol(args,spec,rows,materials,hashes,old)==protocol,'Protocol replay differs')
    from transformers import AutoTokenizer
    tokenizer=AutoTokenizer.from_pretrained(args.model,local_files_only=True)
    grammar=p.s.LabelGrammar(tokenizer,p.s.eos_ids(args.model,tokenizer))
    p.require(p.preflight(args,spec,rows,tokenizer,grammar)==e.read_json(base/'preflight.json'),'Preflight differs')
    if prepared_only:
        progress=e.read_json(base/'progress.json')
        p.require(progress['status']=='prepared_not_started' and progress['free_saved']==progress['classification_saved']==0,
                  'Expected unstarted prepared run')
        p.require(not any((base/task/'predictions.json').exists() for task in ['free_answer','classification']),
                  'GPU predictions already exist; use completed verification')
        return dict(status='prepared_verified_not_started',inputs=len(rows),new_gpu_outputs=0,
                    implementation_fingerprints=len(protocol['implementation_sha256']),
                    protocol_sha256=m.digest(base/'protocol.json'),input_judgments_are_independent=False)
    saved=e.read_json(base/'reports/pilot.json')
    if saved['annotation_sha256'] is not None:
        p.require(m.digest(base/'review/annotation_snapshots'/f'{saved["annotation_sha256"]}.csv')==saved['annotation_sha256'],
                  'Consumed annotation snapshot differs')
    args.annotations=Path(saved['annotation_file'])
    report=p.analyze(args,rows,probe,tokenizer,grammar,write=False)
    p.require(report==saved,'Report replay differs')
    records=p.cache(base,'free_answer',rows,tokenizer,grammar,probe,args.model)
    with tempfile.TemporaryDirectory() as tmp:
        reference=Path(tmp)
        p.review.export_review(reference,{r['id']:r for r in rows},{'chat':records})
        for relative in ['review/manifest.json','review/annotations_template.csv','review/blind_review.html']:
            p.require((base/relative).read_bytes()==(reference/relative).read_bytes(),f'Review export differs: {relative}')
    progress=e.read_json(base/'progress.json')
    p.require(progress['status']==report['status'] and progress['protocol_sha256']==m.digest(base/'protocol.json'),
              'Progress does not match completed analysis')
    if args.smoke:
        p.require(e.read_json(base/'smoke_gate.json')==report['technical_smoke'],'Smoke gate differs')
    return dict(status='verified_complete',instances=len(rows),new_outputs=2*len(rows),
                implementation_fingerprints=len(protocol['implementation_sha256']),
                unknown_behavior_rows=report['unknown_behavior_rows'],
                protocol_sha256=m.digest(base/'protocol.json'),
                limitation=report['limitation'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run_dir',type=Path,default=p.DEFAULT)
    parser.add_argument('--prepared_only',action='store_true')
    args=parser.parse_args()
    print(p.m.json_text(verify(p.e.resolve(args.run_dir),args.prepared_only)))


if __name__=='__main__':main()
