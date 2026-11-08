# -*- coding: utf-8 -*-
import json
from pathlib import Path
from collections import Counter, defaultdict
R = Path(r"D:/1_ai/_hb_lab/r58")
Q = R / "e2e" / "questions"

print("=== 各面计数分级的实际落盘情况 ===")
stat = defaultdict(lambda: Counter())
for p in sorted(Q.glob("题目_*.json")):
    if "残缺诊断" in p.name:
        continue
    for q in json.loads(p.read_text(encoding="utf-8")):
        f = q.get("face")
        if not f:
            continue
        stat[f]["总"] += 1
        if q.get("v2_pass") is False:
            stat[f]["排除"] += 1
            continue
        stat[f][q.get("count_tier", "未标")] += 1

for f in sorted(stat):
    s = stat[f]
    print(f"  {f:3s} 总{s['总']:3d} | 排除{s['排除']:2d} | counted {s['counted']:3d} | conditional {s['conditional']:3d} | excluded {s['excluded']:3d} | 未标 {s['未标']:3d}")

# 空缺面是否有标记
print()
print("=== 空缺面是否有机器可读标记 ===")
cov = R / "e2e" / "questions" / "题目_覆盖声明.json"
print("  覆盖声明文件存在:", cov.exists())

# 判据版本一致性
print()
print("=== 判据版本一致性 ===")
vers = Counter()
for p in Q.glob("题目_*.json"):
    if "残缺诊断" in p.name:
        continue
    for q in json.loads(p.read_text(encoding="utf-8")):
        vers[q.get("judge_version")] += 1
print("  ", dict(vers))
j = R / "e2e" / "tools" / "judge.py"
print("  judge.py 存在:", j.exists(), "| 大小:", j.stat().st_size if j.exists() else 0)