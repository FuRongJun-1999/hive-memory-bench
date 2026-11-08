# -*- coding: utf-8 -*-
import json
from pathlib import Path
p = Path(r'D:/1_ai/_hb_lab/r58/e2e/run/meow_probe/results.jsonl')
if not p.exists():
    print('还没有结果文件')
else:
    rows = [json.loads(l) for l in p.read_text(encoding='utf-8').splitlines() if l.strip()]
    print('已完成 %d 题' % len(rows))
    for r in rows:
        print('  %-24s %-4s %4ds 工具%2d | %s' % (r['qid'], r['type'], r['dt'], len(r['tools']), r['answer'][:70].replace(chr(10),' ')))