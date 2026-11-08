# -*- coding: utf-8 -*-
import json, re
from pathlib import Path
R = Path(r'D:/1_ai/_hb_lab/r58')
d = json.loads((R/'questions/题目_选择题_182.json').read_text(encoding='utf-8'))['questions']
iv = [x for x in d if x['kind'] == 'intervention']
print('干预题:', len(iv))
print()
# 1) 题干是否含否定前提
NEG = ['没有', '不存在', '缺失', '去掉', '不再', '失效', '未']
POS = ['依然', '照样', '仍然', '也成立', '也照常', '依然显示', '依然存在']
print('=== 题干含否定前提的题 ===')
neg_q = [x for x in iv if any(k in x['question'] for k in NEG)]
print('  %d / %d' % (len(neg_q), len(iv)))
print()
print('=== 干扰项里出现「依然/照样/仍然」等肯定词的次数 ===')
cnt = 0; examples = []
for x in neg_q:
    for k in 'ABCD':
        if k not in x['options'] or k == x['answer']: continue
        v = x['options'][k]
        if any(p in v for p in POS):
            cnt += 1
            if len(examples) < 6:
                examples.append((x['id'], k, v[:100]))
print('  命中 %d 处（%d 题）' % (cnt, len(set(e[0] for e in examples)) if examples else 0))
for qid, k, v in examples:
    print('    %s %s: %s' % (qid, k, v))
print()
# 2) 抽样 3 题看差异段
print('=== 抽样 3 题的答案 vs 干扰项（差异点）===')
import textwrap
for x in iv[10:13]:
    print('--- %s 答案=%s' % (x['id'], x['answer']))
    print('    问:', x['question'][:80])
    keys = [k for k in 'ABCD' if k in x['options']]
    vals = [x['options'][k] for k in keys]
    mn = min(len(v) for v in vals)
    L = 0
    while L < mn and all(v[L] == vals[0][L] for v in vals): L += 1
    print('    共同前缀 %d 字' % L)
    for k in keys:
        mark = ' ★' if k == x['answer'] else ''
        print('      %s%s: %s' % (k, mark, x['options'][k][L:L+110]))
    print()