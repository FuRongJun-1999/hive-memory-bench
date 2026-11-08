# -*- coding: utf-8 -*-
import json, re
from pathlib import Path
from collections import Counter
OLD = Path(r'D:/1_ai/_hb_lab/r58/e2e/run/pr64')
NEW = Path(r'D:/1_ai/_hb_lab/r58/e2e/run/pr64_v2')
old = {x['qid']: x for x in json.loads((OLD/'题目_选择题_150.json').read_text(encoding='utf-8'))}
new = {x['qid']: x for x in json.loads((NEW/'题目_选择题_150.json').read_text(encoding='utf-8'))}
print('题数: 旧 %d -> 新 %d' % (len(old), len(new)))

print()
print('=== 1) 4 题截断是否真修 ===')
for qid in ('S-026','S-041','S-073','S-138'):
    o, n = old[qid]['question'], new[qid]['question']
    changed = '✅ 已改' if o != n else '❌ 未改'
    print('  %s %s' % (qid, changed))
    print('     旧: %s' % o[:80])
    print('     新: %s' % n[:110])

print()
print('=== 2) S-044 / S-045 是否真改 ===')
for qid in ('S-044','S-045'):
    print('  %s' % qid)
    print('     旧: %s' % ' / '.join('%s.%s' % (k,v) for k,v in old[qid]['options'].items()))
    print('     新: %s' % ' / '.join('%s.%s' % (k,v) for k,v in new[qid]['options'].items()))
    print('     答案: %s -> %s' % (old[qid]['answer'], new[qid]['answer']))

print()
print('=== 3) S-005 / S-066 / S-067 是否被动过（应未动）===')
for qid in ('S-005','S-066','S-067'):
    same_q = old[qid]['question'] == new[qid]['question']
    same_o = old[qid]['options'] == new[qid]['options']
    print('  %s 题干%s 选项%s' % (qid, '未改' if same_q else '已改', '未改' if same_o else '已改'))

print()
print('=== 4) 全局回归 ===')
lens = [len(x['question']) for x in new.values()]
print('  题干 < 8 字:', sum(1 for l in lens if l < 8))
bad_end = [q for q,x in new.items() if re.search(r'[中，的、是啊了和与或对于在为把被从向：]$', x['question'].strip())]
print('  仍以连接词/标点结尾:', len(bad_end), bad_end[:6])
c = Counter(x['answer'] for x in new.values())
print('  答案分布:', dict(sorted(c.items())))
print('  选项数非4的:', sum(1 for x in new.values() if len(x['options']) != 4))
print('  qid 唯一:', len(new) == len(set(new)))
print('  有 fact 的:', sum(1 for x in new.values() if x.get('fact')))