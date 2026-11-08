# -*- coding: utf-8 -*-
import json, re
from pathlib import Path
from collections import Counter
R = Path(r'D:/1_ai/_hb_lab/r58')
d = json.loads((R/'e2e/run/pr64/题目_选择题_150.json').read_text(encoding='utf-8'))
corpus = (R/'corpus/语料.md').read_text(encoding='utf-8', errors='replace')
def norm(s):
    return re.sub(r'[\s\u3000]+', '', s or '')
NC = norm(corpus)

print('=== 检查 2：fact 能否回原文（仅蜂巢指南 38 题可验） ===')
bee = [x for x in d if x['material'] == '蜂巢指南']
hit_exact = hit_part = miss = 0
misses = []
for x in bee:
    f = norm(x['fact'])
    if not f:
        continue
    if f in NC:
        hit_exact += 1
    else:
        # 找最长可匹配片段
        best = 0
        for L in range(len(f), 9, -1):
            found = any(f[i:i+L] in NC for i in range(0, len(f)-L+1))
            if found:
                best = L; break
        if best >= 12:
            hit_part += 1
        else:
            miss += 1
            misses.append((x['qid'], best, x['fact'][:50]))
print('  蜂巢题数:', len(bee))
print('  fact 逐字命中:', hit_exact)
print('  部分命中(>=12字):', hit_part)
print('  未命中:', miss)
for qid, b, f in misses[:8]:
    print('    %s 最长%d字 | %s' % (qid, b, f))

print()
print('=== 检查 4：题干是否含原文专名 ===')
# 简单判据：题干里出现 2 字以上大写/专名式词，或在 fact 里出现但题干也出现
import collections
pron_hits = []
for x in d:
    q = x['question']
    f = x['fact']
    # 提取 fact 中的书名号/引号内专名
    names = re.findall(r'[《「『]([^》」』]{2,8})[》」』]', f)
    for n in names:
        if n in q:
            pron_hits.append((x['qid'], n))
print('  题干含 fact 中书名号专名的:', len(pron_hits))
for q, n in pron_hits[:6]:
    print('    %s 专名「%s」' % (q, n))

print()
print('=== 检查 1：干扰项是否与正解重复/同义 ===')
bad_dup = []
bad_far = []
for x in d:
    ans = x['answer']
    ao = x['options'].get(ans, '')
    na = norm(ao)
    for k, v in x['options'].items():
        if k == ans: continue
        nv = norm(v)
        if not nv or not na: continue
        # 完全相同或互相包含
        if nv == na or (len(nv) >= 4 and nv in na) or (len(na) >= 4 and na in nv):
            bad_dup.append((x['qid'], k, v[:30], ao[:30]))
        # 与正解完全无共同字（过于离谱）
        if not (set(nv) & set(na)):
            bad_far.append((x['qid'], k, v[:30], ao[:30]))
print('  干扰项与正解重复/包含:', len(bad_dup))
for q,k,v,a in bad_dup[:6]:
    print('    %s %s「%s」 vs 正解「%s」' % (q,k,v,a))
print('  干扰项与正解零共同字符:', len(bad_far))
for q,k,v,a in bad_far[:4]:
    print('    %s %s「%s」 vs 正解「%s」' % (q,k,v,a))