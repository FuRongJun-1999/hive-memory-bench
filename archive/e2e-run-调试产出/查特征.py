# -*- coding: utf-8 -*-
import re
from pathlib import Path
R = Path(r'D:/1_ai/_hb_lab/r58')
corp = R/'e2e/corpus'
texts = {}
for f in sorted(corp.glob('*.md')):
    texts[f.name] = re.sub(r'\s', '', f.read_text(encoding='utf-8', errors='ignore'))
# 用短特征词定位 S-066~S-073 这批「紧急状态」题源
for kw in ('余裕', '紧急状态', '极简信号', '问题—回答', '全知者'):
    print('=== 「%s」 ===' % kw)
    for name, t in texts.items():
        c = t.count(kw)
        if c:
            i = t.find(kw)
            print('  %-40s %3d 次 | ...%s...' % (name, c, t[max(0,i-50):i+70]))
    print()