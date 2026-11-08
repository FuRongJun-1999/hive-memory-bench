# -*- coding: utf-8 -*-
import subprocess
from collections import defaultdict
from pathlib import Path
R = Path(r'D:/1_ai/_hb_lab/r58')
p = subprocess.run(['git','ls-files'], capture_output=True, text=True, encoding='utf-8', errors='replace', cwd=str(R))
files = [f for f in p.stdout.split(chr(10)) if f.strip()]
print('追踪文件总数:', len(files))
print()
agg = defaultdict(lambda: [0, 0])
for f in files:
    if '/' in f:
        top = f.split('/')[0]
    else:
        top = '(根目录)'
    try:
        sz = (R/f).stat().st_size
    except Exception:
        sz = 0
    agg[top][0] += 1
    agg[top][1] += sz
print('%-22s %6s %12s' % ('目录', '文件数', '总大小'))
print('-' * 44)
for k, v in sorted(agg.items(), key=lambda x: -x[1][1]):
    print('%-22s %6d %11.1f KB' % (k, v[0], v[1]/1024))