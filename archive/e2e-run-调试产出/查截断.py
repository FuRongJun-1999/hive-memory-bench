# -*- coding: utf-8 -*-
import json, re
from pathlib import Path
R = Path(r'D:/1_ai/_hb_lab/r58')
d = json.loads((R/'e2e/run/pr64/题目_选择题_150.json').read_text(encoding='utf-8'))
print('=== 题干完整性检查 ===')
bad = []
for x in d:
    q = x['question'].strip()
    issues = []
    if len(q) < 8:
        issues.append('过短(%d字)' % len(q))
    # 以连接词/介词结尾 → 很可能截断
    if re.search(r'[中，的、是啊了和与或对于在为把被从向]$', q):
        issues.append('以连接词结尾')
    if q.endswith(('，', '、', '：', '（')):
        issues.append('以标点结尾')
    # 选项过短
    shortopt = [k for k, v in x['options'].items() if len(v.strip()) < 2]
    if shortopt:
        issues.append('选项过短%s' % shortopt)
    if issues:
        bad.append((x['qid'], x['material'], q, issues))
print('  有问题的题:', len(bad), '/', len(d))
for qid, m, q, iss in bad:
    print('    %s [%s] %s' % (qid, m, ';'.join(iss)))
    print('        题干: %s' % q[:70])
print()
print('=== 题干长度分布 ===')
lens = sorted(len(x['question']) for x in d)
print('  最短 %d | 中位 %d | 最长 %d' % (lens[0], lens[len(lens)//2], lens[-1]))
print('  <15 字的题:', sum(1 for x in d if len(x['question']) < 15))
print()
print('=== 选项长度一致性（4 选项长度差异过大的题）===')
big = []
for x in d:
    ls = [len(v) for v in x['options'].values()]
    if max(ls) - min(ls) > 15:
        big.append((x['qid'], ls, list(x['options'].values())))
print('  差异>15字的:', len(big))
for qid, ls, opts in big[:5]:
    print('    %s %s | %s' % (qid, ls, ' / '.join(o[:25] for o in opts)))