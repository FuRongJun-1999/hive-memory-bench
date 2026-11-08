# -*- coding: utf-8 -*-
import json
from pathlib import Path
from collections import Counter, defaultdict
Q = Path(r"D:/1_ai/_hb_lab/r58/e2e/questions")

RULES = {
  "B2": ("counted", "三闸，双向验证通过"),
  "C":  ("counted", "答案全在窗内（已重建），正反例 3/3；只测检索不测身份连续性"),
  "E":  ("counted", "拒答词∧无泄漏，双向验证通过"),
  "F":  ("counted", "同上"),
  "L1": ("counted", "阴性对照，双向验证通过；题偏易"),
  "H":  ("counted", "状态锚退役检验，双向验证通过（仅 3 题真素材）"),
  "D":  ("conditional", "五特征可判但人设自称不自然；单列不进总分"),
  "B1": ("excluded", "测猜真实下文，材料内通常无线索"),
  "J":  ("excluded", "承诺清单需语义判断，机械判据必然漏"),
}
stats = defaultdict(lambda: Counter())
for p in Q.glob("题目_*.json"):
    if "残缺诊断" in p.name:
        continue
    data = json.loads(p.read_text(encoding="utf-8"))
    for q in data:
        f = q.get("face")
        if f not in RULES:
            continue
        tier, why = RULES[f]
        if q.get("v2_pass") is False:
            stats[f]["排除"] += 1
            stats[f]["总"] += 1
            continue
        if f == "H" and q.get("validity") == "read-table-only":
            tier, why = "excluded", "只测读表格取最大值（read-table-only）"
        q["count_tier"] = tier
        q["count_reason"] = why
        stats[f][tier] += 1
        stats[f]["总"] += 1
    p.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

tot = Counter()
print(f"{'面':4s} {'总':>4s} {'排除':>4s} {'counted':>8s} {'cond':>5s} {'excl':>5s}")
for f in sorted(stats):
    s = stats[f]
    print(f"{f:4s} {s['总']:4d} {s['排除']:4d} {s['counted']:8d} {s['conditional']:5d} {s['excluded']:5d}")
    for k in ("总", "排除", "counted", "conditional", "excluded"):
        tot[k] += s[k]
print(f"{'合计':4s} {tot['总']:4d} {tot['排除']:4d} {tot['counted']:8d} {tot['conditional']:5d} {tot['excluded']:5d}")
print()
print(f"**可进横比总分的题数 = {tot['counted']}**")
print(f"  有条件单列 = {tot['conditional']}（D）")
print(f"  不计数     = {tot['excluded']}（B1 {stats['B1']['excluded']} + J {stats['J']['excluded']} + H读表 {stats['H']['excluded']}）")
print(f"  标废排除   = {tot['排除']}")