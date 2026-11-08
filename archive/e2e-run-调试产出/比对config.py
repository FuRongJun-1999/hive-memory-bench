# -*- coding: utf-8 -*-
import json
from pathlib import Path
for name in ('config.local.json', 'config.local.json.bak-2026-10-28'):
    p = Path(r'D:/program/dsh-memory-main/hive') / name
    if not p.exists():
        print(name, '不存在'); continue
    try:
        d = json.loads(p.read_text(encoding='utf-8'))
    except Exception as e:
        print(name, '解析失败', str(e)[:60]); continue
    print('===', name, '===')
    for k in ('HIVE_API_BASE','HIVE_API_KEY','HIVE_WEB_SEARCH_KEY','HIVE_ORCH_TOKEN_FILE'):
        v = d.get(k)
        if isinstance(v, str) and ('KEY' in k or 'TOKEN' in k):
            print('  %-24s <len=%d>' % (k, len(v)))
        else:
            print('  %-24s %s' % (k, v))
    print()