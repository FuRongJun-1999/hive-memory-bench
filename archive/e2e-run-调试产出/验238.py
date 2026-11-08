# -*- coding: utf-8 -*-
import json, math, subprocess
from pathlib import Path
from collections import Counter
R = Path(r'D:/1_ai/_hb_lab/r58')
qs = json.loads((R/'questions/题目_选择题_238.json').read_text(encoding='utf-8'))['questions']
n = len(qs)
ce = sum(1 for x in qs if x['answer'] == 'E')
print('=== 1) 基线现在成立吗 ===')
print('  n = %d | E 是答案 %d (%.1f%%)' % (n, ce, ce/n*100))
non_e = n - ce
print('  非 E 题 %d，四选一随机期望 = %.1f 题 = %.1f%%' % (non_e, non_e/4, non_e/4/n*100))
print('  → 一个「永不选 E」的系统随机期望 %.1f%%，与 5 选 1 理论值 20%% 相差 %.1f 点' % (non_e/4/n*100, abs(non_e/4/n*100 - 20)))
print('  → 结论:', '✅ 0.2 基线成立' if abs(non_e/4/n*100 - 20) < 2 else '⚠ 仍有偏差，需注明')
print()
print('=== 2) q007 是否改过（对比 182 版）===')
old_p = R/'e2e/run/pr64_v2/题目_选择题_150.json'
q7_new = next(x for x in qs if x['id'] == 'q007')
print('  新答案:', q7_new['answer'])
print('  B 全文:', q7_new['options']['B'])
print('  → B 是否仍含「原文没有给出明确的机制说明」:', '是 ❌ 未改' if '没有给出明确' in q7_new['options']['B'] else '否 ✅ 已改')
print('  E 全文:', q7_new['options']['E'])
print()
print('=== 3) o027 的 rubric（cards/o027.yaml）===')
c = R/'cards/o027.yaml'
if c.exists():
    t = c.read_text(encoding='utf-8', errors='replace')
    import re
    pts = re.findall(r'- id: (p\d+)', t)
    reqs = re.findall(r'required: (true|false)', t)
    print('  条目数:', len(pts), '| required 数:', sum(1 for r in reqs if r == 'true'))
    print('  是否写了「全覆盖/漏一即错」:', '是' if ('全覆盖' in t or '漏一' in t) else '否 ❌')
else:
    print('  不存在')
print()
print('=== 4) 新增 e001-e056 是什么 ===')
es = [x for x in qs if x['id'].startswith('e')]
print('  数量:', len(es))
print('  kind:', dict(Counter(x['kind'] for x in es)))
print('  答案分布:', dict(sorted(Counter(x['answer'] for x in es).items())))
print('  是否全 is_unknown:', all(x.get('is_unknown') for x in es))
print('  首题:', es[0]['id'], '|', es[0]['question'][:70])