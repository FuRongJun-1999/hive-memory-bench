# -*- coding: utf-8 -*-
import json, re, subprocess, sys
from pathlib import Path
R = Path(r'D:/1_ai/_hb_lab/r58')
RUN = R / 'e2e/run'
meta = json.loads((RUN/'xsession_meta.json').read_text(encoding='utf-8'))
def load(tag):
    t = (RUN/('xsession_%s.txt' % tag)).read_text(encoding='utf-8')
    return json.loads(re.search(r'\{[\s\S]*\}', t).group(0))
r1 = load('r1'); r2 = load('r2'); r3 = load('r3')
print('r1:', len(r1['scores']), '| r2:', len(r2['scores']), '| r3:', len(r3['scores']))
print('r2 pushback:', len(r2.get('pushback', [])))

# r2 按打乱顺序给出，还原到原序
order = meta['round2_order']          # 打乱后的 qid 序列
orig  = meta['round1_order']          # 原序 qid
pos = {qid: i for i, qid in enumerate(order)}
r2_scores = r2['scores']
# 对每个原序 qid，找到它在打乱序里的位置，取对应分数
r2_by_qid = {qid: r2_scores[pos[qid]] for qid in orig if pos[qid] < len(r2_scores)}
print('还原后 r2 条数:', len(r2_by_qid))

scores = []
for i, qid in enumerate(orig):
    scores.append({'round':'round1','qid':qid,'score':r1['scores'][i]})
    if qid in r2_by_qid:
        scores.append({'round':'round2','qid':qid,'score':r2_by_qid[qid]})
for i, qid in enumerate(meta['round3_order']):
    scores.append({'round':'round3','qid':qid,'score':r3['scores'][i]})
p = RUN/'xsession_scores.json'
p.write_text(json.dumps(scores, ensure_ascii=False, indent=1), encoding='utf-8')
print('scores:', len(scores))
print()
# 逐题一致率（跨会话 + 打乱）
same = sum(1 for i, qid in enumerate(orig) if r1['scores'][i] == r2_by_qid.get(qid))
print('=== 跨会话 r1 vs r2 逐题相同 ===')
print('  %d/%d = %.0f%%' % (same, len(orig), same/len(orig)*100))
print()
# 判分
pp = subprocess.run([sys.executable,'-X','utf8', str(R/'persona-consistency/tools/score_k.py'),
  '--bank', str(R/'persona-consistency/questions/K_persona_consistency_v2.json'),
  '--scores', str(p), '--json', str(RUN/'xsession_detail.json')], capture_output=True, text=True, encoding='utf-8')
print(pp.stdout)