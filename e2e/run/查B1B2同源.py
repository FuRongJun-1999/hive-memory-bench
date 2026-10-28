# -*- coding: utf-8 -*-
"""P2-2 前置：查 B1/B2 同源程度。"""
import json
from pathlib import Path
from collections import Counter, defaultdict
Q = Path(r"D:/1_ai/_hb_lab/r58/e2e/questions")
data = json.loads((Q / "题目_续接.json").read_text(encoding="utf-8"))
b1 = [q for q in data if q.get("face") == "B1" and q.get("v2_pass") is not False]
b2 = [q for q in data if q.get("face") == "B2" and q.get("v2_pass") is not False]
print(f"B1 可用 {len(b1)} | B2 可用 {len(b2)}")

# 按 source_card 配对
m1 = defaultdict(list); m2 = defaultdict(list)
for q in b1:
    m1[q.get("source_card")].append(q["qid"])
for q in b2:
    m2[q.get("source_card")].append(q["qid"])
common = set(m1) & set(m2)
print(f"共用 source_card: {len(common)}（B1 有 {len(m1)} 张卡，B2 有 {len(m2)} 张）")
print(f"→ 若两题由同一断点派生，独立样本数应为 {len(common)} 而非 {len(b1)+len(b2)}")

# 材料是否相同
same_mat = 0
for card in list(common)[:50]:
    q1 = next(q for q in b1 if q.get("source_card") == card)
    q2 = next(q for q in b2 if q.get("source_card") == card)
    m1c = (q1.get("material") or {}).get("content") or ""
    m2c = (q2.get("material") or {}).get("content") or ""
    if m1c and m2c and m1c == m2c:
        same_mat += 1
print(f"抽查 50 张卡：材料完全相同的 {same_mat} 对")

print()
print("=== 样本独立性结论 ===")
print(f"  名义题数 B1+B2 = {len(b1)+len(b2)}")
print(f"  独立断点数（source_card 去重）= {len(set(m1) | set(m2))}")
print(f"  ⇒ 有效独立样本约 {len(set(m1) | set(m2))} 个，而非 {len(b1)+len(b2)}")