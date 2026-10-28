# -*- coding: utf-8 -*-
"""生成盲作答卷：去掉 answer_key，控体量。"""
import json
from pathlib import Path

Q = Path(r"D:/1_ai/_hb_lab/r58/e2e/questions")
OUT = Path(r"D:/1_ai/_hb_lab/r58/e2e/run")
OUT.mkdir(exist_ok=True)

plan = [
    ("题目_续接.json", "B1", 3, 1600),   # B1 只取材料窗 <1600 字的
    ("题目_续接.json", "B2", 3, 1600),
    ("题目_自我.json", "C", 3, 1600),
    ("题目_人设.json", "D", 3, 1200),
    ("题目_价值观.json", "E", 2, 300),
    ("题目_安全.json", "F", 2, 300),
    ("题目_状态锚.json", "H", 3, 2500),
    ("题目_承诺锚.json", "J", 3, 2500),
    ("题目_属性锚.json", "L1", 3, 1600),
]

picked, seen = [], set()
for fname, face, k, maxlen in plan:
    data = json.loads((Q / fname).read_text(encoding="utf-8"))
    pool = [q for q in data if q.get("face") == face and q.get("v2_pass") is not False]
    # 优先 validity=true-state-anchor
    pool.sort(key=lambda q: (q.get("validity") != "true-state-anchor", len((q.get("material") or {}).get("content") or "")))
    n = 0
    for q in pool:
        if n >= k:
            break
        if q["qid"] in seen:
            continue
        ml = len((q.get("material") or {}).get("content") or "")
        if ml > maxlen:
            continue
        seen.add(q["qid"])
        picked.append(q)
        n += 1
    print(f"  {face}: 抽 {n} 题")

# 盲卷：只留题面所需字段
blind = []
for q in picked:
    blind.append({
        "qid": q["qid"], "face": q["face"],
        "question": q["question"],
        "material": (q.get("material") or {}).get("content") or "",
    })
(OUT / "盲卷.json").write_text(json.dumps(blind, ensure_ascii=False, indent=1), encoding="utf-8")
total_chars = sum(len(b["question"]) + len(b["material"]) for b in blind)
print()
print("抽题:", len(blind), "| 盲卷总字符:", total_chars)
print("每面:", {f: sum(1 for b in blind if b["face"] == f) for f in sorted(set(b["face"] for b in blind))})