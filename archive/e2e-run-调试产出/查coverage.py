# -*- coding: utf-8 -*-
import json, re
from pathlib import Path
R = Path(r'D:/1_ai/_hb_lab/r58')
t = (R/'cards/o027.yaml').read_text(encoding='utf-8', errors='replace')
lines = t.split(chr(10))
print('=== o027.yaml 第 75-86 行（rubric 元信息）===')
for i in range(74, min(86, len(lines))):
    print('  %3d: %s' % (i+1, lines[i]))
print()
# 统计所有卡片里 coverage_required 的分布
import glob
vals = {}
for c in sorted((R/'cards').glob('*.yaml')):
    tt = c.read_text(encoding='utf-8', errors='replace')
    m = re.search(r'coverage_required:\s*([0-9.]+)', tt)
    if m:
        vals.setdefault(m.group(1), []).append(c.stem)
print('=== 全库 coverage_required 分布 ===')
for v, ids in sorted(vals.items()):
    print('  %s : %d 张卡 %s' % (v, len(ids), ids[:8]))
print()
# o027 的 rubric 5 条，B 覆盖几条
qs = json.loads((R/'questions/题目_选择题_238.json').read_text(encoding='utf-8'))['questions']
o27 = next((x for x in qs if x['id'] == 'o027'), None)
print('=== o027 选择题项 ===')
print('  required_count:', o27.get('required_count'), '| answer:', o27['answer'])
print('  → 若 coverage_required=0.7，5 条中覆盖 4 条 = 80%% ≥ 70%%')
print('  → 但选择题把「覆盖 4/5 的 B」当作错误选项')
print('  → **rubric 标准（70%% 就过）与选择题标准（必须 5/5）不一致**')