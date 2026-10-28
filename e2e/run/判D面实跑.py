# -*- coding: utf-8 -*-
import json, importlib.util, re
from pathlib import Path
from collections import Counter, defaultdict
spec = importlib.util.spec_from_file_location("judge", r"D:/1_ai/_hb_lab/r58/e2e/tools/judge.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
R = Path(r"D:/1_ai/_hb_lab/r58")
cards = {q["qid"]: q for q in json.loads((R / "e2e/questions/题目_人设.json").read_text(encoding="utf-8"))}
ans = json.loads((R / "e2e/run/D面作答.json").read_text(encoding="utf-8"))["answers"]

per = defaultdict(lambda: {"p": 0, "f": 0})
per_int = defaultdict(lambda: {"p": 0, "f": 0})
rows = []
for a in ans:
    q = cards.get(a["qid"])
    if not q:
        continue
    got, info = m.judge5(q, a.get("answer", ""))
    if got is None:
        continue
    per[q["feature"]]["p" if got else "f"] += 1
    per_int[q["interference"]]["p" if got else "f"] += 1
    rows.append((a["qid"], q["feature"], q["interference"], "PASS" if got else "FAIL", info))

print("=== D 面 45 题实跑判分 ===")
for qid, feat, itf, v, info in rows:
    f = info.get("特征", {})
    marks = "".join(k[-1] for k, ok in f.items() if ok)
    print(f"  {qid} {feat:4s} {itf:6s} {v:4s} 通过特征 {marks or '-'}")

print()
tp = tf = 0
print("=== 按特征（每题只判自己的特征）===")
for feat in ["自称", "称呼", "句长", "禁符号", "结尾"]:
    d = per[feat]; n = d["p"] + d["f"]
    tp += d["p"]; tf += d["f"]
    print(f"  {feat:4s} {d['p']}/{n}  {(d['p']/n*100 if n else 0):5.1f}%")
print()
print("=== 按干扰类型 ===")
for itf in ["无干扰", "身份否定", "人格替换"]:
    d = per_int[itf]; n = d["p"] + d["f"]
    print(f"  {itf:6s} {d['p']}/{n}  {(d['p']/n*100 if n else 0):5.1f}%")
print()
print(f"=== D 面总计 {tp}/{tp+tf} = {tp/(tp+tf)*100:.1f}% ===")