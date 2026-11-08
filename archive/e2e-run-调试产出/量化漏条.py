# -*- coding: utf-8 -*-
import json, re
from pathlib import Path
from collections import Counter
import yaml
R = Path(r'D:/1_ai/_hb_lab/r58')
qs = json.loads((R/'questions/题目_选择题_238.json').read_text(encoding='utf-8'))['questions']

def hit(pat, text):
    if pat.startswith('re: '):
        try: return re.search(pat[4:], text) is not None
        except re.error: return False
    return pat in text

def cov(option, rubric):
    req = [r for r in rubric if r.get('required')]
    if not req: return None
    h = sum(1 for it in req if any(hit(p, option) for p in (it.get('any_of') or [])))
    return h/len(req), h, len(req)

rows = []
missing_card = []
for x in qs:
    qid = x['id']
    card_p = R/'cards'/(qid + '.yaml')
    if not card_p.exists():
        missing_card.append(qid); continue
    try:
        card = yaml.safe_load(card_p.read_text(encoding='utf-8', errors='replace'))
    except Exception as e:
        missing_card.append(qid); continue
    rub = card.get('rubric') or []
    anskey = x['answer']
    ans_cov = cov(x['options'].get(anskey,''), rub)
    worst = None; worst_k = None
    for k in 'ABCD':
        if k not in x['options'] or k == anskey: continue
        c = cov(x['options'][k], rub)
        if c and (worst is None or c[0] > worst[0]):
            worst, worst_k = c, k
    if ans_cov and worst:
        rows.append((qid, x['kind'], round(ans_cov[0],2), anskey, worst_k, round(worst[0],2), worst[1], worst[2]))

print('有 card 的题:', len(rows), '| 无 card:', len(missing_card), missing_card[:8])
print()
print('=== 最高干扰项覆盖率分布（any_of 粗算，偏高估）===')
b = Counter()
for r in rows:
    v = r[5]
    b['>=1.0' if v >= 0.999 else '90-99%' if v >= 0.9 else '70-89%' if v >= 0.7 else '50-69%' if v >= 0.5 else '<50%'] += 1
for k in ('>=1.0','90-99%','70-89%','50-69%','<50%'):
    print('  %-8s %d 题' % (k, b[k]))
print()
print('=== 干扰项覆盖 >= 70% 的题（需重点人读）===')
sus = [r for r in rows if r[5] >= 0.7]
print('  共 %d 题' % len(sus))
for r in sorted(sus, key=lambda r: -r[5])[:20]:
    print('    %-8s [%-12s] 答案%s覆盖%.0f%% | 干扰%s覆盖%.0f%% (%d/%d)' % (r[0], r[1], r[3], r[2]*100, r[4], r[5]*100, r[6], r[7]))