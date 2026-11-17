#!/usr/bin/env python3
"""Create controlled paraphrases of the exposed candidate-extraction prompts."""
import json
from pathlib import Path
import query_determinacy_template_world_extraction as template
import query_determinacy_world_extract_material as prior

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/review/2026-11-15-query-determinacy-world-paraphrase-dev-v1/material.jsonl'


def build():
    original={r['id']:r for r in map(json.loads,prior.OLD.read_text(encoding='utf-8').splitlines())}
    output=[]
    for row in prior.build():
        source=original[row['source_id']];lines=source['prompt'].splitlines();text=lines[1]
        axiom=template.AXIOM if text.startswith(template.AXIOM) else ''
        rest=text[len(axiom):]
        match=template.SOURCE.match(rest) if row['condition']=='dual_sources' else template.ALT.match(rest)
        expected_tail=template.SOURCE_TAIL if row['condition']=='dual_sources' else template.ALT_TAIL
        if not match or rest[match.end():]!=expected_tail:raise ValueError('original source template changed')
        subject,a,b=match['subject'],match['a'],match['b'];style=(int(row['case'][-2:])-1)%3
        if row['condition']=='dual_sources':
            options=[
                f'档案甲记载{subject}是{a}；档案乙记载同一记录是{b}。题设保证真实值只能是以上两个值之一，二者均有可能，无法判断哪份档案正确。',
                f'第一份记录给出{a}，第二份记录给出{b}，它们都指{subject}。题设保证真实值恰好是这两个值之一，两个值都可能，现有信息不能判定哪份记录正确。',
                f'{subject}有两份不一致的记载：{a}、{b}。题设保证真实值必为其中之一，两种情况均有可能，但没有信息判断哪份记载正确。']
        else:
            options=[
                f'已知{subject}只能取{a}或{b}，两种情况均有可能，题设没有信息指出究竟是哪一个。',
                f'关于{subject}，真实值不是{a}就是{b}；题设保证两者均可能且没有额外依据选定其中一个。',
                f'{subject}的可能值恰好是{a}、{b}；题设保证两种可能都存在，现有信息不能作进一步区分。']
        item=dict(row);item['source_id']=row['id'];item['id']=row['id']+'__paraphrase'
        item['style']=style+1
        item['prompt']='\n'.join((lines[0],axiom+options[style],prior.INSTRUCTION))
        output.append(item)
    return output


def main():
    rows=build();encoded=''.join(json.dumps(x,ensure_ascii=False,sort_keys=True)+'\n' for x in rows)
    if len(rows)!=24 or len({x['id'] for x in rows})!=24:raise ValueError('row count')
    if OUT.exists():
        if OUT.read_text(encoding='utf-8')!=encoded:raise ValueError('existing material differs')
        print('material matches')
    else:
        with OUT.open('x',encoding='utf-8') as f:f.write(encoded)
        print('created',OUT)


if __name__=='__main__':main()
