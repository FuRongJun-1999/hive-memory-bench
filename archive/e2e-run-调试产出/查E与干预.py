# -*- coding: utf-8 -*-
import json
from pathlib import Path
from collections import Counter
R = Path(r'D:/1_ai/_hb_lab/r58')
d = json.loads((R/'questions/题目_选择题_182.json').read_text(encoding='utf-8'))['questions']

print('=== E 选项文本是否统一 ===')
es = Counter(x['options'].get('E','') for x in d)
for txt, c in es.most_common():
    print('  %3d 次 | %s' % (c, txt))
print()
print('  => 5 选 1 理论基线 20%，但 E 仅 1/182 是答案 → ', end='')
print('实际有效基线约 %.1f%%（4 选 1）' % (100/4))
print()
print('=== 干预轮 90 题的结构 ===')
iv = [x for x in d if x['kind'] == 'intervention']
print('  题数:', len(iv))
print('  答案分布:', dict(sorted(Counter(x['answer'] for x in iv).items())))
print('  rubric_source 样例:', iv[0]['rubric_source'])
print('  字段齐全:', all('required_count' in x and 'is_unknown' in x for x in iv))
print()
print('=== 干预轮首题 ===')
print(json.dumps({k: (v[:90] if isinstance(v,str) else v) for k,v in iv[0].items() if k != 'options'}, ensure_ascii=False, indent=1))
print('  选项:')
for k in 'ABCDE':
    if k in iv[0]['options']:
        mark = ' ★' if k == iv[0]['answer'] else ''
        print('    %s. %s%s' % (k, iv[0]['options'][k][:100], mark))
print()
print('=== 主轮 92 题（cards 来源）的结构 ===')
mc = [x for x in d if x['rubric_source'].startswith('cards/')]
print('  题数:', len(mc), '| 答案分布:', dict(sorted(Counter(x['answer'] for x in mc).items())))
print('  kind:', dict(Counter(x['kind'] for x in mc)))