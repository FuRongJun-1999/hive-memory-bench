# -*- coding: utf-8 -*-
import json, statistics
from pathlib import Path
R = Path(r"D:/1_ai/_hb_lab/r58")
cards = {q["qid"]: q for q in json.loads((R / "e2e/questions/题目_一致性探针.json").read_text(encoding="utf-8"))}
j = json.loads((R / "e2e/run/K面作答.json").read_text(encoding="utf-8"))
r1 = {x["qid"]: x["score"] for x in j["round1"]}
r2 = {x["qid"]: x["score"] for x in j["round2"]}

from collections import defaultdict
dims = defaultdict(lambda: {"pos": [], "neg": [], "pos2": [], "neg2": []})
for qid, q in cards.items():
    d = q["subface"]
    if q["polarity"] == "正向":
        dims[d]["pos"].append(r1[qid]); dims[d]["pos2"].append(r2[qid])
    else:
        dims[d]["neg"].append(r1[qid]); dims[d]["neg2"].append(r2[qid])

print("=" * 74)
print("一致性探针读数（T1 正反向一致 / T2 注入前后重测一致）")
print("=" * 74)
print("%-12s %6s %6s %8s %8s  %5s %5s %5s" % ("维度", "正向", "反向", "反向计分", "T1差", "T1", "T2", "分差"))

t1_ok = t2_ok = 0
all_scores = []
rows = []
for d in sorted(dims):
    v = dims[d]
    pos = statistics.mean(v["pos"]); neg = statistics.mean(v["neg"])
    neg_rev = 6 - neg
    d1 = abs(pos - neg_rev)
    t1 = d1 <= 1
    pos2 = statistics.mean(v["pos2"])
    d2 = abs(pos - pos2)
    t2 = d2 <= 1
    t1_ok += t1; t2_ok += t2
    all_scores += v["pos"] + v["neg"]
    rows.append((d, pos, neg, neg_rev, d1, t1, t2, d2))
    print("%-12s %6.1f %6.1f %8.1f %8.1f  %5s %5s %5.1f" % (d, pos, neg, neg_rev, d1, "OK" if t1 else "FAIL", "OK" if t2 else "FAIL", d2))

print()
print("T1 正反向一致: %d/6" % t1_ok)
print("T2 重测一致  : %d/6" % t2_ok)
print()
print("=== 分数分布（检查是否「一律给 3 分」）===")
from collections import Counter
c = Counter(all_scores)
print("  ", dict(sorted(c.items())))
print("  均值 %.2f | 标准差 %.2f | 不同取值 %d 种" % (statistics.mean(all_scores), statistics.pstdev(all_scores), len(c)))
if len(c) <= 2:
    print("  ⚠ 取值过少 → 该面读数作废（不表态 ≠ 一致）")
else:
    print("  取值充分，方差正常")