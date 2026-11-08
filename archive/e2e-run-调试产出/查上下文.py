# -*- coding: utf-8 -*-
import re
from pathlib import Path
NEW = Path(r'D:/1_ai/_hb_lab/r58/e2e/run/pr64_v2')
for name in ('README.md', '选择题题库_设计说明_v1.0.md'):
    p = NEW/name
    if not p.exists(): continue
    t = p.read_text(encoding='utf-8')
    print('=' * 70)
    print(name)
    print('=' * 70)
    for kw in ('位置偏差', '逐字', 'fact'):
        for m in re.finditer(kw, t):
            s = max(0, m.start()-120); e = min(len(t), m.end()+120)
            seg = t[s:e].replace(chr(10), ' ').strip()
            print('  [%s] ...%s...' % (kw, seg))
            print()