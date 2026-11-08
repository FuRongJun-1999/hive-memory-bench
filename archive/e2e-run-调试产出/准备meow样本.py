# -*- coding: utf-8 -*-
import json
from pathlib import Path
R = Path(r'D:/1_ai/_hb_lab/r58')
corp = json.loads((R / 'chain/corpus/corpus.json').read_text(encoding='utf-8'))
keys = json.loads((R / 'chain/keys/keys.json').read_text(encoding='utf-8'))

hu = [s for s in corp if s['doc'] == '猎户项目']
print('猎户项目语料段:', len(hu))
tot = sum(len(s['text']) for s in hu)
print('总字符:', tot)
print('seq 范围:', min(s['seq'] for s in hu), '-', max(s['seq'] for s in hu))
print()
hq = [q for q in keys if q['doc'] == '猎户项目']
print('猎户项目题:', len(hq))
from collections import Counter
print('问型:', dict(Counter(q['type'] for q in hq)))
print()
# 只取现值+历史
sel = [q for q in hq if q['type'] in ('现值','历史')]
print('选中（现值+历史）:', len(sel))
for q in sel[:3]:
    print(' ', q['qid'], '|', q['type'], '|', q['question'][:80])
    print('    答案:', json.dumps(q['answer'], ensure_ascii=False)[:160])
print()
# 导出准备
out = R / 'e2e/run/meow_probe'
out.mkdir(parents=True, exist_ok=True)
(out / 'hu_corpus.json').write_text(json.dumps(hu, ensure_ascii=False, indent=1), encoding='utf-8')
(out / 'hu_questions.json').write_text(json.dumps(sel, ensure_ascii=False, indent=1), encoding='utf-8')
print('已导出到', out)