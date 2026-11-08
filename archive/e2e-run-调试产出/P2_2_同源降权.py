# -*- coding: utf-8 -*-
"""P2-2：B1/B2 同源降权 + 全库 independence_cluster 打标。"""
import json
from pathlib import Path
from collections import defaultdict
Q = Path(r"D:/1_ai/_hb_lab/r58/e2e/questions")

P = Q / "题目_续接.json"
data = json.loads(P.read_text(encoding="utf-8"))
n = 0
for q in data:
    card = q.get("source_card")
    if card:
        q["independence_cluster"] = "card_" + str(card)
        q["independence_note"] = ("B1 与 B2 由同一断点派生（同 source_card），**不可相加**；"
                                  "两者的独立样本按断点计")
        n += 1
P.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
print("续接题打 independence_cluster:", n)

# H 面：同文件
P2 = Q / "题目_状态锚.json"
d2 = json.loads(P2.read_text(encoding="utf-8"))
n2 = 0
for q in d2:
    f = q.get("source_file") or ""
    q["independence_cluster"] = "file_" + (f[:20] if f else "unknown")
    if q.get("validity") == "true-state-anchor":
        q["independence_note"] = "3 道真状态锚题全部来自第八话「搬家」同一段落，**不是 3 个独立样本**"
        n2 += 1
P2.write_text(json.dumps(d2, ensure_ascii=False, indent=1), encoding="utf-8")
print("H 面打标:", len(d2), "（真状态锚", n2, "）")

# 统计：各面的独立簇数
print()
print("=== 各面独立簇 ===")
for p in sorted(Q.glob("题目_*.json")):
    if "残缺诊断" in p.name:
        continue
    dd = json.loads(p.read_text(encoding="utf-8"))
    if not dd:
        continue
    usable = [q for q in dd if q.get("v2_pass") is not False]
    clusters = set(q.get("independence_cluster") for q in usable if q.get("independence_cluster"))
    if not usable:
        continue
    f = usable[0].get("face")
    print(f"  {f:3s}: 可用 {len(usable):3d} 题 | 独立簇 {len(clusters):3d}" if clusters else f"  {f:3s}: 可用 {len(usable):3d} 题 | 独立簇（未标）")