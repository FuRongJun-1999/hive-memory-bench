# -*- coding: utf-8 -*-
import subprocess, os
from pathlib import Path
R = Path(r'D:/1_ai/_hb_lab/r58')
def run(*a, **kw):
    p = subprocess.run(list(a), capture_output=True, text=True, encoding='utf-8', errors='replace', cwd=str(R), **kw)
    return p.returncode, (p.stdout or '') + (p.stderr or '')

# Step 1: 建三类目录
for d in ('mcq/e2e-simple', 'mcq/reasoning', 'mcq/persona', 'archive'):
    (R/d).mkdir(parents=True, exist_ok=True)
print('Step1 目录已建')

# Step 2: 从 main 拉 150 题 → mcq/e2e-simple/
rc, out = run('git','show','origin/main:questions/题目_选择题_150.json')
if rc == 0:
    (R/'mcq/e2e-simple/题目_选择题_150.json').write_text(out, encoding='utf-8')
    print('Step2 150 题已从 main 拉入 (%d 字节)' % len(out))
else:
    print('Step2 FAIL', out[:150])
rc, out = run('git','show','origin/main:questions/作答契约_选择题.md')
if rc == 0:
    (R/'mcq/e2e-simple/作答契约_选择题.md').write_text(out, encoding='utf-8')
    print('Step2 契约已拉入')

# Step 3: 238 题 → mcq/reasoning/
rc, out = run('git','mv','questions/题目_选择题_238.json','mcq/reasoning/题目_选择题_238.json')
print('Step3 238 题迁移:', rc, out.strip()[:100])

# Step 4: K 面题库 → mcq/persona/
for f in ('K_persona_consistency.json', 'K_persona_consistency_v2.json', 'K_面作业规程_v1.0.md'):
    src = 'persona-consistency/' + f
    if (R/src).exists():
        rc, out = run('git','mv', src, 'mcq/persona/' + f)
        print('Step4 %s: %s' % (f, 'ok' if rc==0 else out.strip()[:80]))
## 作业规程在根目录 persona-consistency/
if (R/'persona-consistency/K_面作业规程_v1.0.md').exists():
    rc, out = run('git','mv','persona-consistency/K_面作业规程_v1.0.md','mcq/persona/K_面作业规程_v1.0.md')
    print('Step4 作业规程:', rc)

print()
print('=== 新结构 ===')
for d in ('mcq/e2e-simple', 'mcq/reasoning', 'mcq/persona'):
    p = R/d
    fs_ = sorted(x.name for x in p.iterdir() if x.is_file()) if p.exists() else []
    print('  %-20s %s' % (d + '/', fs_))