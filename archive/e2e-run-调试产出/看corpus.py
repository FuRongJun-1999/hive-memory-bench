# -*- coding: utf-8 -*-
import json
from pathlib import Path
from collections import Counter, defaultdict
R = Path(r'D:/1_ai/_hb_lab/r58')
corp = json.loads((R / 'chain/corpus/corpus.json').read_text(encoding='utf-8'))
print('corpus 类型:', type(corp).__name__)
if isinstance(corp, dict):
    print('键:', list(corp.keys())[:10])
    ch = corp.get('chapters') or corp.get('docs') or corp.get('segments')
else:
    ch = corp
print('段数:', len(ch) if ch else 0)
if ch:
    print('首段字段:', list(ch[0].keys()))
    print('首段前 300:', json.dumps(ch[0], ensure_ascii=False)[:300])
    print()
    cid = Counter(d.get('cid','?')[:6] for d in ch)
    print('按 doc 前缀分布（前 10）:', dict(list(cid.most_common(10))))
print()
keys = json.loads((R / 'chain/keys/keys.json').read_text(encoding='utf-8'))
bydoc = defaultdict(list)
for q in keys:
    bydoc[q['doc']].append(q)
print('文档数:', len(bydoc))
for d, qs in sorted(bydoc.items(), key=lambda t: -len(t[1]))[:6]:
    tc = Counter(q['type'] for q in qs)
    print('  %-10s 题 %3d | 问型 %s' % (d, len(qs), dict(tc)))