# -*- coding: utf-8 -*-
import json, re
from pathlib import Path
import yaml
R = Path(r'D:/1_ai/_hb_lab/r58')
card = yaml.safe_load((R/'cards/o027.yaml').read_text(encoding='utf-8', errors='replace'))
qs = json.loads((R/'questions/题目_选择题_238.json').read_text(encoding='utf-8'))['questions']
o27 = next(x for x in qs if x['id'] == 'o027')
B = o27['options']['B']
print('=== B 全文（%d 字）===' % len(B))
print(B)
print()
print('=== p1 的 any_of 逐条测试 ===')
p1 = next(r for r in card['rubric'] if r['id'] == 'p1')
for pat in p1['any_of']:
    if pat.startswith('re: '):
        m = re.search(pat[4:], B)
        print('  [正则] %-46s %s' % (pat[4:][:44], ('命中: '+m.group(0)) if m else '未命中'))
    else:
        print('  [字面] %-46s %s' % (pat, '命中' if pat in B else '未命中'))