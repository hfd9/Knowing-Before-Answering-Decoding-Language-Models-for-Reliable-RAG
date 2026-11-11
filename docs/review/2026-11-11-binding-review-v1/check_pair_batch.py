"""Check follow-up pair judgments against delivered pair text without author labels."""
import argparse
import json
from pathlib import Path
parser=argparse.ArgumentParser();parser.add_argument('batch',type=int);parser.add_argument('--work',default='/tmp/binding-review-20261111');args=parser.parse_args()
w=Path(args.work); supplied=json.loads((w/f'pair-batch-{args.batch}.txt').read_text().split('\n',1)[1])['items']
by={x['pair_id']:x for x in supplied};assert len(by)==6
events=[json.loads(x) for x in (w/f'pair-response-{args.batch}.jsonl').read_text().splitlines() if x.strip()]
assert events[0]['type']=='thread.started' and events[-1]['type']=='turn.completed'
messages=[e['item'] for e in events if e['type']=='item.completed']
assert len(messages)==1 and messages[0]['type']=='agent_message'
text=messages[0]['text'].strip()
if text.startswith('```'):text=text.split('\n',1)[1].rsplit('```',1)[0].strip()
rows=json.loads(text)['items'];assert len(rows)==6 and {x['pair_id'] for x in rows}==set(by)
citations=0
for x in rows:
    assert x['relation'] in ('same','different','unknown') and isinstance(x['reason'],str) and x['reason'].strip()
    for side in ('left','right'):
        evidence=x[side+'_evidence'];assert isinstance(evidence,list) and len(evidence)>=2
        slots=set()
        for e in evidence:
            assert isinstance(e['slot'],int) and 1<=e['slot']<=5
            assert isinstance(e['quote'],str) and e['quote'] and e['quote'] in by[x['pair_id']][side]['docs'][e['slot']-1]
            slots.add(e['slot']);citations+=1
        assert len(slots)>=2
print(json.dumps({'status':'passed_pair_public_check','batch':args.batch,'pairs':6,'citation_occurrences':citations,
 'relations':{s:sum(x['relation']==s for x in rows) for s in ('same','different','unknown')},
 'semantic_truth_or_private_context_certified':False}))
