# -*- coding: utf-8 -*-
import subprocess, json
def show(ref, path):
    p = subprocess.run(['git','-C',r'D:/1_ai/_hb_lab/r58','show','%s:%s' % (ref, path)],
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    return p.stdout if p.returncode == 0 else None

# roleplay 侧
rd = show('origin/feat/roleplay-track', 'roleplay/questions/D_人设_v1.json')
rk = show('origin/feat/roleplay-track', 'roleplay/questions/K_一致性_v1.json')
# persona-consistency 侧
pd = show('origin/main', 'persona-consistency/questions/D_persona_features.json')
pk = show('origin/main', 'persona-consistency/questions/K_persona_consistency.json')

for label, a, b in (('D 面', rd, pd), ('K_v1', rk, pk)):
    print('=' * 60)
    print(label)
    if a is None or b is None:
        print('  读取失败 roleplay=%s persona=%s' % (a is not None, b is not None))
        continue
    ja, jb = json.loads(a), json.loads(b)
    print('  roleplay 题数:', len(ja), '| persona 题数:', len(jb))
    # 逐题 compare：题面
    qa = [q.get('question') or q.get('item') or '' for q in ja]
    qb = [q.get('question') or q.get('item') or '' for q in jb]
    same = sum(1 for x in qa if x in qb)
    print('  题面完全相同条数:', same, '/', len(qa))
    # 字段对比
    print('  roleplay 字段:', sorted(ja[0].keys())[:10])
    print('  persona  字段:', sorted(jb[0].keys())[:10])
    print('  首题 roleplay:', (qa[0] or '')[:70])
    print('  首题 persona :', (qb[0] or '')[:70])