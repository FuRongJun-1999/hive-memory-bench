# -*- coding: utf-8 -*-
import json
from pathlib import Path
import yaml
R = Path(r'D:/1_ai/_hb_lab/r58')
qs = {x['id']: x for x in json.loads((R/'questions/题目_选择题_238.json').read_text(encoding='utf-8'))['questions']}
for qid in ('o002','o005','o006','o007','o008'):
    x = qs[qid]
    card = yaml.safe_load((R/'cards'/(qid+'.yaml')).read_text(encoding='utf-8', errors='replace'))
    req = [r for r in card['rubric'] if r.get('required')]
    print('=' * 76)
    print('%s 答案=%s | rubric %d 条' % (qid, x['answer'], len(req)))
    print('问:', x['question'][:95])
    print('要点:')
    for r in req:
        print('   %s. %s' % (r['id'], r['point'][:72]))
    print()
    print('选项（答案 ★）:')
    for k in 'ABCD':
        if k not in x['options']: continue
        mark = ' ★' if k == x['answer'] else ''
        print('  %s%s: %s' % (k, mark, x['options'][k][:190]))
    print()