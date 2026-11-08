# -*- coding: utf-8 -*-
import json
from pathlib import Path
from collections import Counter
R = Path(r'D:/1_ai/_hb_lab/r58')
keys = json.loads((R / 'chain/keys/keys.json').read_text(encoding='utf-8'))
print('顶层类型:', type(keys).__name__)
if isinstance(keys, dict):
    print('顶层键:', list(keys.keys())[:12])
    for k, v in list(keys.items())[:3]:
        print(' ', k, '->', type(v).__name__, (len(v) if hasattr(v, '__len__') else ''))
    qs = keys.get('questions') or keys.get('keys') or keys.get('items')
else:
    qs = keys
print()
if qs:
    print('题数:', len(qs))
    q0 = qs[0]
    print('首题字段:', list(q0.keys()) if isinstance(q0, dict) else type(q0))
    print()
    print('首题样例:', json.dumps(q0, ensure_ascii=False)[:900])
    if isinstance(qs[0], dict):
        types = Counter(q.get('type') or q.get('qtype') or '?' for q in qs if isinstance(q, dict))
        print()
        print('问型分布:', dict(types))