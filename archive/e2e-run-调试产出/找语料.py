# -*- coding: utf-8 -*-
import json
from pathlib import Path
from collections import Counter
R = Path(r'D:/1_ai/_hb_lab/r58')
d = json.loads((R/'e2e/run/pr64/题目_选择题_150.json').read_text(encoding='utf-8'))
print('=== material 分布 ===')
print(dict(Counter(x['material'] for x in d)))
print()
print('=== 仓库语料候选 ===')
for p in ('corpus', 'chain/corpus', 'data', 'sources'):
    q = R / p
    if q.exists():
        fs = sorted(q.glob('*'))[:12]
        print(' %-16s %d 项' % (p, len(list(q.glob('*')))))
        for f in fs:
            print('    %-40s %8d' % (f.name, f.stat().st_size if f.is_file() else 0))
print()
print('=== 找 秦吏 / 毛选 ===')
for name in ('秦吏', '毛选', '毛泽东', '蜂巢指南'):
    hits = []
    for pat in ('**/*%s*' % name,):
        hits += [str(x.relative_to(R)) for x in R.glob(pat) if x.is_file()][:5]
    print(' %-8s %s' % (name, hits if hits else '未找到'))