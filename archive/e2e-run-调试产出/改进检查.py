# -*- coding: utf-8 -*-
import json, re
from pathlib import Path
R = Path(r'D:/1_ai/_hb_lab/r58')
corpus = re.sub(r'\s', '', (R/'corpus/语料.md').read_text(encoding='utf-8', errors='replace'))
d = json.loads((R/'e2e/run/pr64/题目_选择题_150.json').read_text(encoding='utf-8'))
bee = [x for x in d if x['material'] == '蜂巢指南']

def entities(s):
    """提取可作为定位锚的实体：数字、带数字的量、书名号内容、2-4 字专名词"""
    out = set()
    for m in re.findall(r'[0-9]+', s):
        out.add(m)
    for m in re.findall(r'[《「『]([^》」』]{2,12})[》」』]', s):
        out.add(m)
    for m in re.findall(r'[\u4e00-\u9fa5]{2,4}', s):
        out.add(m)
    return out

print('=== 检查 2（改进）：fact 的实体能否在原文邻近定位 ===')
ok = partial = bad = 0
bads = []
for x in bee:
    f = x['fact']
    ents = entities(f)
    # 只留原文里存在的实体
    intext = [e for e in ents if e in corpus]
    if not intext:
        bad += 1; bads.append((x['qid'], 0, 0, f[:50])); continue
    # 取最长实体作锚，看其他实体是否在其 ±400 字窗口内
    anchor = max(intext, key=len)
    win = 400
    near = 0
    for e in intext:
        for m in re.finditer(re.escape(e), corpus):
            a = max(0, m.start() - win); b = min(len(corpus), m.end() + win)
            if anchor in corpus[a:b]:
                near += 1; break
    ratio = near / len(intext)
    if ratio >= 0.5:
        ok += 1
    elif ratio > 0:
        partial += 1
    else:
        bad += 1; bads.append((x['qid'], len(intext), round(ratio,2), f[:50]))
print('  实体可在原文邻近定位(?50%%): %d/%d' % (ok, len(bee)))
print('  部分可定位: %d' % partial)
print('  无法定位: %d' % bad)
for qid, n, r, f in bads[:6]:
    print('    %s 原文实体%d个 邻近率%.2f | %s' % (qid, n, r, f))

print()
print('=== 检查 1（改进）：干扰项是否「同句式只改关键信息」 ===')
import statistics
struct_ok = struct_bad = 0
struct_bads = []
for x in d:
    opts = list(x['options'].values())
    if len(opts) != 4:
        struct_bads.append((x['qid'], '选项数%d' % len(opts))); continue
    # 两两的最长公共前缀长度 / 最短长度
    sims = []
    for i in range(4):
        for j in range(i+1, 4):
            a, b = opts[i], opts[j]
            L = 0
            for ca, cb in zip(a, b):
                if ca == cb: L += 1
                else: break
            sims.append(L / max(1, min(len(a), len(b))))
    avg = sum(sims)/len(sims)
    if avg >= 0.35:
        struct_ok += 1
    else:
        struct_bad += 1
        struct_bads.append((x['qid'], round(avg,2), opts))
print('  选项同句式(公共前缀>=35%%): %d/%d' % (struct_ok, len(d)))
print('  结构性偏弱: %d' % struct_bad)
for qid, a, o in struct_bads[:6]:
    print('    %s 相似度%.2f | %s' % (qid, a, ' / '.join(x[:14] for x in o)))

print()
print('=== 检查 3：答案分布 ===')
from collections import Counter
c = Counter(x['answer'] for x in d)
print('  ', dict(c), '| 极差', max(c.values())-min(c.values()))
# 分组看
print('  按材料分组:')
for m in ('秦吏','毛选','蜂巢指南','对话'):
    sub = [x['answer'] for x in d if x['material']==m]
    print('    %-8s n=%2d %s' % (m, len(sub), dict(Counter(sub))))