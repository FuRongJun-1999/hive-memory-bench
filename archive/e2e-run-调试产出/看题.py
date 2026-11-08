# -*- coding: utf-8 -*-
import json
from pathlib import Path
from collections import Counter
P = Path(r'D:/1_ai/_hb_lab/r58/e2e/run/pr64/题目_选择题_150.json')
d = json.loads(P.read_text(encoding='utf-8'))
print('题数:', len(d))
print('字段:', sorted(d[0].keys()))
print()
print('=== 首题 ===')
print(json.dumps(d[0], ensure_ascii=False, indent=1)[:1200])
print()
print('=== 统计 ===')
print('按 doc:', dict(Counter(x.get('doc') for x in d)))
print('答案分布:', dict(Counter(x.get('answer') for x in d)))
print('有 fact 的:', sum(1 for x in d if x.get('fact')))