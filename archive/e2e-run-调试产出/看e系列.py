# -*- coding: utf-8 -*-
import json
from pathlib import Path
from collections import Counter
R = Path(r'D:/1_ai/_hb_lab/r58')
qs = json.loads((R/'questions/题目_选择题_238.json').read_text(encoding='utf-8'))['questions']
es = [x for x in qs if x['id'].startswith('e')]
print('=== e 系列 56 题：答案分布与题目模式 ===')
print('答案:', dict(sorted(Counter(x['answer'] for x in es).items())))
print()
print('=== 答案=E 的题（44）看题干 ===')
e_ans = [x for x in es if x['answer'] == 'E']
for x in e_ans[:10]:
    print('  %s | %s' % (x['id'], x['question'][:85]))
print('  ...')
print()
print('=== 答案≠E 的题（12）看题干 ===')
ne = [x for x in es if x['answer'] != 'E']
for x in ne:
    print('  %s [%s] | %s' % (x['id'], x['answer'], x['question'][:80]))
print()
print('=== o027 的 required 异常 ===')
c = R/'cards/o027.yaml'
t = c.read_text(encoding='utf-8', errors='replace')
import re
print('  文件行数:', len(t.split(chr(10))))
for i, line in enumerate(t.split(chr(10))):
    if 'required' in line or re.match(r'- id:', line) or line.startswith('rubric'):
        print('  %3d: %s' % (i+1, line[:80]))