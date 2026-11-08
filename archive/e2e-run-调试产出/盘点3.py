# -*- coding: utf-8 -*-
import os
from pathlib import Path
R = Path(r'D:/1_ai/_hb_lab/r58')
for top in ('e2e','questions','docs','results','systems','cards','persona-consistency','chain'):
    d = R/top
    if not d.exists(): continue
    print('=== %s/ ===' % top)
    subs = sorted([x for x in d.iterdir() if x.is_dir()])
    fs_ = sorted([x for x in d.iterdir() if x.is_file()])
    for s in subs:
        n = len(list(s.rglob('*')))
        sz = sum(f.stat().st_size for f in s.rglob('*') if f.is_file())
        print('   [dir] %-30s %4d 项 %8.1f KB' % (s.name + '/', n, sz/1024))
    for f in fs_[:12]:
        print('   [file] %-29s %8.1f KB' % (f.name[:29], f.stat().st_size/1024))
    if len(fs_) > 12:
        print('   ... 另有 %d 个文件' % (len(fs_) - 12))
    print()