# -*- coding: utf-8 -*-
import subprocess
def run(*a):
    p = subprocess.run(list(a), capture_output=True, text=True, encoding='utf-8', errors='replace', cwd=r'D:/1_ai/_hb_lab/r58')
    return p.returncode, (p.stdout or '') + (p.stderr or '')
print('=== fetch ===')
rc, out = run('git','fetch','origin','feat/mcq-150-selection-bank')
print('rc', rc, out[-300:])
print()
print('=== 远端分支确认 ===')
rc, out = run('git','ls-remote','--heads','origin','feat/mcq-150-selection-bank')
print(out.strip()[:200])
print()
print('=== 改动文件 ===')
rc, out = run('git','diff','--stat','origin/main...origin/feat/mcq-150-selection-bank')
print('rc', rc)
print(out[-800:] if out else '(空)')