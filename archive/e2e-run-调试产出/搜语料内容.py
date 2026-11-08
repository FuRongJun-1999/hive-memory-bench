# -*- coding: utf-8 -*-
from pathlib import Path
R = Path(r'D:/1_ai/_hb_lab/r58')
MARK = {
  '秦吏': ['派出所', '警官学院', '里正、亭长', '南郡太守腾', '公士', '上造', '五户一伍'],
  '毛选': ['小资产阶级', '陈独秀', '张国焘', '都市苦力工人', '工人运动', '地主阶级'],
  '蜂巢': ['陈默', '信用点', '蜂巢世界'],
}
exts = {'.md', '.json', '.txt', '.jsonl'}
targets = []
for f in R.rglob('*'):
    if not f.is_file() or f.suffix.lower() not in exts: continue
    if '.git' in f.parts: continue
    try: sz = f.stat().st_size
    except Exception: continue
    if sz >= 10000: targets.append(f)
print('扫描', len(targets), '个文件')
print()
res = {k: [] for k in MARK}
for f in targets:
    try:
        t = f.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        continue
    for name, kws in MARK.items():
        hits = sum(1 for k in kws if k in t)
        if hits >= 2:
            res[name].append((hits, str(f.relative_to(R)), len(t)))
for name, lst in res.items():
    print('=== %s ===' % name)
    if not lst:
        print('  未找到'); continue
    for hits, p, sz in sorted(lst, reverse=True)[:6]:
        print('  特征命中%d/6  %-50s %d 字符' % (hits, p, sz))
    print()