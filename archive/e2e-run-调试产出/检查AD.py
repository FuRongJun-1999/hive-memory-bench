# -*- coding: utf-8 -*-
import json, re
from pathlib import Path
R = Path(r'D:/1_ai/_hb_lab/r58')
d = json.loads((R/'questions/题目_选择题_182.json').read_text(encoding='utf-8'))['questions']
def n(s): return re.sub(r'\s', '', s)

print('=== A-D 之间的长短版（排除固定短句 E）===')
dups = []
for x in d:
    keys = [k for k in 'ABCD' if k in x['options']]
    for i in range(len(keys)):
        for j in range(i+1, len(keys)):
            a, b = n(x['options'][keys[i]]), n(x['options'][keys[j]])
            if not a or not b or min(len(a), len(b)) < 20: continue
            short, lg = (a, b) if len(a) < len(b) else (b, a)
            ratio = len(short)/len(lg)
            # 短的是长的前缀，或整体高度重合
            if lg.startswith(short) and ratio > 0.6:
                dups.append((x['id'], keys[i], keys[j], len(a), len(b), round(ratio*100)))
print('  长短版嫌疑:', len(dups))
for row in sorted(dups, key=lambda r: -r[5])[:15]:
    print('    %s %s(%d) vs %s(%d) 覆盖%d%%' % row)

print()
print('=== 作者点名的 o027 / q007 ===')
for qid in ('o027','q007','q016'):
    x = next((y for y in d if y['id'] == qid), None)
    if not x: print(' ', qid, '不存在'); continue
    print('--- %s [%s] 答案=%s is_unknown=%s' % (qid, x['kind'], x['answer'], x.get('is_unknown')))
    print('    问:', x['question'][:100])
    for k in 'ABCDE':
        if k not in x['options']: continue
        mark = ' ★' if k == x['answer'] else ''
        print('    %s(%3d字). %s%s' % (k, len(x['options'][k]), x['options'][k][:110], mark))
    print()