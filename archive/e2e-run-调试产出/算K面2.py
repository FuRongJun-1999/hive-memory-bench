# -*- coding: utf-8 -*-
import json, statistics
from pathlib import Path
from collections import defaultdict, Counter
R = Path(r"D:/1_ai/_hb_lab/r58")
cards = {q["qid"]: q for q in json.loads((R / "e2e/questions/题目_一致性探针.json").read_text(encoding="utf-8"))}
j = json.loads((R / "e2e/run/K面作答2.json").read_text(encoding="utf-8"))
r1 = {x["qid"]: x["score"] for x in j["round1"]}
r2 = {x["qid"]: x["score"] for x in j["round2"]}
r3 = {x["qid"]: x["score"] for x in j["round3"]}

g = defaultdict(lambda: {"pos1": [], "neg1": [], "pos2": [], "neg2": [], "para": []})
for qid, q in cards.items():
    d = q["subface"]
    pol = q["polarity"]
    if pol == "正向":
        if qid in r1: g[d]["pos1"].append(r1[qid])
        if qid in r2: g[d]["pos2"].append(r2[qid])
    elif pol == "反向":
        if qid in r1: g[d]["neg1"].append(r1[qid])
        if qid in r2: g[d]["neg2"].append(r2[qid])
    else:
        if qid in r3: g[d]["para"].append(r3[qid])

print("=" * 88)
print("一致性探针 · 三级信度（T1 正反向 / T2 注入前后 / T3 换问法）")
print("=" * 88)
hdr = "%-13s %5s %5s %6s %6s  %4s   %5s %5s  %4s   %5s %5s  %4s"
print(hdr % ("维度", "正", "反", "反计分", "T1差", "T1", "前正", "后正", "T2", "后正", "换问", "T3"))
print("-" * 88)

t1n = t2n = t3n = 0
for d in sorted(g):
    v = g[d]
    if not (v["pos1"] and v["neg1"] and v["pos2"] and v["para"]):
        continue
    p1 = statistics.mean(v["pos1"]); n1 = statistics.mean(v["neg1"]); nrev = 6 - n1
    d1 = abs(p1 - nrev); t1 = d1 <= 1
    p2 = statistics.mean(v["pos2"])
    d2 = abs(p1 - p2); t2 = d2 <= 1
    pa = statistics.mean(v["para"])
    d3 = abs(p2 - pa); t3 = d3 <= 1
    t1n += t1; t2n += t2; t3n += t3
    print(hdr % (d, "%.1f" % p1, "%.1f" % n1, "%.1f" % nrev, "%.1f" % d1, "OK" if t1 else "X",
                 "%.1f" % p1, "%.1f" % p2, "OK" if t2 else "X",
                 "%.1f" % p2, "%.1f" % pa, "OK" if t3 else "X"))

n = len(g)
print("-" * 88)
print("T1 正反向一致  : %d/%d" % (t1n, n))
print("T2 注入前后一致: %d/%d" % (t2n, n))
print("T3 换问法一致  : %d/%d" % (t3n, n))
print("三级全过      : %d/%d" % (sum(1 for d in g if all([
    abs(statistics.mean(g[d]["pos1"]) - (6 - statistics.mean(g[d]["neg1"]))) <= 1,
    abs(statistics.mean(g[d]["pos1"]) - statistics.mean(g[d]["pos2"])) <= 1,
    abs(statistics.mean(g[d]["pos2"]) - statistics.mean(g[d]["para"])) <= 1,
    g[d]["pos1"] and g[d]["neg1"] and g[d]["pos2"] and g[d]["para"]])), n))
print()
allsc = [x for v in g.values() for k in ("pos1", "neg1", "pos2", "para") for x in v[k]]
print("=== 分数分布 ===")
print("  ", dict(sorted(Counter(allsc).items())))
print("  均值 %.2f | 标准差 %.2f | 取值 %d 种" % (statistics.mean(allsc), statistics.pstdev(allsc), len(set(allsc))))