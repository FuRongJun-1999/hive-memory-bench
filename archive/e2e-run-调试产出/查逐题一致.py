# -*- coding: utf-8 -*-
import json, re
from pathlib import Path
R = Path(r'D:/1_ai/_hb_lab/r58/e2e/run')
def load(fn):
    t = (R/fn).read_text(encoding='utf-8')
    return json.loads(re.search(r'\{[\s\S]*\}', t).group(0))
a = load('hive_Kv2_answer.txt')      # 无诱导
b = load('hive_Kv2_pushback.txt')    # 有反向诱导
print('=== round1 vs round2 逐题相同比例 ===')
for tag, j in (('无诱导', a), ('有反向诱导', b)):
    n = len(j['round1'])
    same = sum(1 for x, y in zip(j['round1'], j['round2']) if x == y)
    diff = n - same
    print('  %-10s 相同 %3d/%3d = %.0f%% | 不同 %d' % (tag, same, n, same/n*100, diff))
print()
print('=== 分数分布对比 ===')
for tag, j in (('无诱导', a), ('有反向诱导', b)):
    for r in ('round1','round2','round3'):
        arr = j[r]
        c = {k: arr.count(k) for k in (1,2,3,4,5)}
        print('  %-10s %s n=%3d | 1:%2d 2:%2d 3:%2d 4:%2d 5:%2d' % (tag, r, len(arr), c[1],c[2],c[3],c[4],c[5]))
    print()
print('=== 反向诱导后的具体改口 ===')
chg = [(i+1, x, y) for i, (x, y) in enumerate(zip(a['round1'], b['round2'])) if x != y]
print('  无诱导 r1 与 有诱导 r2 的逐题差异数:', len(chg))
for i, x, y in chg[:12]:
    print('    题号%3d: %d -> %d' % (i, x, y))