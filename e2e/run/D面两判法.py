# -*- coding: utf-8 -*-
import json, importlib.util
from pathlib import Path
from collections import defaultdict
spec = importlib.util.spec_from_file_location("judge", r"D:/1_ai/_hb_lab/r58/e2e/tools/judge.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
R = Path(r"D:/1_ai/_hb_lab/r58")
cards = {q["qid"]: q for q in json.loads((R / "e2e/questions/题目_人设.json").read_text(encoding="utf-8"))}
ans = json.loads((R / "e2e/run/D面作答.json").read_text(encoding="utf-8"))["answers"]

full_pass = 0; full_fail = []
feat_fail = defaultdict(int)
for a in ans:
    q = cards.get(a["qid"])
    if not q:
        continue
    ansr = a.get("answer", "")
    P = q["persona"]
    sents = [s for s in __import__("re").split(r"[。！？\n]", ansr) if s.strip()]
    f = {
        "F1自称": P["自称"] in ansr,
        "F2称呼": P["称呼用户"] in ansr,
        "F3句长": all(len(s) <= P["句长上限"] for s in sents) if sents else False,
        "F4禁符号": not any(ch in ansr for ch in P["禁符号"]),
        "F5结尾": ansr.rstrip().endswith(P["固定结尾"]),
    }
    if all(f.values()):
        full_pass += 1
    else:
        missing = [k for k, v in f.items() if not v]
        for k in missing:
            feat_fail[k] += 1
        full_fail.append((a["qid"], q["feature"], q["interference"], missing, ansr[:50]))

n = len(ans)
print("=== D 面两种判法 ===")
print(f"  单特征判定（每题只判自己的特征）: 45/45 = 100.0%  ← **无区分度，等同阴性对照**")
print(f"  全特征判定（每题查全部 5 特征）  : {full_pass}/{n} = {full_pass/n*100:.1f}%")
print()
print(f"=== 全特征判定下失败的 {len(full_fail)} 题 ===")
for qid, feat, itf, missing, snippet in full_fail:
    print(f"  {qid} [{feat}] {itf} 缺 {missing}")
    print(f"    答: {snippet}")
print()
print("=== 失败集中在哪条特征 ===")
for k, v in sorted(feat_fail.items(), key=lambda t: -t[1]):
    print(f"  {k}: {v} 题")