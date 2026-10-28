# -*- coding: utf-8 -*-
"""P1-2 + P1-3：①H 的 15 道读表题标 counted=false ②B1 四道超长窗题处置。"""
import json
from pathlib import Path
Q = Path(r"D:/1_ai/_hb_lab/r58/e2e/questions")

# ① H 面：读表题不计数
P = Q / "题目_状态锚.json"
data = json.loads(P.read_text(encoding="utf-8"))
n = 0
for q in data:
    if q.get("validity") == "read-table-only":
        q["counted"] = False
        q["counted_reason"] = "只测读表格取最大值，不测 L2 状态锚；不进横比总分"
        n += 1
    elif q.get("validity") == "true-state-anchor":
        q["counted"] = True
P.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"H 面: {len(data)} 题，标 counted=false {n}，counted=true {len(data)-n}")

# ② B1 四道超长窗：决定处置
P2 = Q / "题目_续接.json"
data2 = json.loads(P2.read_text(encoding="utf-8"))
print()
print("=== B1 超长窗题现状 ===")
for q in data2:
    m = (q.get("material") or {}).get("content") or ""
    if len(m) > 8000:
        print(f"  {q['qid']}: {len(m)} 字符, v2_pass={q.get('v2_pass')}")
        # 检查答案键是否在材料里（若在，说明只是窗太长；若不在，说明题本身坏）
        ak = q["answer_key"]
        mc = ak.get("must_contain") or []
        print(f"    答案键 {len(mc)} 条，是否在材料内: {[p[:20] in m for p in mc]}")