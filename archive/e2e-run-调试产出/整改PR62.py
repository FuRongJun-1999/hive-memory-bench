# -*- coding: utf-8 -*-
import subprocess
from pathlib import Path
R = Path(r'D:/1_ai/_hb_lab/r58')
def run(*a):
    p = subprocess.run(list(a), capture_output=True, text=True, encoding='utf-8', errors='replace', cwd=str(R))
    return p.returncode, (p.stdout or '') + (p.stderr or '')

# 1) 建目录
(R / 'persona-consistency/results').mkdir(parents=True, exist_ok=True)

# 2) 删 100% 重复的题库（git rm）
for f in ('D_人设_v1.json', 'E_价值观_v1.json', 'F_安全_v1.json', 'K_一致性_v1.json'):
    rc, out = run('git', 'rm', '-q', 'roleplay/questions/' + f)
    print('删', f, '| rc', rc, out.strip()[:80])

# 3) 删重复判分器与对应读数
for f in ('roleplay/judge.py', 'roleplay/results/K_v1_readings.json'):
    rc, out = run('git', 'rm', '-q', f)
    print('删', f, '| rc', rc, out.strip()[:80])

# 4) 迁 K_v2 题库
rc, out = run('git', 'mv', 'roleplay/questions/K_一致性_v2.json', 'persona-consistency/questions/K_persona_consistency_v2.json')
print('迁 K_v2 题库 | rc', rc, out.strip()[:80])

# 5) 迁 score_k.py
rc, out = run('git', 'mv', 'roleplay/score_k.py', 'persona-consistency/tools/score_k.py')
print('迁 score_k.py | rc', rc, out.strip()[:80])

# 6) 迁读数
for src, dst in (('roleplay/results/K_v2_readings.json', 'persona-consistency/results/K_v2_readings.json'),
                 ('roleplay/results/D_readings.json', 'persona-consistency/results/D_readings.json')):
    rc, out = run('git', 'mv', src, dst)
    print('迁', src.split('/')[-1], '| rc', rc, out.strip()[:80])

print()
print('=== 整改后 roleplay/ 剩余 ===')
rc, out = run('git', 'status', '--short')
print(out[:1500])