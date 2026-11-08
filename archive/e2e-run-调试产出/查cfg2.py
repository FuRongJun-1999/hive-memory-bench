# -*- coding: utf-8 -*-
import json, datetime
from pathlib import Path
p = Path(r'D:/program/dsh-memory-main/hive/config.local.json')
d = json.loads(p.read_text(encoding='utf-8'))
print('=== config.local.json ===')
for k in ('HIVE_API_BASE','HIVE_API_KEY','HIVE_WORKERS'):
    v = d.get(k)
    if k.endswith('KEY'):
        print('%-16s <存在=%s, len=%d>' % (k, bool(v), len(v) if v else 0))
    else:
        print('%-16s %s' % (k, v))
print()
print('mtime:', datetime.datetime.fromtimestamp(p.stat().st_mtime).isoformat())

# 对比 serve 中记录的值
import subprocess
r = subprocess.run(['python','-c','''
import json,sys
from pathlib import Path
p=Path(r"D:/program/dsh-memory-main/hive/jobs")
cfgs=[q for q in p.parent.glob("config*.json")]
print("jobs dir ok")
'''], capture_output=True, text=True)