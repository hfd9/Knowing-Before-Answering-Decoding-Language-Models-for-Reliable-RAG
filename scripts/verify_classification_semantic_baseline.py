"""CPU-only read-only replay of a completed semantic baseline, including bootstrap."""

import argparse
from pathlib import Path

import classification_semantic_baseline as s


def verify(base):
    e = s.e
    saved = e.read_json(base/'protocol.json')
    s.require(saved['task'] == 'validation_only_semantic_classification', 'Wrong experiment task')
    for relative, expected in saved['code_and_prompt_sha256'].items():
        s.require(e.repro.digest_file(s.ROOT/relative) == expected, f'Frozen code changed: {relative}')
    for relative, expected in saved['auxiliary_reference_sha256'].items():
        s.require(e.repro.digest_file(s.ROOT/relative) == expected, f'Auxiliary source changed: {relative}')
    args = argparse.Namespace(model=saved['model'], run_dir=base,
              reference=Path(saved['reference']), baseline=Path(saved['baseline']),
              limit_questions=3 if saved['smoke'] else None)
    rows, spec = s.old.sources(args)
    config = e.read_json(s.PROMPTS)
    s.require(s.make_protocol(args, rows, spec, config) == saved, 'Protocol replay differs')
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(args.model, local_files_only=True)
    grammar = s.LabelGrammar(tokenizer, s.eos_ids(args.model, tokenizer))
    protocol_hash = e.repro.digest_file(base/'protocol.json')
    s.require(e.read_json(base/'preflight.json') == s.preflight(args,rows,tokenizer,config,grammar),
              'Preflight replay differs')
    report = s.analyze(args, rows, config, protocol_hash, tokenizer, grammar, write=False)
    s.require(e.read_json(base/'reports/val.json') == report, 'Metrics/selection/bootstrap replay differs')
    progress = e.read_json(base/'progress.json')
    s.require(progress['status'] == 'analysis_complete' and progress['protocol_sha256'] == protocol_hash,
              'Progress is not complete for this protocol')
    if saved['smoke']:
        s.require(e.read_json(base/'smoke_gate.json') == report['technical_smoke'], 'Saved smoke gate differs')
    return dict(status='verified_complete', run_dir=str(base), instances_per_candidate=len(rows),
                new_outputs=len(rows)*2, code_fingerprints_checked=len(saved['code_and_prompt_sha256']),
                selection=report['selection'], auxiliary_known_inputs=report['auxiliary_development_diagnosis']['known'],
                protocol_sha256=protocol_hash, published_metrics_and_bootstrap_replayed=True,
                limitation=report['note'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run_dir', type=Path, default=s.DEFAULT)
    parser.add_argument('--output', type=Path, help='Optional new JSON; existing files are not overwritten')
    args = parser.parse_args()
    result = verify(s.e.resolve(args.run_dir))
    if args.output:
        s.require(not args.output.exists(), 'Output already exists; preserve it')
        s.e.repro.write_json(args.output,result)
    import json
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__ == '__main__':main()
