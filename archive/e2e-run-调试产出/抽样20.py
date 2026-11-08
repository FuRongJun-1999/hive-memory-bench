import json
from pathlib import Path
R = Path(r'D:/1_ai/_hb_lab/r58')
d = json.loads((R/'e2e/run/pr64/题目_选择题_150.json').read_text(encoding='utf-8'))
# 每个 material 抽 5 题（按 qid 排序取前 5）
out = []
for m in ('秦吏','毛选','蜂巢指南','对话'):
    sub = sorted([x for x in d if x['material']==m], key=lambda x: x['qid'])[:5]
    out += sub
lines = []
for x in out:
    lines.append('[%s] 材料=%s' % (x['qid'], x['material']))
    lines.append('  问：%s' % x['question'])
    for k in 'ABCD':
        mark = ' ★' if k == x['answer'] else ''
        lines.append('   %s. %s%s' % (k, x['options'][k], mark))
    lines.append('  依据(fact)：%s' % x['fact'])
    lines.append('')
Path(r'D:/1_ai/_hb_lab/r58/e2e/run/pr64/抽样20题.txt').write_text(chr(10).join(lines), encoding='utf-8')
print('抽样', len(out), '题 |', len(chr(10).join(lines)), '字符')
print()
print(chr(10).join(lines)[:1500])