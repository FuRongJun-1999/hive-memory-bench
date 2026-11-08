# -*- coding: utf-8 -*-
import subprocess, json
from pathlib import Path
R = Path(r'D:/1_ai/_hb_lab/r58')
def run(*a):
    p = subprocess.run(list(a), capture_output=True, text=True, encoding='utf-8', errors='replace', cwd=str(R))
    return p.returncode, (p.stdout or '') + (p.stderr or '')
print('=== main 上的 questions/ ===')
rc, out = run('git','ls-tree','--name-only','origin/main','questions/')
print(out.strip() if rc==0 else 'ERR')
print()
print('=== 当前分支 questions/ ===')
rc, out = run('git','ls-tree','--name-only','HEAD','questions/')
print(out.strip() if rc==0 else 'ERR')
print()
print('=== 两套选择题是否同源 ===')
rc, out = run('git','cat-file','-s','origin/main:questions/题目_选择题_150.json')
print('main 的 150 题:', out.strip(), '字节' if rc==0 else 'ERR')
rc, out = run('git','cat-file','-s','HEAD:questions/题目_选择题_238.json')
print('HEAD 的 238 题:', out.strip(), '字节' if rc==0 else 'ERR')
print()
# 150 题的 material 分布
p = subprocess.run(['git','show','origin/main:questions/题目_选择题_150.json'], capture_output=True, text=True, encoding='utf-8')
if p.returncode == 0:
    d = json.loads(p.stdout)
    from collections import Counter
    print('150 题 material:', dict(Counter(x.get('material') for x in d)))
    print('150 题字段:', sorted(d[0].keys()))
print()
# 238 题字段
d2 = json.loads((R/'questions/题目_选择题_238.json').read_text(encoding='utf-8'))['questions']
print('238 题字段:', sorted(d2[0].keys()))
print('238 题 kind:', dict(Counter(x['kind'] for x in d2)))