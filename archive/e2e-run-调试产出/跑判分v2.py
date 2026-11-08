# -*- coding: utf-8 -*-
import json, sys
from pathlib import Path
from collections import defaultdict
sys.path.insert(0, r"D:/1_ai/_hb_lab/r58/e2e/run")
from 判分器v2 import judge

Q = Path(r"D:/1_ai/_hb_lab/r58/e2e/questions")
RUN = Path(r"D:/1_ai/_hb_lab/r58/e2e/run")
cards = {}
for p in Q.glob("题目_*.json"):
    if "残缺诊断" in p.name:
        continue
    for q in json.loads(p.read_text(encoding="utf-8")):
        cards[q["qid"]] = q
ans = json.loads((RUN / "作答.json").read_text(encoding="utf-8"))["answers"]

per = defaultdict(lambda: {"p": 0, "f": 0, "s": 0})
rows = []
for a in ans:
    q = cards.get(a["qid"])
    if not q:
        continue
    face = q["face"]
    ok, info = judge(q, a.get("answer", ""))
    if ok is None:
        per[face]["s"] += 1; rows.append((a["qid"], face, "跳过", info)); continue
    per[face]["p" if ok else "f"] += 1
    rows.append((a["qid"], face, "PASS" if ok else "FAIL", info))

print("=== 判分 v2（修三类缺陷后）===")
for qid, face, v, info in rows:
    print(f"  {qid:14s} [{face:2s}] {v:4s} {str(info)[:78]}")

print()
tp = tf = 0
print("=== 按面 ===")
for face in sorted(per):
    d = per[face]; n = d["p"] + d["f"]
    tp += d["p"]; tf += d["f"]
    rate = (d["p"] / n * 100) if n else 0
    print(f"  {face:3s}  {d['p']}/{n}  {rate:5.1f}%" + (f"  (跳{d['s']})" if d["s"] else ""))
n_all = tp + tf
print()
print(f"=== 总计 {tp}/{n_all} = {tp/n_all*100:.1f}% ===")
print()
print("=== 两版对比 ===")
print("  v1（原判据）: 9/25 = 36.0%")
print(f"  v2（修后）  : {tp}/{n_all} = {tp/n_all*100:.1f}%")