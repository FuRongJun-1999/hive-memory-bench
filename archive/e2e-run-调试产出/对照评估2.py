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

def load(fn):
    j = json.loads((R / "e2e/run" / fn).read_text(encoding="utf-8"))
    def norm(arr, order):
        if arr and isinstance(arr[0], dict):
            return {x["qid"]: x["score"] for x in arr}
        return {q["qid"]: arr[i] for i, q in enumerate(order)}
    return norm(j["round1"], L12), norm(j["round2"], L12), norm(j["round3"], L3)

def evaluate(fn, label):
    r1, r2, r3 = load(fn)
    g = defaultdict(lambda: {"p1": [], "n1": [], "p2": [], "pa": []})
    for q in L12:
        if q["polarity"] == "正向":
            g[q["subface"]]["p1"].append(r1[q["qid"]]); g[q["subface"]]["p2"].append(r2[q["qid"]])
        else:
            g[q["subface"]]["n1"].append(r1[q["qid"]])
    for q in L3:
        g[q["subface"]]["pa"].append(r3[q["qid"]])
    print("=" * 82)
    print(label)
    print("=" * 82)
    h = "%-15s %5s %5s %6s %5s %3s  %4s %4s %6s %s"
    print(h % ("维度", "正", "反", "反计分", "T1差", "T1", "T2", "T3", "方差", "有效性"))
    print("-" * 82)
    nall = nvalid = nvalid_pass = 0
    rows = []
    for d in sorted(g):
        v = g[d]
        p1 = statistics.mean(v["p1"]); nn1 = statistics.mean(v["n1"]); nrev = 6 - nn1
        p2 = statistics.mean(v["p2"]); pa = statistics.mean(v["pa"])
        var = statistics.pstdev(v["p1"])
        flat = len(set(v["p1"])) == 1
        d1 = abs(p1 - nrev); ok1 = d1 <= TOL
        d2 = abs(p1 - p2); ok2 = d2 <= TOL
        d3 = abs(p2 - pa); ok3 = d3 <= TOL
        passed = ok1 and ok2 and ok3
        nall += passed
        if not flat:
            nvalid += 1
            if passed:
                nvalid_pass += 1
        print(h % (d, "%.2f" % p1, "%.2f" % nn1, "%.2f" % nrev, "%.2f" % d1,
                   "OK" if ok1 else "X", "OK" if ok2 else "X", "OK" if ok3 else "X",
                   "%.2f" % var, "作废(恒定)" if flat else "有效"))
        rows.append((d, passed, flat))
    n = len(rows)
    print("-" * 82)
    print("三级全过        : %d/%d" % (nall, n))
    print("扣掉作废维度后  : **%d/%d 有效维度全过**" % (nvalid_pass, nvalid))
    print()
    return nall, n, nvalid, nvalid_pass

a = evaluate("K_lingshu_作答.json", "实验组 · 灵枢（带 dsh-memory 插件，当前会话）")
b = evaluate("K108b作答.json", "对照组 · 蜂巢子代理（裸模型，无插件）")
print("=" * 82)
print("对照（扣除「分数恒定」的作废维度）")
print("=" * 82)
print("  灵枢    : 全过 %d/%d | 有效维度 %d/%d 全过" % (a[0], a[1], a[3], a[2]))
print("  裸模型  : 全过 %d/%d | 有效维度 %d/%d 全过" % (b[0], b[1], b[3], b[2]))