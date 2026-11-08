# -*- coding: utf-8 -*-
import subprocess, os, shutil
from pathlib import Path
R = Path(r'D:/1_ai/_hb_lab/r58')
def run(*a):
    p = subprocess.run(list(a), capture_output=True, text=True, encoding='utf-8', errors='replace', cwd=str(R))
    return p.returncode, (p.stdout or '') + (p.stderr or '')

# 1) README 用我们的
rc, out = run('git','checkout','--ours','README.md')
print('1) README 用本地版:', rc)
run('git','add','README.md')

# 2/3) questions/ 的两个文件：已在 mcq/e2e-simple/，删冲突产物
for f in ('archive/题目_选择题_150.json', 'archive/作答契约_选择题.md'):
    if (R/f).exists():
        run('git','rm','-q','-f', f)
        print('2/3) 删', f)

# 4) docs/选择题题库_设计说明_v1.0.md -> mcq/e2e-simple/设计说明_v1.0.md
src = R/'archive/docs-旧分析25/选择题题库_设计说明_v1.0.md'
if src.exists():
    (R/'mcq/e2e-simple').mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(R/'mcq/e2e-simple/设计说明_v1.0.md'))
    print('4) 150 题设计说明 -> mcq/e2e-simple/')

# 5) 238 题设计说明 -> mcq/reasoning/设计说明_v1.0.md
src2 = R/'archive/docs-旧分析25/选择题改造与三方案对照_v1.0.md'
if src2.exists():
    (R/'mcq/reasoning').mkdir(parents=True, exist_ok=True)
    shutil.move(str(src2), str(R/'mcq/reasoning/设计说明_v1.0.md'))
    print('5) 238 题设计说明 -> mcq/reasoning/')

# 6) 处理 main 上新增的 docs/选择题题库_设计说明_v1.0.md（冲突项）
for f in ('archive/docs-旧分析25/选择题题库_设计说明_v1.0.md',):
    if (R/f).exists():
        run('git','rm','-q','-f', f)
        print('6) 删重复', f)

run('git','add','-A')
rc, out = run('git','status','--short')
conf = [l for l in out.split(chr(10)) if l.strip() and l.strip()[:2] in ('UU','AA','DD','AU','UA','DU','UD')]
print()
print('剩余冲突:', len(conf))
for l in conf[:10]: print('  ', l[:100])
print()
print('=== 最终 mcq/ ===')
for sub in ('e2e-simple','reasoning','persona'):
    p = R/'mcq'/sub
    if p.exists():
        for f in sorted(p.iterdir()):
            print('  %-24s %-42s %7.1f KB' % (sub+'/', f.name, f.stat().st_size/1024))