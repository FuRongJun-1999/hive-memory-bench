# -*- coding: utf-8 -*-
import json
from pathlib import Path
from collections import defaultdict, Counter
Q = Path(r"D:/1_ai/_hb_lab/r58/e2e/questions")

stat = defaultdict(lambda: {"可用": 0, "counted": 0, "cond": 0, "excl": 0, "clusters": set()})
for p in Q.glob("题目_*.json"):
    if "残缺诊断" in p.name:
        continue
    for q in json.loads(p.read_text(encoding="utf-8")):
        f = q.get("face")
        if not f or q.get("v2_pass") is False:
            continue
        s = stat[f]
        s["可用"] += 1
        tier = q.get("count_tier", "counted")
        if tier == "counted":
            s["counted"] += 1
        elif tier == "conditional":
            s["cond"] += 1
        else:
            s["excl"] += 1
        c = q.get("independence_cluster")
        if c:
            s["clusters"].add(c)

print(f"{'面':4s} {'可用':>4s} {'counted':>8s} {'cond':>5s} {'excl':>5s} {'独立簇':>7s}")
tot = Counter()
for f in sorted(stat):
    s = stat[f]
    cl = len(s["clusters"]) if s["clusters"] else "-"
    print(f"{f:4s} {s['可用']:4d} {s['counted']:8d} {s['cond']:5d} {s['excl']:5d} {str(cl):>7s}")
    for k in ("可用", "counted", "cond", "excl"):
        tot[k] += s[k]
    if s["clusters"]:
        tot["clusters"] += len(s["clusters"])
print(f"{'合计':4s} {tot['可用']:4d} {tot['counted']:8d} {tot['cond']:5d} {tot['excl']:5d} {tot['clusters']:7d}")