# -*- coding: utf-8 -*-
import json, re
from pathlib import Path
R = Path(r'D:/1_ai/_hb_lab/r58')
d = json.loads((R/'questions/题目_选择题_182.json').read_text(encoding='utf-8'))['questions']
def n(s): return re.sub(r'\s', '', s)

def lcs_len(a, b):
    if not a or not b: return 0
    prev = [0]*(len(b)+1)
    for i in range(1, len(a)+1):
        cur = [0]*(len(b)+1)
        ai = a[i-1]
        for j in range(1, len(b)+1):
            if ai == b[j-1]:
                cur[j] = prev[j-1] + 1
        prev = cur
    return max(prev)

print('=== 选项两两雷同度（LCS / 平均长度）===')
rows = []
for x in d:
    keys = [k for k in 'ABCD' if k in x['options']]
    if len(keys) < 4: continue
    best = 0; pair = None
    for i in range(len(keys)):
        for j in range(i+1, len(keys)):
            a, b = n(x['options'][keys[i]]), n(x['options'][keys[j]])
            if min(len(a), len(b)) < 30: continue
            r = lcs_len(a, b) / ((len(a)+len(b))/2)
            if r > best:
                best = r; pair = (keys[i], keys[j])
    rows.append((x['id'], x['kind'], round(best, 3), pair, x['answer']))
rows.sort(key=lambda r: -r[2])
print('  雷同度分布:')
for lo, hi in ((0.95,1.01),(0.90,0.95),(0.85,0.90),(0.80,0.85),(0.0,0.80)):
    c = sum(1 for r in rows if lo <= r[2] < hi)
    print('    %.2f-%.2f : %d 题' % (lo, min(hi,1.0), c))
print()
print('  雷同度 >= 0.90 的题（两选项几乎一样）:', sum(1 for r in rows if r[2] >= 0.90))
print('  雷同度 >= 0.85 的题:', sum(1 for r in rows if r[2] >= 0.85))
print()
print('  最雷同的 15 题:')
for qid, kind, r, pair, ans in rows[:15]:
    flag = ' ⚠答案在其中' if pair and ans in pair else ''
    print('    %-8s [%-12s] %.3f %s%s' % (qid, kind, r, pair, flag))
print()
print('=== 按 kind ===')
import statistics
for kind in ('open','objective','intervention'):
    sub = [r for r in rows if r[1] == kind]
    if sub:
        print('  %-13s n=%2d | 雷同度中位 %.3f | >=0.90: %d 题' % (kind, len(sub), statistics.median([r[2] for r in sub]), sum(1 for r in sub if r[2] >= 0.90)))