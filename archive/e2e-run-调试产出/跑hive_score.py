import subprocess, sys
from pathlib import Path
R = Path(r'D:/1_ai/_hb_lab/r58')
p = subprocess.run([sys.executable, '-X', 'utf8', str(R/'persona-consistency/tools/score_k.py'),
                    '--bank', str(R/'persona-consistency/questions/K_persona_consistency_v2.json'),
                    '--scores', str(R/'e2e/run/hive_Kv2_scores.json'),
                    '--json', str(R/'e2e/run/hive_Kv2_detail.json')],
                   capture_output=True, text=True, encoding='utf-8', errors='replace')
print(p.stdout)
if p.stderr.strip(): print('ERR:', p.stderr[:400])