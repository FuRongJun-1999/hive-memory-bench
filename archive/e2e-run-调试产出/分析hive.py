# -*- coding: utf-8 -*-
import json, statistics
from pathlib import Path
R = Path(r'D:/1_ai/_hb_lab/r58')
d = json.loads((R/'e2e/run/hive_Kv2_detail.json').read_text(encoding='utf-8'))
g = json.loads((R/'e2e/run/hive_Kv2_scores.json').read_text(encoding='utf-8'))
ans = json.loads((R/'e2e/run/hive_Kv2_answer.txt').read_text(encoding='utf-8').strip() and __import__('re').search(r'\{[\s\S]*\}', (R/'e2e/run/hive_Kv2_answer.txt').read_text(encoding='utf-8')).group(0))

print('=== 1) 三轮极端值占比 ===')
for tag, arr in (('round1', ans['round1']), ('round2', ans['round2']), ('round3', ans['round3'])):
    n = len(arr)
    c5 = sum(1 for x in arr if x == 5)
    c1 = sum(1 for x in arr if x == 1)
    cmid = sum(1 for x in arr if x == 3)
    print('  %-7s n=%3d | 5 占 %2d(%.0f%%) | 1 占 %2d(%.0f%%) | 3 占 %2d(%.0f%%)' % (
        tag, n, c5, c5/n*100, c1, c1/n*100, cmid, cmid/n*100))

print()
print('=== 2) 跨维度离散度（双单元指出的漏洞）===')
p1 = [x['p1'] for x in d['rows']]
p2 = [x['p2'] for x in d['rows']]
pa = [x['pa'] for x in d['rows']]
n1 = [x['n1_rev'] for x in d['rows']]
for name, v in (('正说 p1', p1), ('二轮 p2', p2), ('换问法 pa', pa), ('反说反计', n1)):
    print('  %-10s 均值 %.2f | 标准差 %.2f | 唯一值 %d 种 %s' % (
        name, statistics.mean(v), statistics.pstdev(v), len(set(v)), sorted(set(v))))

print()
print('=== 3) 「四值全同」的维度（真正零信息量）===')
flat4 = [x['dim'] for x in d['rows'] if abs(x['p1']-x['n1_rev']) < 1e-9 and abs(x['p1']-x['p2']) < 1e-9 and abs(x['p1']-x['pa']) < 1e-9]
print('  ', flat4 if flat4 else '无')

print()
print('=== 4) 换问法（round3）与第二轮是否几乎相同 ===')
same = sum(1 for a, b in zip(ans['round2'][:60], ans['round3']))
diff = sum(1 for a, b in zip(ans['round2'][:60], ans['round3']) if a != b)
print('  round2 前 60 与 round3 逐题比较：相同 %d / 不同 %d' % (same-diff if False else sum(1 for a,b in zip(ans['round2'][:60], ans['round3']) if a==b), diff))
print('  （round3 与 round2 若高度相同 → 换问法没起作用）')