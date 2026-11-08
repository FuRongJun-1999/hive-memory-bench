# -*- coding: utf-8 -*-
import json, re
from pathlib import Path
from collections import Counter
R = Path(r'D:/1_ai/_hb_lab/r58')
d = json.loads((R/'questions/题目_选择题_182.json').read_text(encoding='utf-8'))['questions']
def n(s): return re.sub(r'\s', '', s)

print('=== A-D 共享前缀长度分布 ===')
rows = []
for x in d:
    keys = [k for k in 'ABCD' if k in x['options']]
    if len(keys) < 4: continue
    strs = [n(x['options'][k]) for k in keys]
    mn = min(len(s) for s in strs)
    # 所有 4 个共享的最长公共前缀
    L = 0
    while L < mn and all(s[L] == strs[0][L] for s in strs):
        L += 1
    rows.append((x['id'], x['kind'], L, mn, round(L/mn*100) if mn else 0))
print('  共享前缀 >=100 字的题:', sum(1 for r in rows if r[2] >= 100))
print('  共享前缀 >=50 字的题 :', sum(1 for r in rows if r[2] >= 50))
print('  共享前缀 >=20 字的题 :', sum(1 for r in rows if r[2] >= 20))
print('  共享前缀 <20 字的题  :', sum(1 for r in rows if r[2] < 20))
print()
print('  共享前缀占最短选项比例分布:')
for lo, hi in ((0,20),(20,40),(40,60),(60,80),(80,101)):
    c = sum(1 for r in rows if lo <= r[4] < hi)
    print('    %2d-%2d%%: %d 题' % (lo, hi, c))
print()
print('  最严重的 12 题:')
for r in sorted(rows, key=lambda r: -r[4])[:12]:
    print('    %-8s [%-12s] 前缀%3d字 / 最短%3d字 = %d%%' % (r[0], r[1], r[2], r[3], r[4]))
print()
print('=== 按 kind 分组看 ===')
for kind in ('open','objective','intervention'):
    sub = [r for r in rows if r[1] == kind]
    if not sub: continue
    import statistics
    print('  %-13s n=%2d | 前缀中位 %d 字 | >=100字: %d' % (kind, len(sub), statistics.median([r[2] for r in sub]), sum(1 for r in sub if r[2] >= 100)))