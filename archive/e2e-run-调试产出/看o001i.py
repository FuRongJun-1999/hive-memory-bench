# -*- coding: utf-8 -*-
import json, re
from pathlib import Path
R = Path(r'D:/1_ai/_hb_lab/r58')
d = {x['id']: x for x in json.loads((R/'questions/题目_选择题_182.json').read_text(encoding='utf-8'))['questions']}
x = d['o001i']
print('=== o001i（干预题，机器从 o001 推导）===')
print('问:', x['question'])
print('答案:', x['answer'], '| required:', x['required_count'], '| rubric:', x['rubric_source'])
print()
opts = {k: x['options'][k] for k in 'ABCD' if k in x['options']}
# 去共同前缀
vals = list(opts.values())
mn = min(len(v) for v in vals)
L = 0
while L < mn and all(v[L] == vals[0][L] for v in vals):
    L += 1
print('四个选项的共同前缀:', L, '字')
print('共同前缀内容:', vals[0][:L])
print()
print('=== 差异部分（去掉共同前缀）===')
for k in 'ABCD':
    if k not in opts: continue
    mark = ' ★答案' if k == x['answer'] else ''
    print('%s%s:' % (k, mark))
    print('  ', opts[k][L:L+260])
    print()