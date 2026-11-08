# -*- coding: utf-8 -*-
import json, subprocess
from pathlib import Path
from collections import Counter
R = Path(r'D:/1_ai/_hb_lab/r58')
p = R/'questions/题目_选择题_238.json'
d = json.loads(p.read_text(encoding='utf-8'))
if isinstance(d, dict):
    print('顶层键:', list(d.keys()))
    qs = d.get('questions', [])
    for k, v in d.items():
        if not isinstance(v, list): print('  %-10s %s' % (k, str(v)[:90]))
else:
    qs = d
print('题数:', len(qs))
print('kind:', dict(Counter(x['kind'] for x in qs)))
print('答案分布:', dict(sorted(Counter(x['answer'] for x in qs).items())))
print('is_unknown:', sum(1 for x in qs if x.get('is_unknown')))
print()
print('=== 我的 4 处必改，逐个查 ===')
# 1) 基线
g = R/'grade_mcq.py'
t = g.read_text(encoding='utf-8') if g.exists() else ''
import re
base_hits = re.findall(r'baseline[^\n]{0,60}', t)
print('1) grade_mcq.py 基线相关:')
for h in base_hits[:6]: print('     ', h.strip())
print('     文件是否被本次提交改过:', '否（不在 e61aab6 改动列表）')
print()
# 2) q007
q7 = next((x for x in qs if x['id'] == 'q007'), None)
print('2) q007 是否还在:', '在' if q7 else '已删/改名')
if q7:
    print('     答案:', q7['answer'])
    for k in 'ABCDE':
        if k in q7['options']:
            mark = ' ★' if k == q7['answer'] else ''
            print('     %s: %s%s' % (k, q7['options'][k][:95], mark))
print()
# 3) o027
o27 = next((x for x in qs if x['id'] == 'o027'), None)
print('3) o027 required_count:', o27.get('required_count') if o27 else '不存在')
print()
# 4) is_unknown 分层
print('4) is_unknown=True 的题:', [x['id'] for x in qs if x.get('is_unknown')])