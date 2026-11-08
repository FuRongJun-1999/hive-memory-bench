# -*- coding: utf-8 -*-
import json
from pathlib import Path
R = Path(r'D:/1_ai/_hb_lab/r58')
# 语料.md
p = R/'corpus/语料.md'
if p.exists():
    t = p.read_text(encoding='utf-8', errors='replace')
    print('=== corpus/语料.md ===')
    print('字符:', len(t))
    for k in ('秦吏', '毛选', '毛泽东', '蜂巢', '派出所', '警官学院'):
        print('  含「%s」: %s (%d 次)' % (k, k in t, t.count(k)))
    print('  开头 200:', t[:200].replace(chr(10),' '))
print()
for n in ('u01','u02','u03'):
    q = R/'corpus'/(n + '.json')
    if not q.exists(): continue
    try:
        j = json.loads(q.read_text(encoding='utf-8'))
    except Exception as e:
        print(n, '解析失败', str(e)[:60]); continue
    print('=== %s.json ===' % n, type(j).__name__)
    if isinstance(j, dict):
        print('  键:', list(j.keys())[:8])
    elif isinstance(j, list):
        print('  条数:', len(j), '| 首项键:', list(j[0].keys())[:8] if j and isinstance(j[0], dict) else '-')