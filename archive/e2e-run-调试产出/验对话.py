# -*- coding: utf-8 -*-
import json, re
from pathlib import Path
R = Path(r'D:/1_ai/_hb_lab/r58')
d = json.loads((R/'e2e/run/pr64_v2/题目_选择题_150.json').read_text(encoding='utf-8'))

# 真实对话语料：e2e/corpus/*.md
corp = R/'e2e/corpus'
texts = []
for f in sorted(corp.glob('*.md')):
    t = f.read_text(encoding='utf-8', errors='ignore')
    texts.append((f.name, re.sub(r'\s', '', t)))
print('真实对话语料: %d 个文件, 合计 %d 字符' % (len(texts), sum(len(t) for _, t in texts)))
print()

conv = [x for x in d if x['material'] == '对话']
print('=== 真实对话 %d 题：fact 能否在 e2e/corpus 定位 ===' % len(conv))
ok = part = bad = 0
bads = []
for x in conv:
    f = re.sub(r'\s', '', x['fact'])
    best = 0; bestf = ''
    for name, t in texts:
        for L in range(min(len(f), 40), 5, -2):
            hit = False
            for i in range(0, len(f)-L+1):
                if f[i:i+L] in t:
                    hit = True; break
            if hit:
                if L > best: best, bestf = L, name
                break
    if best >= 20: ok += 1
    elif best >= 10: part += 1
    else:
        bad += 1
        bads.append((x['qid'], best, x['fact'][:55]))
print('  逐字片段>=20字:', ok)
  10-19字:', part)
  '<10字:', bad)
print()
if bads:
    print('  未能定位的:')
    for qid, b, f in bads[:8]:
        print('    %s 最长%d字 | %s' % (qid, b, f))