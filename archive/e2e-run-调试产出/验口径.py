# -*- coding: utf-8 -*-
import re
from pathlib import Path
NEW = Path(r'D:/1_ai/_hb_lab/r58/e2e/run/pr64_v2')
print('=== 口径检查（README + 设计说明 + 契约）===')
files = {'README.md': NEW/'README.md', '设计说明': NEW/'选择题题库_设计说明_v1.0.md', '契约': NEW/'作答契约_选择题.md'}
checks = [
    ('判分环节零噪声', ['判分环节零噪声', '判分环节零噪声'], '要求限定「判分环节」'),
    ('25% 基线', ['25%', '25 %', '0.25'], '要求报随机基线'),
    ('二项检验', ['二项检验', 'binomial', '二项'], '要求给检验方法'),
    ('fact 改写', ['改写概括', '改写', '概括'], '要求改 fact 口径'),
    ('不能逐字定位', ['不能逐字', '不可逐字', '无法逐字', '不用于逐字'], '要求明确否定逐字'),
]
for name, p in files.items():
    if not p.exists():
        print(' %s 缺失' % name); continue
    t = p.read_text(encoding='utf-8')
    print(' --- %s (%d 字符) ---' % (name, len(t)))
    for label, kws, why in checks:
        hit = [k for k in kws if k in t]
        mark = '✅' if hit else '  '
        print('    %s %-14s %s' % (mark, label, hit[:2] if hit else '（未出现）'))

print()
print('=== 旧断言是否已删 ===')
for name, p in files.items():
    if not p.exists(): continue
    t = p.read_text(encoding='utf-8')
    for bad in ('位置偏差已排除', '已排除位置偏差', '无位置偏差'):
        if bad in t:
            print('  %s 仍含「%s」' % (name, bad))
print('  （无输出=已删）')

print()
print('=== 契约里的题数 ===')
c = (NEW/'作答契约_选择题.md').read_text(encoding='utf-8')
for m in re.findall(r'\d+\s*题', c):
    print('  出现:', m)
if '118' in c:
    print('  ❌ 仍有 118')
else:
    print('  ✅ 无 118 笔误')

print()
print('=== 契约全文 ===')
print(c[:1400])