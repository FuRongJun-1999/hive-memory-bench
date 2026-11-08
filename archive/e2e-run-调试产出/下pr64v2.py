# -*- coding: utf-8 -*-
import subprocess, base64, urllib.parse
from pathlib import Path
OUT = Path(r'D:/1_ai/_hb_lab/r58/e2e/run/pr64_v2')
OUT.mkdir(parents=True, exist_ok=True)
REF = 'b3f5f76b7140191a6bb8e2efe2c28fb45ecba944'
REPO = 'FuRongJun-1999/hive-memory-bench'
FILES = [
    'questions/题目_选择题_150.json',
    'questions/作答契约_选择题.md',
    'docs/选择题题库_设计说明_v1.0.md',
    'README.md',
]
for f in FILES:
    p = subprocess.run(['gh','api','repos/%s/contents/%s?ref=%s' % (REPO, urllib.parse.quote(f), REF), '--jq', '.content'],
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    if p.returncode != 0:
        print('FAIL', f, p.stderr[:120]); continue
    try:
        data = base64.b64decode(''.join(p.stdout.split())).decode('utf-8')
    except Exception as e:
        print('DECODE FAIL', f, str(e)[:80]); continue
    name = f.split('/')[-1]
    (OUT / name).write_text(data, encoding='utf-8')
    print('OK %-40s %7d' % (name, len(data)))