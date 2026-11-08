# -*- coding: utf-8 -*-
import os
from collections import defaultdict
from pathlib import Path
R = Path(r'D:/1_ai/_hb_lab/r58')
agg = defaultdict(lambda: [0, 0])
for root, dirs, files in os.walk(R):
    if '.git' in root or '.tmp' in root or 'node_modules' in root:
        dirs[:] = []
        continue
    rel = os.path.relpath(root, R)
    top = rel.split(os.sep)[0] if rel != '.' else 'ROOT'
    for f in files:
        try:
            sz = os.path.getsize(os.path.join(root, f))
        except Exception:
            sz = 0
        agg[top][0] += 1
        agg[top][1] += sz
print('%-24s %6s %12s' % ('顶层', '文件数', '总大小'))
print('-' * 46)
tot_n = tot_s = 0
for k, v in sorted(agg.items(), key=lambda x: -x[1][1]):
    print('%-24s %6d %10.1f KB' % (k, v[0], v[1]/1024))
    tot_n += v[0]; tot_s += v[1]
print('-' * 46)
print('%-24s %6d %10.1f KB' % ('合计', tot_n, tot_s/1024))