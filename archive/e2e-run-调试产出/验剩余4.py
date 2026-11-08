# -*- coding: utf-8 -*-
import re
from pathlib import Path
R = Path(r'D:/1_ai/_hb_lab/r58')
texts = {}
for f in sorted((R/'e2e/corpus').glob('*.md')):
    texts[f.name] = re.sub(r'\s', '', f.read_text(encoding='utf-8', errors='ignore'))
KEYS = {
  'S-072': ['关于过去', '紧迫性', '根本不匹配', '不匹配'],
  'S-073': ['急', '极简', '触发', '响应模式', '切换'],
  'S-145': ['非语言', '无法替代', '替代它们'],
  'S-149': ['二元', '问题—回答', '问题-回答', '接收输入'],
}
for qid, kws in KEYS.items():
    print('=== %s ===' % qid)
    for kw in kws:
        hit = [(n, t.count(kw), t.find(kw)) for n, t in texts.items() if kw in t]
        if hit:
            for n, c, i in sorted(hit, key=lambda x: -x[1])[:2]:
                seg = texts[n][max(0,i-45):i+65]
                print('  「%s」 %s ×%d | ...%s...' % (kw, n, c, seg))
        else:
            print('  「%s」 未命中' % kw)
    print()