import json
from pathlib import Path
p = Path(r'D:/1_ai/_hb_lab/r58/questions/题目_选择题_182.json')
d = json.loads(p.read_text(encoding='utf-8'))
print('顶层键:', list(d.keys()))
for k, v in d.items():
    if isinstance(v, list):
        print('  %-16s list[%d]' % (k, len(v)))
    elif isinstance(v, dict):
        print('  %-16s dict keys=%s' % (k, list(v.keys())[:8]))
    else:
        print('  %-16s %s' % (k, str(v)[:100]))
print()
# 找题目数组
q = None
for k, v in d.items():
    if isinstance(v, list) and v and isinstance(v[0], dict) and 'options' in v[0]:
        q = (k, v); break
if q:
    k, arr = q
    print('题目数组在键:', k, '| 题数:', len(arr))
    print('字段:', sorted(arr[0].keys()))
    print()
    print('=== 首题 ===')
    print(json.dumps(arr[0], ensure_ascii=False, indent=1)[:1500])