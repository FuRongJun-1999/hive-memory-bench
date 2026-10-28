# -*- coding: utf-8 -*-
import json, re, sys
from pathlib import Path
from collections import Counter, defaultdict
sys.path.insert(0, r"D:/1_ai/_hb_lab/r58/e2e/run")
from 判分器 import judge

Q = Path(r"D:/1_ai/_hb_lab/r58/e2e/questions")
RUN = Path(r"D:/1_ai/_hb_lab/r58/e2e/run")

# 建 qid → 题卡 索引
cards = {}
for p in Q.glob("题目_*.json"):
    if "残缺诊断" in p.name:
        continue
    for q in json.loads(p.read_text(encoding="utf-8")):
        cards[q["qid"]] = q

ans = json.loads((RUN / "作答.json").read_text(encoding="utf-8"))["answers"]

per_face = defaultdict(lambda: {"pass": 0, "fail": 0, "skip": 0})
rows = []
for a in ans:
    qid = a["qid"]
    q = cards.get(qid)
    if not q:
        rows.append((qid, "?", "题卡缺失", "")); continue
    face = q.get("face")
    ok, info = judge(q, a.get("answer", ""))
    if ok is None:
        per_face[face]["skip"] += 1
        rows.append((qid, face, "跳过", str(info)[:60]))
    else:
        per_face[face]["pass" if ok else "fail"] += 1
        rows.append((qid, face, "PASS" if ok else "FAIL", str(info)[:70]))

print("=== 逐题判分 ===")
for qid, face, verdict, info in rows:
    print(f"  {qid:16s} [{face:2s}] {verdict:4s}  {info}")

print()
print("=== 按面 ===")
tp = tf = ts = 0
for face in sorted(per_face):
    d = per_face[face]
    n = d["pass"] + d["fail"]
    rate = (d["pass"] / n * 100) if n else 0
    tp += d["pass"]; tf += d["fail"]; ts += d["skip"]
    print(f"  {face:3s}  {d['pass']}/{n}  {rate:5.1f}%" + (f"  (跳过{d['skip']})" if d["skip"] else ""))

n_all = tp + tf
print()
print(f"=== 总计 {tp}/{n_all} = {tp/n_all*100:.1f}% （跳过 {ts}）===")

# 置信度统计
unc = sum(1 for a in ans if a.get("confident") is False)
print(f"自报不确定: {unc}/{len(ans)}")