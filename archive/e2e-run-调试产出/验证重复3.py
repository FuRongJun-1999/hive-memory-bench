# -*- coding: utf-8 -*-
import hashlib
from pathlib import Path
R = Path(r'D:/1_ai/_hb_lab/r58')
def h(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16] if p.exists() else None
for a, b in [
    ('roleplay/judge.py', 'persona-consistency/tools/judge.py'),
    ('roleplay/score_k.py', 'persona-consistency/tools/judge_K.py'),
]:
    pa, pb = R / a, R / b
    print('%-28s %s  %s' % (a, h(pa), pa.stat().st_size if pa.exists() else '-'))
    print('%-28s %s  %s' % (b, h(pb), pb.stat().st_size if pb.exists() else '-'))
    print('  相同:', h(pa) == h(pb) and pa.exists() and pb.exists())
    print()