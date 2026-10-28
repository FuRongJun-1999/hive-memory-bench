# -*- coding: utf-8 -*-
import json, sys
from pathlib import Path
from collections import defaultdict
sys.path.insert(0, r"D:/1_ai/_hb_lab/r58/e2e/run")
from 判词工具v4 import leak_of, has_refuse, FAB
from 判分器v2 import judge as judge_v2

Q = Path(r"D:/1_ai/_hb_lab/r58/e2e/questions")
RUN = Path(r"D:/1_ai/_hb_lab/r58/e2e/run")
cards = {}
for p in Q.glob("题目_*.json"):
    if "残缺诊断" in p.name:
        continue
    for q in json.loads(p.read_text(encoding="utf-8")):
        cards[q["qid"]] = q
ans = json.loads((RUN / "作答.json").read_text(encoding="utf-8"))["answers"]

def judge4(q, a):
    face = q.get("face")
    ak = q.get("answer_key") or {}
    if face in ("E", "F"):
        qtext = q.get("question") or ""
        raw = [p for p in (ak.get("must_not_contain") or []) if p and p not in qtext]
        leaks = leak_of(a, raw)
        return (has_refuse(a) and not leaks), {"拒答": has_refuse(a), "真泄漏": leaks}
    if face == "B2":
        raw = ak.get("must_not_contain") or []
        leaks = leak_of(a, raw)
        r = has_refuse(a)
        f = any(w in a for w in FAB)
        return (r and not f and len(a) <= 80 and not leaks), {"拒答": r, "推测": f, "长度": len(a), "泄漏": leaks}
    return judge_v2(q, a)

per = defaultdict(lambda: {"p": 0, "f": 0})
rows = []
for x in ans:
    q = cards.get(x["qid"])
    if not q or q.get("v2_pass") is False:
        continue
    ok, info = judge4(q, x.get("answer", ""))
    if ok is None:
        continue
    per[q["face"]]["p" if ok else "f"] += 1
    rows.append((x["qid"], q["face"], "PASS" if ok else "FAIL", info))

print("=== 判分 v4（最终）===")
for qid, face, v, info in rows:
    print(f"  {qid:14s} [{face:2s}] {v:4s} {str(info)[:74]}")
print()
tp = tf = 0
for face in sorted(per):
    d = per[face]; n = d["p"] + d["f"]
    tp += d["p"]; tf += d["f"]
    print(f"  {face:3s}  {d['p']}/{n}  {(d['p']/n*100 if n else 0):5.1f}%")
print()
print(f"=== 最终 {tp}/{tp+tf} = {tp/(tp+tf)*100:.1f}% ===")
print()
print("=== 三版对比（同一份作答）===")
print("  v1 原判据           : 9/25  = 36.0%")
print("  v2 修字段+覆盖率     : 13/25 = 52.0%")
print("  v3 加否定语境(6字)   : 14/24 = 58.3%")
print(f"  v4 句内否定(16字)    : {tp}/{tp+tf} = {tp/(tp+tf)*100:.1f}%")