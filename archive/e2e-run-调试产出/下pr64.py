# -*- coding: utf-8 -*-
import subprocess, json, base64, urllib.parse
from pathlib import Path
OUT = Path(r'D:/1_ai/_hb_lab/r58/e2e/run/pr64')
OUT.mkdir(parents=True, exist_ok=True)
REF = 'feat/mcq-150-selection-bank'
REPO = 'FuRongJun-1999/hive-memory-bench'
FILES = [
    'questions/题目_选择题_150.json',
    'questions/作答契约_选择题.md',
    'docs/选择题题库_设计说明_v1.0.md',
]
for f in FILES:
    q = urllib.parse.quote(f)
    p = subprocess.run(['gh','api', 'repos/%s/contents/%s?ref=%s' % (REPO, q, REF), '--jq', '.content'],
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    if p.returncode != 0:
        print('FAIL', f, p.stderr[:150]); continue
    try:
        data = base64.b64decode(''.join(p.stdout.split())).decode('utf-8')
    except Exception as e:
        print('DECODE FAIL', f, str(e)[:100]); continue
    name = f.split('/')[-1]
    (OUT / name).write_text(data, encoding='utf-8')
    print('OK %-42s %7d 字符' % (name, len(data)))
print()
print('下载目录:', OUT)