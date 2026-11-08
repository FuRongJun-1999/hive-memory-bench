# -*- coding: utf-8 -*-
import json
from pathlib import Path
R = Path(r'D:/1_ai/_hb_lab/r58')
d = json.loads((R / 'e2e/run/lingshu_self_Kv2_detail.json').read_text(encoding='utf-8'))
print('=== 灵枢 K_v2 逐维原始分数（本次自答）===')
print('%-16s %6s %8s %6s %6s %4s %4s %4s %s' % ('维度','正说','反说反计','二轮','换问法','T1','T2','T3','有效'))
print('-'*78)
for x in d['rows']:
    print('%-16s %6.2f %8.2f %6.2f %6.2f %4s %4s %4s %s' % (
        x['dim'], x['p1'], x['n1_rev'], x['p2'], x['pa'],
        'OK' if x['T1'] else 'X', 'OK' if x['T2'] else 'X', 'OK' if x['T3'] else 'X',
        '有效' if x['valid'] else '作废'))
print()
print('汇总:', '三级全过 %d/%d | 有效通过 %d/%d | 通过率 %s%%' % (
    d['all_pass'], d['dims'], d['valid_pass'], d['valid_dims'], d['pass_rate']))
print()
print('=== 与 PR #62 的对照 ===')
pr62 = json.loads((R / 'persona-consistency/results/K_v2_readings.json').read_text(encoding='utf-8'))
for r in pr62['readings']:
    if 'lingshu' in r['system']:
        print('  PR#62 读数  %-28s %d/%d 有效%d  %.1f%%' % (r['system'], r['all_pass'], r['dims'], r['valid_dims'], r['pass_rate']))
print('  本次自答    %-28s %d/%d 有效%d  %.1f%%' % ('lingshu(当前会话自答)', d['all_pass'], d['dims'], d['valid_dims'], d['pass_rate']))
print('  差异        +%.1f pp' % (d['pass_rate'] - [r for r in pr62['readings'] if 'lingshu' in r['system']][0]['pass_rate']))