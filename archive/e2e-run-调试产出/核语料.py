# -*- coding: utf-8 -*-
import json
from pathlib import Path
from collections import Counter
R = Path(r'D:/1_ai/_hb_lab/r58')
corpus = (R/'corpus/语料.md').read_text(encoding='utf-8', errors='replace')
print('=== corpus/语料.md 里的关键词 ===')
for k in ('陈默', '信用点', '李振国', '机器人协理员', '合成餐', '求知园'):
    print('  %-12s %s (%d 次)' % (k, k in corpus, corpus.count(k)))
print()
# 看蜂巢指南 38 题的 question 里有什么专名
d = json.loads((R/'e2e/run/pr64/题目_选择题_150.json').read_text(encoding='utf-8'))
bee = [x for x in d if x['material'] == '蜂巢指南']
print('=== 蜂巢 38 题的题干样例 ===')
for x in bee[:6]:
    print('  %s | %s' % (x['qid'], x['question'][:45]))
    print('       fact: %s' % x['fact'][:60])
print()
# 整个仓库里搜陈默
print('=== 全仓搜「陈默」 ===')
hits = []
for f in R.rglob('*.md'):
    try:
        t = f.read_text(encoding='utf-8', errors='replace')
    except Exception:
        continue
    if '陈默' in t:
        hits.append((str(f.relative_to(R)), t.count('陈默')))
for h in sorted(hits, key=lambda x: -x[1])[:8]:
    print('  %-50s %d 次' % h)
print('  共', len(hits), '个文件含「陈默」')