"""CPU-only consistency checks for a pre-selection development protocol."""
from itertools import product
import json
from pathlib import Path
from string import Formatter

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / 'docs/review/2026-11-26-new-rule-development-protocol-v1'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def fields(template):
    return {name for _, name, _, _ in Formatter().parse(template) if name is not None}


def check(d, prose):
    scenarios = [['same', 'missing'], ['same', 'old'], ['same', 'new'],
                 ['different', 'missing'], ['different', 'old'], ['different', 'new']]
    require(d['rule_count'] == 2 and d['scenarios'] == scenarios and d['routes'] == ['direct', 'by_version'],
            'scenario design changed')
    plan = list(product(range(d['rule_count']), d['scenarios'], d['routes']))
    require(len(plan) == d['max_first_turn_calls'] == 24, 'first turn count differs')
    missing = [row for row in plan if row[1][1] == 'missing']
    require(len(missing) == 8 and len(missing) * 2 == d['max_followup_calls'] == 16, 'followup limit differs')
    require(fields(d['common']) == {'question', 'facts_and_date_status', 'old_date', 'new_date',
                                   'source_excerpts_and_explicitly_attributed_metadata'}, 'common fields differ')
    require(fields(d['followup']) == {'event', 'date'}, 'followup fields differ')
    for key in ('system', 'common', 'direct', 'by_version', 'followup'):
        require(d[key] in prose, 'machine prompt differs from prose: ' + key)
    require(d['max_new_tokens'] == 768 and d['do_sample'] is False and d['num_beams'] == 1 and
            d['dtype'] == 'bfloat16', 'decoding differs')
    require(d['followup_trigger'] == 'explicit_event_date_request_only' and
            d['fail_handling'] == 'preserve_attempt_stop_no_automatic_retry', 'failure or followup differs')
    require(d['scope_source_label_explicitly_supplied'] is False and d['new_rule_collection_release'] is False and
            d['old_gate_changed'] is False, 'scope, release, or gate differs')
    return {'first_turn': len(plan), 'missing': len(missing), 'max_followup': len(missing) * 2,
            'collection_release': False}


if __name__ == '__main__':
    print(json.dumps(check(json.loads((PACK / 'protocol.json').read_text()),
                           (PACK / 'protocol.md').read_text()), ensure_ascii=False))
