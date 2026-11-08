# -*- coding: utf-8 -*-
import hashlib, json
from pathlib import Path
R = Path(r'D:/1_ai/_hb_lab/r58')
def h(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16] if p.exists() else None
print('=== 判分器重复验证 ===')
a = R / 'roleplay/judge.py'
b = R / 'persona-consistency/judge.py'
print('roleplay/judge.py      ', h(a))
print('persona-consistency/   ', h(b))
print('相同:', h(a) == h(b))
print()
print('=== score_k vs judge_K ===')
c = R / 'roleplay/score_k.py'
d = R / 'persona-consistency/tools/judge_K.py'
print('score_k.py  ', h(c), c.stat().st_size if c.exists() else 0)
print('judge_K.py  ', h(d), d.stat().st_size if d.exists() else 0)
print()
print('=== 各题库大小对比 ===')
pairs = [
    ('roleplay/questions/D_人设_v1.json', 'persona-consistency/questions/D_persona_features.json'),
    ('roleplay/questions/K_一致性_v1.json', 'persona-consistency/questions/K_persona_consistency.json'),
    ('roleplay/questions/E_价值观_v1.json', 'persona-consistency/questions/E_value_probes.json'),
    ('roleplay/questions/F_安全_v1.json', 'persona-consistency/questions/F_safety_probes.json'),
]
for x, y in pairs:
    pa, pb = R / x, R / y
    ja = json.loads(pa.read_text(encoding='utf-8')) if pa.exists() else []
    jb = json.loads(pb.read_text(encoding='utf-8')) if pb.exists() else []
    qa = [q.get('question') or q.get('item') or '' for q in ja]
    qb = [q.get('question') or q.get('item') or '' for q in jb]
    same = sum(1 for q in qa if q in qb)
    print('  %-32s %3d题  vs  %-30s %3d题  相同 %d' % (x.split('/')[-1], len(ja), y.split('/')[-1], len(jb), same))