# -*- coding: utf-8 -*-
"""修口径冲突：定义四层计数，落到题级 weight，并统一 README/覆盖声明。"""
import json
from pathlib import Path
from collections import defaultdict, Counter
Q = Path(r"D:/1_ai/_hb_lab/r58/e2e/questions")

# 四层语义（这是唯一口径）
# ability   进能力横比（可回答「谁更强」）
# control   阴性对照（只验证题目不难，不进能力分）
# diagnostic 只能定位、不进分（H 同段落）
# excluded  不计数
# excused   标废
TIER = {
  "B2": ("ability", 1.0),
  "C":  ("ability", 1.0),
  "D":  ("ability", 1.0),
  "E":  ("ability", 1.0),
  "F":  ("ability", 1.0),
  "L1": ("control", 0.0),
  "H":  ("diagnostic", 0.0),   # 3 题同段落，独立样本=1
  "B1": ("excluded", 0.0),
  "J":  ("excluded", 0.0),
}
stat = defaultdict(Counter)
for p in Q.glob("题目_*.json"):
    if "残缺诊断" in p.name:
        continue
    data = json.loads(p.read_text(encoding="utf-8"))
    changed = False
    for q in data:
        f = q.get("face")
        if f not in TIER:
            continue
        stat[f]["总"] += 1
        if q.get("v2_pass") is False:
            stat[f]["excused"] += 1
            q["count_tier2"] = "excused"
            q["weight"] = 0.0
            changed = True
            continue
        tier2, w = TIER[f]
        # H 的 15 道读表题 → excluded
        if f == "H" and q.get("validity") == "read-table-only":
            tier2, w = "excluded", 0.0
        q["count_tier2"] = tier2
        q["weight"] = w
        stat[f][tier2] += 1
        changed = True
    if changed:
        p.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

print("=== 四层计数（唯一口径）===")
print(f"{'面':4s} {'总':>4s} {'excused':>8s} {'ability':>8s} {'control':>8s} {'diagnostic':>11s} {'excluded':>9s}")
tot = Counter()
for f in sorted(stat):
    s = stat[f]
    print(f"{f:4s} {s['总']:4d} {s['excused']:8d} {s['ability']:8d} {s['control']:8d} {s['diagnostic']:11d} {s['excluded']:9d}")
    for k in ("总", "excused", "ability", "control", "diagnostic", "excluded"):
        tot[k] += s[k]
print(f"{'合计':4s} {tot['总']:4d} {tot['excused']:8d} {tot['ability']:8d} {tot['control']:8d} {tot['diagnostic']:11d} {tot['excluded']:9d}")
print()
print(f"**ability（能力横比可用）= {tot['ability']}**")
print(f"  control（阴性对照，不进能力分）= {tot['control']}")
print(f"  diagnostic（H 同段落，只能定位）= {tot['diagnostic']}")
print(f"  excluded = {tot['excluded']}  |  excused = {tot['excused']}")

# 更新覆盖声明
C = Q / "覆盖声明.json"
cov = json.loads(C.read_text(encoding="utf-8"))
cov["counting_semantics"] = {
  "ability": "进能力横比（可回答谁更强）",
  "control": "阴性对照，只验证题目不难，不进能力分",
  "diagnostic": "只能定位、不进分（H 的 3 题同段落，独立样本=1）",
  "excluded": "不计数",
  "excused": "标废（v2_pass=false）",
}
cov["totals"] = {
  "题卡总数": tot["总"], "标废excused": tot["excused"], "可用": tot["总"] - tot["excused"],
  "ability": tot["ability"], "control": tot["control"],
  "diagnostic": tot["diagnostic"], "excluded": tot["excluded"],
}
for f in cov["faces"]:
    s = stat.get(f)
    if s:
        cov["faces"][f]["ability"] = s["ability"]
        cov["faces"][f]["control"] = s["control"]
        cov["faces"][f]["diagnostic"] = s["diagnostic"]
        cov["faces"][f]["excluded"] = s["excluded"]
        cov["faces"][f]["excused"] = s["excused"]
C.write_text(json.dumps(cov, ensure_ascii=False, indent=2), encoding="utf-8")
print()
print("覆盖声明已改为四层，ability =", tot["ability"])