# -*- coding: utf-8 -*-
import subprocess, sys
from pathlib import Path
R = Path(r'D:/1_ai/_hb_lab/r58')
sk = R / 'persona-consistency/tools/score_k.py'
bank = R / 'persona-consistency/questions/K_persona_consistency_v2.json'
sc = R / 'e2e/run/lingshu_self_scores.json'
out = R / 'e2e/run/lingshu_self_Kv2_detail.json'
p = subprocess.run([sys.executable, '-X', 'utf8', str(sk), '--bank', str(bank), '--scores', str(sc), '--json', str(out)],
                   capture_output=True, text=True, encoding='utf-8', errors='replace')
print(p.stdout)
if p.stderr.strip():
    print('STDERR:', p.stderr[:500])