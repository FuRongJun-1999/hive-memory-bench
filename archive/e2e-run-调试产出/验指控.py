# -*- coding: utf-8 -*-
import json
from pathlib import Path
R = Path(r'D:/1_ai/_hb_lab/r58')
d = {x['qid']: x for x in json.loads((R/'e2e/run/pr64/题目_选择题_150.json').read_text(encoding='utf-8'))}
for qid in ('S-044','S-045','S-005','S-066','S-067','S-063','S-052','S-053'):
    if qid not in d:
        print(qid, '不存在'); continue
    x = d[qid]
    print('=' * 72)
    print('%s [%s] %s' % (qid, x['material'], x['question']))
    for k in 'ABCD':
        mark = ' ★' if k == x['answer'] else ''
        print('   %s. %s%s' % (k, x['options'][k], mark))
    print('   fact:', x['fact'][:110])