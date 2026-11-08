# -*- coding: utf-8 -*-
import json, re
from pathlib import Path
R = Path(r'D:/1_ai/_hb_lab/r58')
d = json.loads((R/'questions/题目_选择题_182.json').read_text(encoding='utf-8'))['questions']
def n(s): return re.sub(r'\s', '', s)

dups = []
for x in d:
    keys = [k for k in 'ABCD' if k in x['options']]
    for i in range(len(keys)):
        for j in range(i+1, len(keys)):
            a, b = n(x['options'][keys[i]]), n(x['options'][keys[j]])
            if not a or not b or min(len(a), len(b)) < 20: continue
            short, lg = (a, b) if len(a) < len(b) else (b, a)
            ratio = len(short)/len(lg)
            if lg.startswith(short) and ratio > 0.6:
                dups.append({'qid': x['id'], 'k1': keys[i], 'k2': keys[j],
                             'l1': len(a), 'l2': len(b), 'pct': round(ratio*100), 'ans': x['answer']})
print('A-D 长短版嫌疑:', len(dups))
for r in sorted(dups, key=lambda r: -r['pct']):
    print('  %-6s %s(%d字) vs %s(%d字) 覆盖%d%% | 答案=%s' % (r['qid'], r['k1'], r['l1'], r['k2'], r['l2'], r['pct'], r['ans']))

print()
print('=' * 74)
for qid in ('o027','q007','q016'):
    x = next((y for y in d if y['id'] == qid), None)
    if not x:
        print(qid, '不存在'); continue
    print('--- %s [%s] 答案=%s is_unknown=%s required=%s' % (qid, x['kind'], x['answer'], x.get('is_unknown'), x.get('required_count')))
    print('    问:', x['question'][:110])
    for k in 'ABCDE':
        if k not in x['options']: continue
        mark = ' ★' if k == x['answer'] else ''
        print('    %s(%3d). %s%s' % (k, len(x['options'][k]), x['options'][k][:120], mark))
    print()