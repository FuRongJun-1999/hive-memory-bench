# -*- coding: utf-8 -*-
import json, re, statistics
from pathlib import Path
from collections import defaultdict
R = Path(r"D:/1_ai/_hb_lab/r58")
cards = json.loads((R / "e2e/questions/题目_一致性探针.json").read_text(encoding="utf-8"))
cards.sort(key=lambda q: q["qid"])
L12 = [q for q in cards if q["stage"] == "T1/T2"]
L3 = [q for q in cards if q["stage"] == "T3"]

ans = (R / "e2e/run/meow_K_answer.txt").read_text(encoding="utf-8")
m = re.search(r"\{[\s\S]*\}", ans)
if not m:
    print("未找到 JSON"); raise SystemExit
j = json.loads(m.group(0))
print("解析成功 | r1", len(j["round1"]), "r2", len(j["round2"]), "r3", len(j["round3"]))
print()
print("=== 注入回应 ===")
for k, v in j.get("injection_replies", {}).items():
    print(" ", k, ":", v[:80])

r1 = {q["qid"]: j["round1"][i] for i, q in enumerate(L12)}
r2 = {q["qid"]: j["round2"][i] for i, q in enumerate(L12)}
r3 = {q["qid"]: j["round3"][i] for i, q in enumerate(L3)}
g = defaultdict(lambda: {"p1": [], "n1": [], "p2": [], "pa": []})
for q in L12:
    d = q["subface"]
    if q["polarity"] == "正向":
        g[d]["p1"].append(r1[q["qid"]]); g[d]["p2"].append(r2[q["qid"]])
    else:
        g[d]["n1"].append(r1[q["qid"]])
for q in L3:
    g[q["subface"]]["pa"].append(r3[q["qid"]])

TOL = 1.0 + 1e-9
print()
print("=" * 84)
print("meow-memory v0.31.0 · 面 K 108 题（智谱 glm-5.3-flash）")
print("=" * 84)
h = "%-16s %5s %5s %6s %5s %3s  %4s %4s %6s %s"
print(h % ("维度", "正", "反", "反计分", "T1差", "T1", "T2", "T3", "方差", "有效性"))
print("-" * 84)
nall = 0; nvalid = 0; nvp = 0
for d in sorted(g):
    v = g[d]
    p1 = statistics.mean(v["p1"]); nn = statistics.mean(v["n1"]); nrev = 6 - nn
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
        nvp += passed
    print(h % (d, "%.2f" % p1, "%.2f" % nn, "%.2f" % nrev, "%.2f" % d1,
               "OK" if ok1 else "X", "OK" if ok2 else "X", "OK" if ok3 else "X",
               "%.2f" % var, "作废" if flat else "有效"))
n = len(g)
print("-" * 84)
print("三级全过        : %d/%d" % (nall, n))
print("扣掉作废维度后  : **%d/%d 有效维度全过**" % (nvp, nvalid))

# 与裸模型对照
import os
K108b = R / "e2e/run/K108b作答.json"
if K108b.exists():
    jb = json.loads(K108b.read_text(encoding="utf-8"))
    b1 = {q["qid"]: jb["round1"][i] for i, q in enumerate(L12)}
    b2 = {q["qid"]: jb["round2"][i] for i, q in enumerate(L12)}
    b3 = {q["qid"]: jb["round3"][i] for i, q in enumerate(L3)}
    gb = defaultdict(lambda: {"p1": [], "n1": [], "p2": [], "pa": []})
    for q in L12:
        d = q["subface"]
        if q["polarity"] == "正向":
            gb[d]["p1"].append(b1[q["qid"]]); gb[d]["p2"].append(b2[q["qid"]])
        else:
            gb[d]["n1"].append(b1[q["qid"]])
    for q in L3:
        gb[q["subface"]]["pa"].append(b3[q["qid"]])
    ba = 0; bv = 0; bvp = 0
    for d in gb:
        v = gb[d]
        p1 = statistics.mean(v["p1"]); nn = statistics.mean(v["n1"]); p2 = statistics.mean(v["p2"]); pa = statistics.mean(v["pa"])
        ok = abs(p1-(6-nn)) <= TOL and abs(p1-p2) <= TOL and abs(p2-pa) <= TOL
        ba += ok
        if len(set(v["p1"])) > 1:
            bv += 1; bvp += ok
    print()
    print("=" * 84)
    print("对照（同一判据、同一 108 题）")
    print("=" * 84)
    print("  meow-memory（有记忆插件）: 全过 %d/%d | 有效 %d/%d 全过" % (nall, n, nvp, nvalid))
    print("  裸模型（无插件）        : 全过 %d/%d | 有效 %d/%d 全过" % (ba, len(gb), bvp, bv))