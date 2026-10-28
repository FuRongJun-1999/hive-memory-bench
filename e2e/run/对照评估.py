# -*- coding: utf-8 -*-
import json, statistics
from pathlib import Path
from collections import defaultdict
R = Path(r"D:/1_ai/_hb_lab/r58")
data = json.loads((R / "e2e/questions/题目_一致性探针.json").read_text(encoding="utf-8"))
data.sort(key=lambda q: q["qid"])
L12 = [q for q in data if q["stage"] == "T1/T2"]
L3 = [q for q in data if q["stage"] == "T3"]
TOL = 1.0 + 1e-9

def evaluate(fn, label):
    j = json.loads((R / "e2e/run" / fn).read_text(encoding="utf-8"))
    r1 = {x["qid"]: x["score"] for x in j["round1"]}
    r2 = {x["qid"]: x["score"] for x in j["round2"]}
    r3 = {x["qid"]: x["score"] for x in j["round3"]}
    g = defaultdict(lambda: {"p1": [], "n1": [], "p2": [], "pa": []})
    for q in L12:
        d, pol = q["subface"], q["polarity"]
        if pol == "正向":
            g[d]["p1"].append(r1[q["qid"]]); g[d]["p2"].append(r2[q["qid"]])
        else:
            g[d]["n1"].append(r1[q["qid"]])
    for q in L3:
        g[q["subface"]]["pa"].append(r3[q["qid"]])
    print("=" * 80)
    print(label)
    print("=" * 80)
    h = "%-15s %5s %5s %6s %6s %3s  %4s %4s %5s"
    print(h % ("维度", "正", "反", "反计分", "T1差", "T1", "T2", "T3", "方差"))
    print("-" * 80)
    n1n = n2n = n3n = nall = 0
    dead = []
    rows = []
    for d in sorted(g):
        v = g[d]
        p1 = statistics.mean(v["p1"]); nn1 = statistics.mean(v["n1"]); nrev = 6 - nn1
        p2 = statistics.mean(v["p2"]); pa = statistics.mean(v["pa"])
        var = statistics.pstdev(v["p1"])
        if len(set(v["p1"])) == 1:
            dead.append(d)
        d1 = abs(p1 - nrev); ok1 = d1 <= TOL
        d2 = abs(p1 - p2); ok2 = d2 <= TOL
        d3 = abs(p2 - pa); ok3 = d3 <= TOL
        n1n += ok1; n2n += ok2; n3n += ok3; nall += (ok1 and ok2 and ok3)
        print(h % (d, "%.2f" % p1, "%.2f" % nn1, "%.2f" % nrev, "%.2f" % d1,
                   "OK" if ok1 else "X", "OK" if ok2 else "X", "OK" if ok3 else "X", "%.2f" % var))
        rows.append((d, ok1, ok2, ok3))
    n = len(rows)
    print("-" * 80)
    print("T1 %d/%d | T2 %d/%d | T3 %d/%d | 三级全过 %d/%d (%.0f%%)" % (n1n, n, n2n, n, n3n, n, nall, n, nall/n*100))
    if dead:
        print("⚠ 分数恒定的维度（应作废）:", dead)
    fails = [(d, [x for x, o in zip(("T1","T2","T3"), (a,b,c)) if not o]) for d,a,b,c in rows if not (a and b and c)]
    print("未全过:", fails if fails else "无")
    print()
    return nall, n

a, n = evaluate("K_lingshu_作答.json", "实验组 · 灵枢（带 dsh-memory 插件）")
b, _ = evaluate("K108b作答.json", "对照组 · 蜂巢子代理（裸模型，无插件）")
print("=" * 80)
print("对照")
print("=" * 80)
print("  灵枢（有插件）  : %d/%d = %.0f%%" % (a, n, a/n*100))
print("  裸模型（无插件）: %d/%d = %.0f%%" % (b, n, b/n*100))
print("  差异            : %+d" % (a - b))