import subprocess, sys, json
from pathlib import Path
R = Path(r'D:/1_ai/_hb_lab/r58')
p = subprocess.run([sys.executable,'-X','utf8', str(R/'persona-consistency/tools/score_k.py'),
  '--bank', str(R/'persona-consistency/questions/K_persona_consistency_v2.json'),
  '--scores', str(R/'e2e/run/hive_pushback_scores.json'),
  '--json', str(R/'e2e/run/hive_pushback_detail.json')], capture_output=True, text=True, encoding='utf-8')
print(p.stdout)
# 对比无诱导版
a = json.loads((R/'e2e/run/hive_Kv2_detail.json').read_text(encoding='utf-8'))
b = json.loads((R/'e2e/run/hive_pushback_detail.json').read_text(encoding='utf-8'))
print('=== 无诱导 vs 有反向诱导 ===')
print('  无诱导      : 三级全过 %d/%d | 有效 %d/%d | %.1f%%' % (a['all_pass'],a['dims'],a['valid_pass'],a['valid_dims'],a['pass_rate']))
print('  有反向诱导  : 三级全过 %d/%d | 有效 %d/%d | %.1f%%' % (b['all_pass'],b['dims'],b['valid_pass'],b['valid_dims'],b['pass_rate']))
print()
print('=== 逐维 T2（诱导前后）差 ===')
am = {x['dim']: x for x in a['rows']}
print('%-16s %8s %8s %8s' % ('维度','无诱导T2','有诱导T2','变化'))
for x in b['rows']:
    o = am.get(x['dim'], {})
    print('%-16s %8.2f %8.2f %+8.2f %s' % (x['dim'], o.get('d2',0), x['d2'], x['d2']-o.get('d2',0), '' if x['T2'] else '← T2失守'))