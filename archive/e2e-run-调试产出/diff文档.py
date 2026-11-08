# -*- coding: utf-8 -*-
from pathlib import Path
OLD = Path(r'D:/1_ai/_hb_lab/r58/e2e/run/pr64')
NEW = Path(r'D:/1_ai/_hb_lab/r58/e2e/run/pr64_v2')
print('=== 「位置偏差已排除」出现情况 ===')
for name in ('选择题题库_设计说明_v1.0.md',):
    for tag, base in (('旧', OLD), ('新', NEW)):
        p = base/name
        if not p.exists():
            print('  %s %s 不存在' % (tag, name)); continue
        t = p.read_text(encoding='utf-8')
        print('  %s %s: 「位置偏差已排除」%s' % (tag, name, '有' if '位置偏差已排除' in t else '无'))
print()
print('=== 设计说明 diff（旧->新）===')
a = (OLD/'选择题题库_设计说明_v1.0.md').read_text(encoding='utf-8')
b = (NEW/'选择题题库_设计说明_v1.0.md').read_text(encoding='utf-8')
print('旧 %d 字符 -> 新 %d 字符' % (len(a), len(b)))
# 逐行找新增
al = set(a.split(chr(10)))
bl = set(b.split(chr(10)))
add = [l for l in bl - al if l.strip()]
rem = [l for l in al - bl if l.strip()]
print()
print('新增 %d 行:' % len(add))
for l in add[:25]:
    print('  + %s' % l[:120])
print()
print('删除 %d 行:' % len(rem))
for l in rem[:15]:
    print('  - %s' % l[:120])