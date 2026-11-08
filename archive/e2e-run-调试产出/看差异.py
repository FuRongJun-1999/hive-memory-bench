# -*- coding: utf-8 -*-
import json, difflib
from pathlib import Path
R = Path(r'D:/1_ai/_hb_lab/r58')
d = {x['id']: x for x in json.loads((R/'questions/题目_选择题_182.json').read_text(encoding='utf-8'))['questions']}
for qid, a, b in (('o012i','B','D'), ('o011i','A','D'), ('o013i','B','D')):
    x = d[qid]
    ta, tb = x['options'][a], x['options'][b]
    sm = difflib.SequenceMatcher(None, ta, tb)
    print('=' * 72)
    print('%s  %s(答案=%s) vs %s | 相似度 %.3f | 长度 %d vs %d' % (qid, a, x['answer'], b, sm.ratio(), len(ta), len(tb)))
    print('问:', x['question'][:90])
    print()
    # 只在差异处输出
    ops = [op for op in sm.get_opcodes() if op[0] != 'equal']
    for tag, i1, i2, j1, j2 in ops[:6]:
        print('  [%s]' % tag)
        print('    %s: ...%s...' % (a, ta[max(0,i1-25):i2+25]))
        print('    %s: ...%s...' % (b, tb[max(0,j1-25):j2+25]))
    print()