# -*- coding: utf-8 -*-
from pathlib import Path
R = Path(r'D:/1_ai/_hb_lab/r58')
print('=== 仓库内所有 >=20KB 的文本类文件 ===')
exts = {'.md', '.json', '.txt', '.jsonl'}
files = []
for f in R.rglob('*'):
    if not f.is_file() or f.suffix.lower() not in exts: continue
    if '.git' in f.parts: continue
    try: sz = f.stat().st_size
    except Exception: continue
    if sz >= 20000: files.append((sz, str(f.relative_to(R))))
files.sort(reverse=True)
for sz, p in files[:35]:
    print('  %8d  %s' % (sz, p))
print('  共', len(files), '个 >=20KB 文件')
print()
print('=== corpus 类目录 ===')
for d in sorted(set(f.parent for f in R.rglob('*') if f.is_file() and 'corpus' in str(f.parent).lower())):
    n = len(list(d.glob('*')))
    print('  %-40s %d 项' % (str(d.relative_to(R)), n))