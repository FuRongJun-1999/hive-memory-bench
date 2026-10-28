# -*- coding: utf-8 -*-
import json, statistics
from pathlib import Path
from collections import defaultdict, Counter
R = Path(r"D:/1_ai/_hb_lab/r58")
cards = {q["qid"]: q for q in json.loads((R / "e2e/questions/题目_一致性探针.json").read_text(encoding="utf-8"))}
j = json.loads((R / "e2e/run/K108作答.json").read_text(encoding="utf-8"))
r1 = {x["qid"]: x["score"] for x in j["round1"]}
r2 = {x["qid"]: x["score"] for x in j["round2"]}
r3 = {x["qid"]: x["score"] for x in j["round3"]}

g = defaultdict(lambda: {"p1": [], "n1": [], "p2": [], "n2": [], "pa": []})
for qid, q in cards.items():
    d, pol = q["subface"], q["polarity"]
    if pol == "正向":
        if qid in r1: g[d]["p1"].append(r1[qid])
        if qid in r2: g[d]["p2"].append(r2[qid])
    elif pol == "反向":
        if qid in r1: g[d]["n1"].append(r1[qid])
        if qid in r2: g[d]["n2"].append(r2[qid])
    else:
        if qid in r3: g[d]["pa"].append(r3[qid])

print("=" * 100)
print("一致性探针 108 题 · 12 维三级信度")
print("=" * 100)
h = "%-14s %5s %5s %6s %5s %3s   %5s %5s %3s   %5s %5s %3s"
print(h % ("维度", "正", "反", "反计分", "T1差", "T1", "前正", "后正", "T2", "后正", "换问", "T3"))
print("-" * 100)
t1n = t2n = t3n = alln = 0
rows = []
for d in sorted(g):
    v = g[d]
    if not (v["p1"] and v["n1"] and v["p2"] and v["pa"]):
        print("%-14s 数据不全" % d); continue
    p1 = statistics.mean(v["p1"]); n1 = statistics.mean(v["n1"]); nrev = 6 - n1
    p2 = statistics.mean(v["p2"]); pa = statistics.mean(v["pa"])
    d1 = abs(p1 - nrev); t1 = d1 <= 1
    d2 = abs(p1 - p2); t2 = d2 <= 1
    d3 = abs(p2 - pa); t3 = d3 <= 1
    t1n += t1; t2n += t2; t3n += t3; alln += (t1 and t2 and t3)
    print(h % (d, "%.1f" % p1, "%.1f" % n1, "%.1f" % nrev, "%.1f" % d1, "OK" if t1 else "X",
               "%.1f" % p1, "%.1f" % p2, "OK" if t2 else "X",
               "%.1f" % p2, "%.1f" % pa, "OK" if t3 else "X"))
    rows.append((d, t1, t2, t3))

n = len(rows)
print("-" * 100)
print("T1 正反向一致  : %d/%d  (%.0f%%)" % (t1n, n, t1n / n * 100))
print("T2 注入前后一致: %d/%d  (%.0f%%)" % (t2n, n, t2n / n * 100))
print("T3 换问法一致  : %d/%d  (%.0f%%)" % (t3n, n, t3n / n * 100))
print("三级全过      : %d/%d  (%.0f%%)" % (alln, n, alln / n * 100))
print()
fails = [(d, [x for x, ok in zip(("T1","T2","T3"), (a,b,c)) if not ok]) for d, a, b, c in rows if not (a and b and c)]
print("未全过的维度:", fails if fails else "无")
print()
allsc = [x for v in g.values() for k in ("p1","n1","p2","pa") for x in v[k]]
print("分数: 均值 %.2f | 标准差 %.2f | 取值 %s" % (
    statistics.mean(allsc), statistics.pstdev(allsc), dict(sorted(Counter(allsc).items()))))