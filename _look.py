# -*- coding: utf-8 -*-
import subprocess, os
from pathlib import Path
R = Path(r'D:/1_ai/_hb_lab/r58')
print('=== archive/docs-旧分析25/ 里的文件 ===')
d = R/'archive/docs-旧分析25'
if d.exists():
    for f in sorted(d.iterdir()):
        print('  %-52s %7.1f KB' % (f.name, f.stat().st_size/1024))
print()
print('=== mcq/reasoning/ 现有 ===')
d2 = R/'mcq/reasoning'
for f in sorted(d2.iterdir()):
    print('  %-52s %7.1f KB' % (f.name, f.stat().st_size/1024))