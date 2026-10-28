# -*- coding: utf-8 -*-
"""P1-1：C 面 30 题答案键是否在材料窗内的全量审计。"""
import json, re
from pathlib import Path
Q = Path(r"D:/1_ai/_hb_lab/r58/e2e/questions")

def norm(s):
    return re.sub(r"[^\w]", "", s or "", flags=re.UNICODE)

data = json.loads((Q / "题目_自我.json").read_text(encoding="utf-8"))
bad, warn, ok = [], [], []
for q in data:
    if q.get("v2_pass") is False:
        continue
    mat = norm((q.get("material") or {}).get("content") or "")
    ak = q.get("answer_key") or {}
    probes = [("must_contain", p) for p in (ak.get("must_contain") or [])]
    if ak.get("unique_fragment"):
        probes.append(("unique_fragment", ak["unique_fragment"]))
    hits = []
    for tag, p in probes:
        np = norm(p)
        if not np:
            continue
        if np in mat:
            hits.append((tag, "全中", len(np)))
        else:
            # 找最长可匹配前缀/子串，判断是否部分在
            best = 0
            for L in range(len(np), 7, -1):
                found = False
                for i in range(0, len(np) - L + 1):
                    if np[i:i+L] in mat:
                        best = L
                        found = True
                        break
                if found:
                    break
            hits.append((tag, f"最长子串{best}", len(np)))
    allin = all(h[1] == "全中" for h in hits)
    rec = (q["qid"], q.get("subface"), hits)
    if allin:
        ok.append(rec)
    elif any(h[1] == "全中" for h in hits):
        warn.append(rec)
    else:
        bad.append(rec)

print(f"C 面审计（{len(data)} 题，跳过已标废）")
print(f"  答案键全在材料窗内: {len(ok)}")
print(f"  部分在（有隐患）   : {len(warn)}")
print(f"  **全都不在（必假阴）**: {len(bad)}")
print()
if bad:
    print("=== 必假阴（答案键完全不在材料窗内）===")
    for qid, sub, hits in bad:
        print(f"  {qid} [{sub}] {hits}")
if warn:
    print()
    print("=== 隐患（部分在）===")
    for qid, sub, hits in warn:
        print(f"  {qid} [{sub}] {hits}")