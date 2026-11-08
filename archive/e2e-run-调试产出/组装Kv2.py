# -*- coding: utf-8 -*-
"""把三轮答案组装成 score_k.py 需要的 scores.json，并出逐维分数。"""
import json, re
from pathlib import Path
R = Path(r'D:/1_ai/_hb_lab/r58')
OUT = R / 'e2e/run'
BANK = R / 'persona-consistency/questions/K_persona_consistency_v2.json'

bank = json.loads(BANK.read_text(encoding='utf-8'))
bank.sort(key=lambda q: q['qid'])
L12 = [q for q in bank if q['stage'] == 'T1/T2']
L3 = [q for q in bank if q['stage'] == 'T3']
print('题库: T1/T2', len(L12), '| T3', len(L3))

def parse_nums(path, expect):
    if not path.exists():
        return None, 'file missing'
    txt = path.read_text(encoding='utf-8')
    m = re.search(r'\{.*\}', txt, re.S)
    if not m:
        nums = [int(x) for x in re.findall(r'\b[1-5]\b', txt)]
        return (nums[:expect], 'regex') if len(nums) >= expect else (None, 'only %d nums' % len(nums))
    try:
        j = json.loads(m.group(0))
    except Exception as e:
        nums = [int(x) for x in re.findall(r'\b[1-5]\b', m.group(0))]
        return (nums[:expect], 'regex2') if len(nums) >= expect else (None, 'bad json %s' % str(e)[:40])
    for k in ('scores', 'round1', 'round2', 'round3', 'answers'):
        if isinstance(j.get(k), list):
            nums = [int(v) for v in j[k] if isinstance(v, (int, float))]
            return (nums[:expect], 'json:' + k) if len(nums) >= expect else (None, 'only %d' % len(nums))
    for v in j.values():
        if isinstance(v, list) and v and isinstance(v[0], (int, float)):
            nums = [int(x) for x in v]
            return (nums[:expect], 'json:first-list') if len(nums) >= expect else (None, 'only %d' % len(nums))
    return None, 'no numeric array'

rounds = {}
for tag, expect, rname in (('r1', len(L12), 'round1'), ('r2', len(L12), 'round2'), ('r3', len(L3), 'round3')):
    nums, how = parse_nums(OUT / ('lingshu_Kv2_%s_answer.txt' % tag), expect)
    print('%-3s 期望%3d 实得%s  [%s]' % (tag, expect, len(nums) if nums else 0, how))
    rounds[rname] = nums

if all(rounds[r] for r in ('round1','round2','round3')):
    scores = []
    for i, q in enumerate(L12):
        scores.append({'round': 'round1', 'qid': q['qid'], 'score': rounds['round1'][i]})
        scores.append({'round': 'round2', 'qid': q['qid'], 'score': rounds['round2'][i]})
    for i, q in enumerate(L3):
        scores.append({'round': 'round3', 'qid': q['qid'], 'score': rounds['round3'][i]})
    p = OUT / 'lingshu_Kv2_scores.json'
    p.write_text(json.dumps(scores, ensure_ascii=False, indent=1), encoding='utf-8')
    print()
    print('已写 scores.json:', len(scores), '条 →', p)
else:
    print()
    print('三轮未齐，暂不组装')