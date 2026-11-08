# -*- coding: utf-8 -*-
import json, re
from pathlib import Path
R = Path(r'D:/1_ai/_hb_lab/r58')
corpus = (R/'corpus/语料.md').read_text(encoding='utf-8', errors='replace')
d = {x['qid']: x for x in json.loads((R/'e2e/run/pr64/题目_选择题_150.json').read_text(encoding='utf-8'))}

for qid in ('S-049', 'S-054', 'S-043'):
    x = d[qid]
    print('=' * 70)
    print('%s | %s' % (qid, x['material']))
    print('题干:', x['question'])
    for k, v in x['options'].items():
        mark = ' <<<' if k == x['answer'] else ''
        print('  %s. %s%s' % (k, v, mark))
    print('fact:', x['fact'])
    # 从 fact 提取关键词去原文找
    kws = re.findall(r'[\u4e00-\u9fa5]{2,4}', x['fact'])
    found = [k for k in set(kws) if k in corpus]
    print('fact 里在原文出现的词:', found[:12])
    # 找 fact 中最长可匹配片段
    nf = re.sub(r'\s', '', x['fact'])
    nc = re.sub(r'\s', '', corpus)
    best, bi = 0, -1
    for L in range(len(nf), 3, -1):
        for i in range(len(nf)-L+1):
            if nf[i:i+L] in nc:
                best, bi = L, i; break
        if best: break
    print('最长可匹配片段: %d 字 -> 「%s」' % (best, nf[bi:bi+best] if best else ''))
    print()

print('=' * 70)
print('=== 原文里「信用点」的 7 处上下文 ===')
for m in re.finditer('信用点', corpus):
    s = max(0, m.start()-60); e = min(len(corpus), m.end()+60)
    print('  ...', corpus[s:e].replace(chr(10), ' '), '...')