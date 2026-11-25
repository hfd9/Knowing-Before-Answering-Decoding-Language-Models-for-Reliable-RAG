"""Post-hoc diagnostic of competing rule/scope evidence choices on exposed records."""
import json, sys
from pathlib import Path
from zipfile import ZipFile
from collections import Counter
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
import query_determinacy_role_assign as candidate
packs=[('prior_48','2026-11-25-typed-holdout-v1','raw.zip'),('prior_12','2026-11-25-typed-ambiguity-v1','raw.zip'),('permutation_24','2026-11-25-role-assignment-dev-v1','live-raw.zip'),('exposed_holdout_36','2026-11-25-role-assignment-holdout-v1','raw.zip')]
def run():
 result={}
 for label,folder,archive in packs:
  path=HERE.parent/folder
  public=json.loads((path/'public.json').read_text())
  ref=json.loads((path/'reference.json').read_text())
  with ZipFile(path/archive) as z:
   rows=[r for n in sorted(z.namelist()) if n.startswith('locate-') and n.endswith('.record.json') for r in json.loads(z.read(n))['records']]
  locations,failures=candidate.assign(public,rows)
  scores={r['id']:candidate.frozen.choice_scores(r) for r in rows}
  detail={}
  for name,roles in locations.items():
   evidence=public['profiles'][name]['evidence']
   remaining=set(evidence)-{roles['earlier'],roles['later']}
   top={role:max(remaining,key=lambda tag:scores[name+'/'+role][tag]) for role in ('rule','scope')}
   tied={role:len({scores[name+'/'+role][tag] for tag in remaining})<len(remaining) for role in top}
   conflict=top['rule']==top['scope'] or any(tied.values())
   gold={'rule':ref['profiles'][name]['rule'][2],'scope':public['profiles'][name]['scope_claims']['source'],'earlier':ref['profiles'][name]['versions'][0][3],'later':ref['profiles'][name]['versions'][1][3]}
   cases=sum(x['profile']==name for x in public['cases'])
   detail[name]={'conflict':conflict,'top':top,'assigned':roles,'reference':gold,'correct':roles==gold,'cases':cases}
  stats=Counter()
  for v in detail.values():
   stats[('conflict' if v['conflict'] else 'no_conflict')+('_correct' if v['correct'] else '_wrong')]+=1
   stats[('withheld' if v['conflict'] else 'accepted')+'_cases']+=v['cases']
   if not v['conflict'] and v['correct']:stats['accepted_correct_cases']+=v['cases']
  result[label]={'profiles':len(public['profiles']),'failures':failures,'stats':dict(stats),'detail':detail}
 return result
if __name__=='__main__':
 out=json.dumps(run(),ensure_ascii=False,indent=2,sort_keys=True)+'\n'
 if '--verify' in sys.argv:
  assert out==(HERE/'results.json').read_text();print('Conflict diagnostic replay passed.')
 else: print(out,end='')
