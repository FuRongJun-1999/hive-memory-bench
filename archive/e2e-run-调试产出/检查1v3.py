# -*- coding: utf-8 -*-
import json
from pathlib import Path
from collections import Counter
R = Path(r'D:/1_ai/_hb_lab/r58')
d = json.loads((R/'e2e/run/pr64/题目_选择题_150.json').read_text(encoding='utf-8'))

def lcs(a, b):
    """最长公共子串长度"""
    if not a or not b: return 0
    best = 0
    prev = [0]*(len(b)+1)
    for i in range(1, len(a)+1):
        cur = [0]*(len(b)+1)
        for j in range(1, len(b)+1):
            if a[i-1] == b[j-1]:
                cur[j] = prev[j-1] + 1
                if cur[j] > best: best = cur[j]
        prev = cur
    return best

print('=== 检查 1（第三版）：干扰项与正解的最长公共子串占比 ===')
rows = []
for x in d:
    ans = x['answer']
    ao = x['options'].get(ans, '')
    worst = 1.0
    worst_o = ''
    for k, v in x['options'].items():
        if k == ans: continue
        base = max(1, min(len(ao), len(v)))
        r = lcs(ao, v) / base
        if r < worst:
            worst, worst_o = r, v
    rows.append((x['qid'], round(worst, 2), ao[:22], worst_o[:22]))
rows.sort(key=lambda t: t[1])
import statistics
print('  占比中位数: %.2f' % statistics.median([r[1] for r in rows]))
print('  占比 < 0.3 的题（干扰项与正解差异过大）:', sum(1 for r in rows if r[1] < 0.3))
print('  占比 < 0.5 的题:', sum(1 for r in rows if r[1] < 0.5))
print('  占比 >= 0.5 的题（合格）:', sum(1 for r in rows if r[1] >= 0.5))
print()
print('  最差的 8 题:')
for qid, r, a, w in rows[:8]:
    print('    %s %.2f | 正解「%s」 vs 最差干扰「%s」' % (qid, r, a, w))

print()
print('=== 检查 3（深入）：分组内答案分布是否偏 ===')
for m in ('秦吏','毛选','蜂巢指南','对话'):
    sub = [x['answer'] for x in d if x['material']==m]
    c = Counter(sub)
    n = len(sub)
    exp = n / 4
    chi = sum((c.get(k,0)-exp)**2/exp for k in 'ABCD')
    print('  %-8s n=%2d %s | 卡方 %.2f (df=3, 临界7.81)' % (m, n, dict(sorted(c.items())), chi))