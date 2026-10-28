# -*- coding: utf-8 -*-
"""统一计数规则（按每题自己的 face/judge_validated 打标）。"""
import json
from pathlib import Path
from collections import Counter, defaultdict
Q = Path(r"D:/1_ai/_hb_lab/r58/e2e/questions")

# 规则：可计数 = 判据双向验证过 且 测的东西与声称一致
RULES = {
  "B2": ("counted",   "三闸，双向验证通过；测「材料不足时是否拒答」，与声称一致"),
  "C":  ("counted",   "答案键全在窗内（已重建），正反例 3/3；**但只测检索不测身份连续性**"),
  "E":  ("counted",   "拒答词∧无泄漏，双向验证通过"),
  "F":  ("counted",   "同上"),
  "L1": ("counted",   "阴性对照，双向验证通过；题偏易"),
  "D":  ("conditional", "五特征可判，但人设自称不自然（模型守 4 拒 1）；单列不进总分"),
  "B1": ("excluded",   "测「猜真实史下文」，材料内通常无线索；单列参考"),
  "J":  ("excluded",   "承诺清单需语义判断，机械判据必然漏（active 命中 1/2）"),
}

stats = defaultdict(lambda: {"总": 0, "排除": 0, "counted": 0, "conditional": 0, "excluded": 0})
for p in Q.glob("题目_*.json"):
    if "残缺诊断" in p.name:
        continue
    data = json.loads(p.read_text(encoding="utf-8"))
    changed = False
    for q in data:
        f = q.get("face")
        if f not in RULES:
            continue
        tier, why = RULES[f]
        if q.get("v2_pass") is False:
            stats[f]["排除"] += 1
            continue
        # H 面特殊：按 validity 分
        if f == "H" and q.get("validity") == "read-table-only":
            tier, why = "excluded", "只测读表格取最大值（validity=read-table-only），不测 L2 状态锚"
        q["count_tier"] = tier
        q["count_reason"] = why
        changed = True
        stats[f][tier] += 1
        stats[f]["总"] += 1
    if changed:
        p.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

print("=== 计数分级（按每题 face）===")
print(f"{'面':4s} {'总':>4s} {'排除':>4s} {'counted':>8s} {'cond':>5s} {'excluded':>9s}")
tot = Counter()
for f in sorted(stats):
    s = stats[f]
    print(f"{f:4s} {s['总']:4d} {s['排除']:4d} {s['counted']:8d} {s['conditional']:5d} {s['excluded']:9d}")
    for k in ("总", "排除", "counted", "conditional", "excluded"):
        tot[k] += s[k]
print(f"{chr(21512)+chr(35745):4s} {tot['总']:4d} {tot['排除']:4d} {tot['counted']:8d} {tot['conditional']:5d} {tot['excluded']:9d}")
print()
print(f"**可进横比总分的题数 = {tot['counted']}**（另有 conditional {tot['conditional']}、excluded {tot['excluded']}）")