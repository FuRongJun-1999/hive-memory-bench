# -*- coding: utf-8 -*-
import json, re
from pathlib import Path
R = Path(r'D:/1_ai/_hb_lab/r58')
d = json.loads((R/'e2e/run/pr64_v2/题目_选择题_150.json').read_text(encoding='utf-8'))
corp = R/'e2e/corpus'
texts = []
for f in sorted(corp.glob('*.md')):
    t = f.read_text(encoding='utf-8', errors='ignore')
    texts.append((f.name, re.sub(r'\s', '', t)))
total = sum(len(t) for _, t in texts)
print('真实对话语料: %d 个文件, 合计 %d 字符' % (len(texts), total))
print()
conv = [x for x in d if x['material'] == '对话']
print('=== 真实对话 %d 题：fact 能否在 e2e/corpus 定位 ===' % len(conv))
ok = 0; part = 0; bad = 0; bads = []
for x in conv:
    f = re.sub(r'\s', '', x['fact'])
    best = 0; bestf = ''
    for name, t in texts:
        L = min(len(f), 40)
        while L > 5:
            found = False
            for i in range(0, len(f) - L + 1):
                if f[i:i+L] in t:
                    found = True
                    break
            if found:
                break
            L -= 2
        if L > best:
            best = L; bestf = name
    if best >= 20:
        ok += 1
    elif best >= 10:
        part += 1
    else:
        bad += 1
        bads.append((x['qid'], best, x['fact'][:55]))
print('  fact 逐字片段 >=20 字: %d' % ok)
print('  10-19 字:              %d' % part)
print('  <10 字（未能定位）:     %d' % bad)
print()
if bads:
    print('  未能定位的题:')
    for qid, b, f in bads[:10]:
        print('    %s 最长%2d字 | %s' % (qid, b, f))