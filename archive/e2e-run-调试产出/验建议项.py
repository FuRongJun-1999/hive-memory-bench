# -*- coding: utf-8 -*-
import json, re, difflib
from pathlib import Path
R = Path(r'D:/1_ai/_hb_lab/r58')
qs = json.loads((R/'questions/题目_选择题_238.json').read_text(encoding='utf-8'))['questions']
d = {x['id']: x for x in qs}
def n(s): return re.sub(r'\s','',s)

print('=== A) o012i 的 B/D 雷同度（上轮 0.777）===')
if 'o012i' in d:
    x = d['o012i']
    sm = difflib.SequenceMatcher(None, x['options']['B'], x['options']['D'])
    print('  相似度: %.3f  (%s)' % (sm.ratio(), '❌ 仍雷同' if sm.ratio() > 0.7 else '✅ 已拉开'))
    print('  B 前 80:', x['options']['B'][:80])
    print('  D 前 80:', x['options']['D'][:80])
else:
    print('  o012i 不存在')
print()
print('=== B) 长短版（上轮 o041 88%、o001 81%）===')
for qid in ('o041','o001'):
    if qid not in d:
        print('  %s 不存在' % qid); continue
    x = d[qid]
    keys = [k for k in 'ABCD' if k in x['options']]
    worst = None
    for i in range(len(keys)):
        for j in range(i+1, len(keys)):
            a, b = n(x['options'][keys[i]]), n(x['options'][keys[j]])
            if min(len(a),len(b)) < 20: continue
            short, lg = (a,b) if len(a)<len(b) else (b,a)
            if lg.startswith(short):
                r = len(short)/len(lg)
                if worst is None or r > worst[2]: worst = (keys[i], keys[j], r)
    if worst:
        print('  %s %s/%s 覆盖 %.0f%%  %s' % (qid, worst[0], worst[1], worst[2]*100, '❌ 仍长短版' if worst[2] > 0.6 else '✅ 已修'))
    else:
        print('  %s ✅ 无长短版' % qid)
print()
print('=== C) 全库长短版扫描（A-D）===')
cnt = 0; bad = []
for x in qs:
    keys = [k for k in 'ABCD' if k in x['options']]
    for i in range(len(keys)):
        for j in range(i+1, len(keys)):
            a, b = n(x['options'][keys[i]]), n(x['options'][keys[j]])
            if min(len(a),len(b)) < 20: continue
            short, lg = (a,b) if len(a)<len(b) else (b,a)
            if lg.startswith(short) and len(short)/len(lg) > 0.6:
                cnt += 1; bad.append((x['id'], keys[i], keys[j], round(len(short)/len(lg)*100)))
print('  长短版嫌疑:', cnt, bad[:8])