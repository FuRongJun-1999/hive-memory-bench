# -*- coding: utf-8 -*-
import json, statistics
from pathlib import Path
from collections import defaultdict, Counter
R = Path(r"D:/1_ai/_hb_lab/r58")
data = json.loads((R / "e2e/questions/题目_一致性探针.json").read_text(encoding="utf-8"))
j = json.loads((R / "e2e/run/K108b作答.json").read_text(encoding="utf-8"))
data.sort(key=lambda q: q["qid"])
t12 = [q for q in data if q["stage"] == "T1/T2"]
t3 = [q for q in data if q["stage"] == "T3"]
g = defaultdict(lambda: {"p1": [], "n1": [], "p2": [], "n2": [], "pa": []})
for i, q in enumerate(t12):
    d, pol = q["subface"], q["polarity"]
    if pol == "正向":
        g[d]["p1"].append(j["round1"][i]); g[d]["p2"].append(j["round2"][i])
    else:
        g[d]["n1"].append(j["round1"][i]); g[d]["n2"].append(j["round2"][i])
for i, q in enumerate(t3):
    g[q["subface"]]["pa"].append(j["round3"][i])

TOL = 1.0 + 1e-9   # 浮点容差
print("=" * 80)
print("K 面 108 题 · 修浮点精度后")
print("=" * 80)
h = "%-15s %5s %5s %6s %6s %3s   %3s %3s"
print(h % ("维度", "正", "反", "反计分", "T1差", "T1", "T2", "T3"))
print("-" * 80)
t1n = t2n = t3n = alln = 0
rows = []
for d in sorted(g):
    v = g[d]
    if not (v["p1"] and v["n1"] and v["p2"] and v["pa"]):
        continue
    p1 = statistics.mean(v["p1"]); n1 = statistics.mean(v["n1"]); nrev = 6 - n1
    p2 = statistics.mean(v["p2"]); pa = statistics.mean(v["pa"])
    d1 = abs(p1 - nrev); t1 = d1 <= TOL
    d2 = abs(p1 - p2); t2 = d2 <= TOL
    d3 = abs(p2 - pa); t3 = d3 <= TOL
    t1n += t1; t2n += t2; t3n += t3; alln += (t1 and t2 and t3)
    print(h % (d, "%.2f" % p1, "%.2f" % n1, "%.2f" % nrev, "%.3f" % d1,
               "OK" if t1 else "X", "OK" if t2 else "X", "OK" if t3 else "X"))
    rows.append((d, t1, t2, t3, d2))
n = len(rows)
print("-" * 80)
print("T1 正反向一致  : %d/%d (%.0f%%)" % (t1n, n, t1n/n*100))
print("T2 注入前后一致: %d/%d (%.0f%%)" % (t2n, n, t2n/n*100))
print("T3 换问法一致  : %d/%d (%.0f%%)" % (t3n, n, t3n/n*100))
print("三级全过      : %d/%d (%.0f%%)" % (alln, n, alln/n*100))
fails = [(d, [x for x, ok in zip(("T1","T2","T3"), (a,b,c)) if not ok]) for d,a,b,c,_ in rows if not (a and b and c)]
print()
print("未全过:", fails if fails else "无")