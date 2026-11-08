# -*- coding: utf-8 -*-
import json, re
from pathlib import Path
R = Path(r'D:/1_ai/_hb_lab/r58')
OUT = R / 'e2e/run/meow_probe'
qs = {q['qid']: q for q in json.loads((OUT / 'hu_questions.json').read_text(encoding='utf-8'))}
rows = [json.loads(l) for l in (OUT / 'results.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]

def extract(ans):
    m = re.search(r'值=([^；;\n]+)', ans)
    val = m.group(1).strip() if m else ''
    m2 = re.search(r'序号=([0-9]+)', ans)
    seq = int(m2.group(1)) if m2 else None
    st = 'active' if ('active' in ans or '生效' in ans or '现行' in ans) else ('retired' if ('retired' in ans or '退役' in ans) else ('absent' if '不存在' in ans else '?'))
    return val, seq, st

print('=' * 96)
print('meow-memory · 猎户项目 · 召回率逐题核对')
print('=' * 96)
pres_n = pres_ok = hist_n = hist_ok = 0
stale_n = 0
for r in rows:
    q = qs.get(r['qid'])
    if not q: continue
    truth = q['answer']
    tv = str(truth.get('value', ''))
    ts = truth.get('at_seq')
    val, seq, st = extract(r['answer'])
    # 值命中：去空白后包含或被包含
    nv = re.sub(r'\s', '', val)
    ntv = re.sub(r'\s', '', tv)
    hit = bool(nv) and (ntv in nv or nv in ntv) and len(nv) >= 2
    ok = hit and (seq == ts)
    typ = r['type']
    if typ == '现值':
        pres_n += 1; pres_ok += hit
    else:
        hist_n += 1; hist_ok += hit
    mark = 'OK ' if ok else 'X  '
    print('%s %-22s %-4s' % (mark, r['qid'], typ))
    print('     答: 值=%s | 序号=%s' % (val[:40], seq))
    print('     真: 值=%s | 序号=%s' % (tv[:40], ts))
    if typ == '现值' and not hit and '未记录' not in val:
        stale_n += 1
        print('     -> 现值答错（用了错误版本/别的值）')
    if '未记录' in val or '查无' in r['answer']:
        print('     -> 拒答（声称记忆库无此记录）')
print()
print('-' * 96)
print('现值正确率  : %d/%d = %.0f%%' % (pres_ok, pres_n, pres_ok/pres_n*100 if pres_n else 0))
print('历史召回率  : %d/%d = %.0f%%' % (hist_ok, hist_n, hist_ok/hist_n*100 if hist_n else 0))
print('滞后/错版率 : %d/%d' % (stale_n, pres_n))