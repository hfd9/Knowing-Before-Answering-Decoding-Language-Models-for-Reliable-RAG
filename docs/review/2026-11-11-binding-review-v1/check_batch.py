"""Check one reviewer batch against public packet only; no author mapping needed."""
import argparse
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
PACKET=ROOT/'docs/review/2026-11-11-binding-repetition-control-draft-v2/review-packet.json'
parser=argparse.ArgumentParser();parser.add_argument('batch',type=int);parser.add_argument('--work',default='/tmp/binding-review-20261111');args=parser.parse_args()
w=Path(args.work); manifest=json.loads((w/'batch-manifest.json').read_text()); entry=manifest[args.batch-1]
packet=json.loads(PACKET.read_text()); public={x['review_id']:x for x in packet['items']}
events=[json.loads(x) for x in (w/f'response-{args.batch}.jsonl').read_text().splitlines() if x.strip()]
assert events[0]['type']=='thread.started' and events[-1]['type']=='turn.completed'
completed=[e['item'] for e in events if e['type']=='item.completed']
assert len(completed)==1 and completed[0]['type']=='agent_message','unexpected tool use or message count'
text=completed[0]['text'].strip()
if text.startswith('```'):
    text=text.split('\n',1)[1].rsplit('```',1)[0].strip()
data=json.loads(text); rows=data['items']; assert len(rows)==6
assert {r['review_id'] for r in rows}==set(entry['ids']) and len({r['review_id'] for r in rows})==6
quotes=0
for r in rows:
    assert r['state'] in ('answerable','insufficient','conflicting','unknown')
    assert isinstance(r['target'],str) and r['target'].strip() and isinstance(r['reason'],str) and r['reason'].strip()
    assert isinstance(r['value_or_values'],list) and isinstance(r['evidence'],list)
    docs=public[r['review_id']]['docs']; slots=set()
    for e in r['evidence']:
        assert isinstance(e['slot'],int) and 1<=e['slot']<=5 and isinstance(e['quote'],str) and e['quote'] and e['quote'] in docs[e['slot']-1]
        slots.add(e['slot']);quotes+=1
    assert slots==set(range(1,6)),'review did not cite every slot'
print(json.dumps({'status':'passed_public_packet_check','batch':args.batch,'items':len(rows),'quotes':quotes,
 'states':{s:sum(r['state']==s for r in rows) for s in ('answerable','insufficient','conflicting','unknown')},
 'tool_use_observed':False,'semantic_truth_or_private_context_certified':False}))
