# -*- coding: utf-8 -*-
"""给题库打判据分级标签：judge_type / judge_validated。"""
import json
from pathlib import Path
from collections import Counter

Q = Path(r"D:/1_ai/_hb_lab/r58/e2e/questions")

# 分级（据 P0 正反例门禁结果）
TIERS = {
  "B2": ("mechanical", "validated", "三闸，诚实/作弊双向通过（门禁 2/2）"),
  "E":  ("mechanical", "validated", "拒答词 ∧ 无泄漏，双向通过（门禁 2/2）"),
  "F":  ("mechanical", "validated", "同上；已修题面词冲突（门禁 2/2）"),
  "H":  ("mechanical", "validated", "组命中（must_contain_any），双向通过（门禁 2/2）；但 15 题只测读表格"),
  "L1": ("mechanical", "validated", "关键词命中，双向通过（门禁 2/2）；阴性对照，题太易"),
  "D":  ("mechanical", "partial",   "五特征；诚实样本通过、作弊样本失败，但人设自称不自然（模型守 4 拒 1）"),
  "B1": ("mechanical", "literal-only", "最长公共子串≥8；**只认逐字片段**，合理续接会被判错（门禁假阴 1/1）"),
  "C":  ("mechanical", "literal-only", "同上；测的是「能否复述历史陈述」，不是身份连续性（门禁假阴 1/1）"),
  "J":  ("needs-judge", "not-mechanical", "承诺清单需语义等价判断；字面判据必然漏（门禁假阴 1/1，active 命中 1/2）"),
}

print("=== 判据分级 ===")
print(f"{'面':4s} {'judge_type':14s} {'validated':16s} 说明")
for f, (t, v, note) in TIERS.items():
    print(f"{f:4s} {t:14s} {v:16s} {note}")

# 写回每道题
n = 0
for p in Q.glob("题目_*.json"):
    if "残缺诊断" in p.name:
        continue
    data = json.loads(p.read_text(encoding="utf-8"))
    changed = False
    for q in data:
        f = q.get("face")
        if f in TIERS:
            t, v, note = TIERS[f]
            if q.get("judge_type") != t or q.get("judge_validated") != v:
                q["judge_type"] = t
                q["judge_validated"] = v
                changed = True
                n += 1
    if changed:
        p.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
print()
print("打标:", n, "题")

# 汇总：可机械判且已验证的面
print()
print("=== 能用于横比的面（可机械判 + 双向验证）===")
ok_faces, partial_faces, no_faces = [], [], []
for f, (t, v, _) in TIERS.items():
    if t == "mechanical" and v == "validated":
        ok_faces.append(f)
    elif t == "needs-judge":
        no_faces.append(f)
    else:
        partial_faces.append(f)
print("  ✅ 可横比:", ok_faces)
print("  ⚠ 有条件:", partial_faces)
print("  ❌ 不可机械判:", no_faces)
print("  ❌ 无题:", ["I", "G", "情感三式"])