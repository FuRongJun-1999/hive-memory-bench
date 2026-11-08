# -*- coding: utf-8 -*-
import subprocess, re, json
from pathlib import Path
R = Path(r'D:/1_ai/_hb_lab/r58')
def run(*a):
    p = subprocess.run(list(a), capture_output=True, text=True, encoding='utf-8', errors='replace', cwd=str(R))
    return p.returncode, (p.stdout or '') + (p.stderr or '')

print('=== 1) roleplay/ 剩余文件 ===')
for f in sorted((R / 'roleplay').rglob('*')):
    if f.is_file(): print('  ', f.relative_to(R), f.stat().st_size)

print()
print('=== 2) persona-consistency/ 新增文件 ===')
for name in ('questions/K_persona_consistency_v2.json', 'tools/score_k.py', 'results/K_v2_readings.json', 'results/D_readings.json'):
    p = R / 'persona-consistency' / name
    print('  %-46s %s' % (name, p.stat().st_size if p.exists() else '缺失'))

print()
print('=== 3) K_v2 题库完整性 ===')
p = R / 'persona-consistency/questions/K_persona_consistency_v2.json'
if p.exists():
    d = json.loads(p.read_text(encoding='utf-8'))
    dims = set(q.get('subface') for q in d)
    stages = {}
    for q in d:
        stages[q.get('stage')] = stages.get(q.get('stage'), 0) + 1
    print('  题数:', len(d), '| 维度:', len(dims), '| 阶段分布:', stages)

print()
print('=== 4) 断链检查（README 里引用的本地路径）===')
for md in ('README.md', 'roleplay/README.md', 'persona-consistency/README.md'):
    p = R / md
    if not p.exists(): continue
    txt = p.read_text(encoding='utf-8')
    links = re.findall(r'\]\(([^)]+\.(?:md|json|py))\)', txt)
    bad = []
    for l in links:
        t = (p.parent / l).resolve()
        if not t.exists(): bad.append(l)
    print('  %-32s 链接 %2d 个 | 断链 %d %s' % (md, len(links), len(bad), bad[:3]))

print()
print('=== 5) 是否残留对已删文件的引用 ===')
gone = ['D_人设_v1.json', 'E_价值观_v1.json', 'F_安全_v1.json', 'K_一致性_v1.json', 'roleplay/judge.py', 'roleplay/score_k.py', 'K_v1_readings.json']
for md in ('README.md', 'roleplay/README.md', 'persona-consistency/README.md'):
    p = R / md
    if not p.exists(): continue
    txt = p.read_text(encoding='utf-8')
    for g in gone:
        if g in txt:
            print('  %s 仍引用 %s' % (md, g))
print('  （无输出=无残留）')