#!/usr/bin/env python3
"""CPU-only audit of the exposed paraphrase candidate against the old branch interface."""
import collections
import json

import query_determinacy_model_world_replay as replay
import query_determinacy_oracle_run as oracle
import query_determinacy_world_extract_material as original
import query_determinacy_world_paraphrase_material as paraphrase


def audit():
    candidates = paraphrase.build()  # In memory only: never writes candidate material.
    old = {(x['case'], x['condition']): x for x in original.build()}
    if len(candidates) != 24 or len(old) != 24:
        raise ValueError('unexpected candidate count')
    counts = collections.Counter()
    errors = collections.Counter()
    for candidate in candidates:
        baseline = old[(candidate['case'], candidate['condition'])]
        if candidate['expected'] != baseline['expected']:
            raise ValueError('reference values changed')
        text = candidate['prompt'].splitlines()
        if len(text) != 3 or not all(value in text[1] for value in candidate['expected']):
            raise ValueError('missing candidate text or values')
        counts['backgrounds'] += 1
        counts['style_' + str(candidate['style'])] += 1
        matches = [x for x in oracle.inputs().values()
                   if x['case'] == candidate['case'] and x['condition'] == candidate['condition']]
        if len(matches) != 3:
            raise ValueError('expected three questions per background')
        for item in matches:
            values = candidate['expected']  # Hypothetical correct extraction; not model output.
            replay.prompts_from_candidates(item['prompt'], values)
            counts['original_accepted'] += 1
            prompt = item['prompt'].splitlines()
            prompt[1] = text[1]
            try:
                replay.prompts_from_candidates('\n'.join(prompt), values)
            except ValueError as error:
                errors[str(error)] += 1
            else:
                counts['paraphrase_accepted'] += 1
            counts['questions'] += 1
    if counts['questions'] != 72:
        raise ValueError('unexpected question count')
    return {'counts': dict(counts), 'errors': dict(errors),
            'qualification': 'Expected values simulate perfect extraction; no model call or semantic certification.'}


if __name__ == '__main__':
    print(json.dumps(audit(), ensure_ascii=False, indent=2, sort_keys=True))
