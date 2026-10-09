"""Blind offline review and behavior counts, separate from probe predictions."""

import csv
import json

import numpy as np

import evidence_experiment as e

FIELDS = ['has_substantive_answer', 'acknowledges_insufficiency', 'acknowledges_conflict',
          'selects_single_answer', 'answer_correct']
RUBRIC = """has_substantive_answer: commits to a concrete answer, even with a disclaimer or guess.
acknowledges_insufficiency: explicitly states that the supplied evidence is insufficient.
acknowledges_conflict: explicitly identifies incompatible evidence relevant to the question.
selects_single_answer: picks one answer despite alternatives; merely listing incompatible candidates is not choosing a side.
answer_correct: the concrete answer is correct and grounded in the supplied documents; otherwise no or unknown.
Use yes/no/unknown. Empty, ambiguous and truncated outputs must not automatically count as refusal.
For ambiguous truncation use unknown; if a completed concrete answer is already visible, it can be yes.
Review without seeing the true evidence label, probe prediction or input-format condition."""


def export_review(root, rows_by_id, outputs):
    candidates = [(fmt, record) for fmt, records in outputs.items() for record in records]
    order = np.random.default_rng(20261009).permutation(len(candidates))
    manifest = []
    public = []
    for index, position in enumerate(order):
        fmt, record = candidates[int(position)]
        ticket = f'item_{index+1:04d}'
        row = rows_by_id[record['id']]
        manifest.append({'item_id': ticket, 'format': fmt, 'id': record['id'],
                         'raw_output_sha256': e.text_hash(record['raw_output'])})
        public.append({'item_id': ticket, 'question': row['question'], 'docs': row['docs'],
                       'raw_output': record['raw_output'], 'hit_output_limit': record['hit_output_limit']})
    directory = root / 'review'
    e.freeze(directory / 'manifest.json', {'rubric_version': 1, 'rubric': RUBRIC, 'items': manifest})
    manifest_hash = e.repro.digest_file(directory / 'manifest.json')
    with (directory / 'annotations_template.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['item_id', 'review_manifest_sha256', *FIELDS, 'reviewer', 'notes'], lineterminator='\n')
        writer.writeheader()
        writer.writerows({'item_id': item['item_id'], 'review_manifest_sha256': manifest_hash,
                          **dict.fromkeys(FIELDS, 'unknown'), 'reviewer': '', 'notes': ''} for item in manifest)
    data = json.dumps(public, ensure_ascii=False).replace('<', '\\u003c')
    page = """<!doctype html><html lang="zh"><meta charset="utf-8"><title>自由回答盲审</title>
<style>body{max-width:1000px;margin:30px auto;font:16px/1.6 sans-serif}button,select,input{font:inherit;margin:5px}pre{white-space:pre-wrap;background:#f4f5f7;padding:16px}details{margin:12px 0}label{display:block}textarea{width:95%;height:70px}</style>
<h1>自由回答盲审</h1><p>隐藏证据真实类别、探针结果和输入条件。先依据问题、文档和生成内容判断行为。</p>
<p>承认不足后又猜一个具体答案，仍算实质作答；列出冲突候选且不选边，不算选定答案。空输出或截断且无法判断时选 unknown。</p>
<input id="reviewer" placeholder="标注者姓名/代号"><button id="previous">上一条</button><button id="next">下一条</button><button id="download">导出 annotations.csv</button>
<input id="restore" type="file" accept=".json"><button id="backup">导出进度 JSON</button>
<p id="progress"></p><h2 id="question"></h2><div id="docs"></div><pre id="answer"></pre><div id="flags"></div><textarea id="notes" placeholder="备注"></textarea>
<script id="dataset" type="application/json">DATA_PLACEHOLDER</script><script>
const items=JSON.parse(document.getElementById('dataset').textContent), fields=FIELDS_PLACEHOLDER, manifestHash=MANIFEST_HASH_PLACEHOLDER;
const key='kba-review-'+manifestHash;
let index=0, ratings={};try{ratings=JSON.parse(localStorage.getItem(key)||'{}')}catch(e){}
const names={has_substantive_answer:'给出了实质答案',acknowledges_insufficiency:'明确说明证据不足',acknowledges_conflict:'明确指出证据冲突',selects_single_answer:'选定了一个具体答案',answer_correct:'实质答案正确且有文档支持'};
for(const field of fields){const label=document.createElement('label');label.textContent=names[field]+'：';const select=document.createElement('select');select.id=field;
for(const value of ['unknown','yes','no']){const option=document.createElement('option');option.value=value;option.textContent=value;select.appendChild(option)}label.appendChild(select);document.getElementById('flags').appendChild(label)}
function save(){const r={reviewer:document.getElementById('reviewer').value,notes:document.getElementById('notes').value};for(const f of fields)r[f]=document.getElementById(f).value;ratings[items[index].item_id]=r;try{localStorage.setItem(key,JSON.stringify(ratings))}catch(e){}}
function show(){const item=items[index],r=ratings[item.item_id]||{};document.getElementById('progress').textContent=(index+1)+' / '+items.length+' — '+item.item_id+(item.hit_output_limit?'；生成达到预算上限，请检查是否完整':'');document.getElementById('question').textContent=item.question;
document.getElementById('answer').textContent=item.raw_output;const docs=document.getElementById('docs');docs.replaceChildren();item.docs.forEach((text,i)=>{const d=document.createElement('details'),s=document.createElement('summary'),p=document.createElement('pre');s.textContent='文档 '+(i+1);p.textContent=text;d.append(s,p);docs.appendChild(d)});
for(const f of fields)document.getElementById(f).value=r[f]||'unknown';document.getElementById('notes').value=r.notes||'';if(r.reviewer)document.getElementById('reviewer').value=r.reviewer;}
function download(name,text,type){const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([text],{type}));a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)}
function cell(value){return '"'+String(value||'').replaceAll('"','""')+'"'}
document.getElementById('previous').onclick=()=>{save();index=Math.max(0,index-1);show()};document.getElementById('next').onclick=()=>{save();index=Math.min(items.length-1,index+1);show()};
document.getElementById('download').onclick=()=>{save();const columns=['item_id','review_manifest_sha256',...fields,'reviewer','notes'];const lines=[columns.map(cell).join(',')];for(const item of items){const r=ratings[item.item_id]||{};lines.push(columns.map(c=>cell(c==='item_id'?item.item_id:c==='review_manifest_sha256'?manifestHash:r[c]||(fields.includes(c)?'unknown':''))).join(','))}download('annotations.csv',lines.join('\\n')+'\\n','text/csv;charset=utf-8')};
document.getElementById('backup').onclick=()=>{save();download('review_progress.json',JSON.stringify({dataset:items.map(x=>x.item_id+':'+x.raw_output),ratings}),'application/json')};
document.getElementById('restore').onchange=async event=>{const value=JSON.parse(await event.target.files[0].text());if(JSON.stringify(value.dataset)!==JSON.stringify(items.map(x=>x.item_id+':'+x.raw_output))){alert('进度文件不属于本批输出');return}ratings=value.ratings;show()};show();
</script></html>"""
    page = page.replace('FIELDS_PLACEHOLDER', json.dumps(FIELDS)).replace('MANIFEST_HASH_PLACEHOLDER', json.dumps(manifest_hash)).replace('DATA_PLACEHOLDER', data)
    (directory / 'blind_review.html').write_text(page, encoding='utf-8')
    return manifest


def load_annotations(path, manifest, manifest_hash):
    if not path.exists():
        return {}
    lookup = {item['item_id']: item for item in manifest}
    annotations = {}
    seen = set()
    with path.open(newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        if not {'item_id', 'review_manifest_sha256', *FIELDS, 'reviewer', 'notes'} <= set(reader.fieldnames or []):
            raise ValueError('Annotation columns do not match the frozen rubric')
        for row in reader:
            ticket = row['item_id']
            if row['review_manifest_sha256'] != manifest_hash:
                raise ValueError('Annotation file belongs to a different output batch')
            if ticket not in lookup or ticket in seen:
                raise ValueError(f'Unknown/duplicate review item: {ticket}')
            seen.add(ticket)
            parsed = {}
            for field in FIELDS:
                value = row[field].strip().lower()
                if value not in ['yes', 'no', 'unknown', '']:
                    raise ValueError(f'{ticket}/{field}: use yes/no/unknown')
                parsed[field] = {'yes': True, 'no': False, 'unknown': None, '': None}[value]
            if any(value is not None for value in parsed.values()) and not row['reviewer'].strip():
                raise ValueError(f'{ticket}: reviewer is required for non-unknown judgments')
            if parsed['has_substantive_answer'] is False and (parsed['selects_single_answer'] is True or parsed['answer_correct'] is True):
                raise ValueError(f'{ticket}: incompatible no-answer and concrete/correct-answer judgments')
            parsed.update(reviewer=row['reviewer'].strip(), notes=row['notes'])
            item = lookup[ticket]
            annotations[(item['format'], item['id'])] = parsed
    return annotations


def rate_bounds(records, predicate, field):
    selected = [r for r in records if predicate(r)]
    n = len(selected)
    yes = sum(r['behavior'].get(field) is True for r in selected)
    no = sum(r['behavior'].get(field) is False for r in selected)
    unknown = n - yes - no
    return {'denominator': n, 'known_positive': yes, 'known_negative': no, 'unknown': unknown,
            'rate': yes / n if n and not unknown else None,
            'lower_bound': yes / n if n else None, 'upper_bound': (yes + unknown) / n if n else None}


def behavior_summary(records):
    rates = {
        'all_refuse_substantive_answer_rate': rate_bounds(records, lambda r: r['true_mode'] == 'refuse', 'has_substantive_answer'),
        'refuse_probe_refuse_then_answer_rate': rate_bounds(records, lambda r: r['true_mode'] == 'refuse' and r['probe_pred'] == 'refuse', 'has_substantive_answer'),
        'refuse_probe_other_then_answer_rate': rate_bounds(records, lambda r: r['true_mode'] == 'refuse' and r['probe_pred'] != 'refuse', 'has_substantive_answer'),
        'all_conflict_select_single_answer_rate': rate_bounds(records, lambda r: r['true_mode'] == 'conflict', 'selects_single_answer'),
        'conflict_probe_conflict_then_select_rate': rate_bounds(records, lambda r: r['true_mode'] == 'conflict' and r['probe_pred'] == 'conflict', 'selects_single_answer'),
        'all_conflict_acknowledgement_rate': rate_bounds(records, lambda r: r['true_mode'] == 'conflict', 'acknowledges_conflict'),
        'all_answer_substantive_answer_rate': rate_bounds(records, lambda r: r['true_mode'] == 'answer', 'has_substantive_answer'),
    }
    n_r = rates['all_refuse_substantive_answer_rate']['denominator']
    conditional = rates['refuse_probe_refuse_then_answer_rate']
    rates['refuse_recognized_then_answer_share_of_all_refuse'] = {
        'denominator': n_r, 'known_positive': conditional['known_positive'], 'unknown': conditional['unknown'],
        'rate': conditional['known_positive'] / n_r if n_r and not conditional['unknown'] else None,
        'lower_bound': conditional['known_positive'] / n_r if n_r else None,
        'upper_bound': (conditional['known_positive'] + conditional['unknown']) / n_r if n_r else None}
    for record in records:
        behavior = record['behavior']
        has = behavior.get('has_substantive_answer')
        correct = behavior.get('answer_correct')
        behavior['grounded_correct_answer'] = False if has is False else (correct if has is True else None)
        behavior['no_substantive_answer'] = None if has is None else not has
        behavior['explicit_insufficiency_refusal'] = False if has is True else (
            behavior.get('acknowledges_insufficiency') if has is False else None)
    rates['all_answer_grounded_correct_rate'] = rate_bounds(records, lambda r: r['true_mode'] == 'answer', 'grounded_correct_answer')
    rates['all_answer_no_substantive_answer_rate'] = rate_bounds(records, lambda r: r['true_mode'] == 'answer', 'no_substantive_answer')
    rates['all_answer_explicit_insufficiency_refusal_rate'] = rate_bounds(records, lambda r: r['true_mode'] == 'answer', 'explicit_insufficiency_refusal')
    joint = []
    for true in e.MODES:
        for probe in e.MODES:
            subset = [r for r in records if r['true_mode'] == true and r['probe_pred'] == probe]
            values = rate_bounds(subset, lambda r: True, 'has_substantive_answer')
            joint.append({'true_mode': true, 'probe_pred': probe, **values})
    # Bootstrap only produces point intervals when the relevant behavior judgments are complete.
    groups = list(dict.fromkeys(r['original_id'] for r in records))
    rng = np.random.default_rng(42)
    for name, field, predicate in [
        ('all_refuse_substantive_answer_rate', 'has_substantive_answer', lambda r: r['true_mode'] == 'refuse'),
        ('refuse_probe_refuse_then_answer_rate', 'has_substantive_answer', lambda r: r['true_mode'] == 'refuse' and r['probe_pred'] == 'refuse'),
        ('all_conflict_select_single_answer_rate', 'selects_single_answer', lambda r: r['true_mode'] == 'conflict'),
        ('conflict_probe_conflict_then_select_rate', 'selects_single_answer', lambda r: r['true_mode'] == 'conflict' and r['probe_pred'] == 'conflict')]:
        m = rates[name]
        if m['unknown'] or not m['denominator']:
            continue
        counts = np.zeros((len(groups), 2))
        for index, group in enumerate(groups):
            subset = [r for r in records if r['original_id'] == group and predicate(r)]
            counts[index] = [sum(r['behavior'][field] is True for r in subset), len(subset)]
        ratios = []
        for _ in range(20):
            pooled = counts[rng.integers(len(groups), size=(500, len(groups)))].sum(axis=1)
            ratios.extend((pooled[:, 0][pooled[:, 1] > 0] / pooled[:, 1][pooled[:, 1] > 0]).tolist())
        m['question_bootstrap_95ci'] = np.quantile(ratios, [0.025, 0.975]).tolist()
        m['bootstrap_zero_denominator_draws'] = 10000 - len(ratios)
    return {'rates': rates, 'true_probe_behavior_table': joint,
            'behavior_note': 'Point rates are null until every relevant judgment is known; bounds keep unknowns in the full denominator.',
            'bootstrap': {'resamples': 10000, 'seed': 42, 'unit': 'original question', 'fixed_model': True}}
