# -*- coding: utf-8 -*-
import json, re
from pathlib import Path
from collections import Counter
R = Path(r'D:/1_ai/_hb_lab/r58')
d = json.loads((R/'questions/题目_选择题_182.json').read_text(encoding='utf-8'))['questions']
print('题数:', len(d))
print('kind 分布:', dict(Counter(x['kind'] for x in d)))
print('答案分布:', dict(sorted(Counter(x['answer'] for x in d).items())))
print('is_unknown=True 的:', sum(1 for x in d if x.get('is_unknown')))
print('rubric_source 前缀:', dict(Counter(x['rubric_source'].split('/')[0] if '/' in x['rubric_source'] else x['rubric_source'][:12] for x in d)))
print()
print('=== 检查 A：长短版干扰项（一选项是另一选项的前缀/删尾）===')
def n(s): return re.sub(r'\s', '', s)
dups = []
for x in d:
    opts = x['options']
    keys = [k for k in 'ABCDE' if k in opts]
    for i in range(len(keys)):
        for j in range(i+1, len(keys)):
            a, b = n(opts[keys[i]]), n(opts[keys[j]])
            if not a or not b: continue
            short, long_ = (a, b) if len(a) < len(b) else (b, a)
            if len(short) < 20: continue
            # 短的是长的前缀，且长度占比高
            if long_.startswith(short) and len(short)/len(long_) > 0.85:
                dups.append((x['id'], keys[i], keys[j], len(short), len(long_), round(len(short)/len(long_)*100)))
print('  长短版嫌疑:', len(dups))
for qid, k1, k2, l1, l2, pct in dups[:12]:
    print('    %s %s(%d字) vs %s(%d字) 覆盖%d%%' % (qid, k1, l1, k2, l2, pct))
print()
print('=== 检查 B：选项长度极差 ===')
big = []
for x in d:
    ls = [len(v) for v in x['options'].values()]
    if max(ls) - min(ls) > 100:
        big.append((x['id'], min(ls), max(ls), max(ls)-min(ls)))
print('  极差>100字:', len(big))
for qid, lo, hi, diff in big[:8]:
    print('    %s 最短%d 最长%d 差%d' % (qid, lo, hi, diff))
print()
print('=== 检查 C：E 选项（我不确定）被用作答案的次数 ===')
eans = [x['id'] for x in d if x['answer'] == 'E']
print('  E 是答案:', len(eans), '/', len(d))
eans_unknown = [x['id'] for x in d if x['answer'] == 'E' and x.get('is_unknown')]
print('  其中 is_unknown=True:', len(eans_unknown))
print('  样例:', eans[:6])