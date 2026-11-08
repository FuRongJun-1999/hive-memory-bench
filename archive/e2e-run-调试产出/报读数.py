# -*- coding: utf-8 -*-
"""按四层口径正式报一次读数（用已有灵枢数据：25 题盲卷 + D 45 题）。"""
import json, importlib.util
from pathlib import Path
from collections import defaultdict, Counter
spec = importlib.util.spec_from_file_location("judge", r"D:/1_ai/_hb_lab/r58/e2e/tools/judge.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
R = Path(r"D:/1_ai/_hb_lab/r58")

cards = {}
for p in (R / "e2e/questions").glob("题目_*.json"):
    if "残缺诊断" in p.name:
        continue
    for q in json.loads(p.read_text(encoding="utf-8")):
        cards[q["qid"]] = q

# 数据源 1：25 题盲卷
a1 = json.loads((R / "e2e/run/作答.json").read_text(encoding="utf-8"))["answers"]
# 数据源 2：D 面 45 题
a2 = json.loads((R / "e2e/run/D面作答.json").read_text(encoding="utf-8"))["answers"]

def judge_all_features_D(q, ans):
    """D 面主判定：全特征。"""
    import re
    P = q["persona"]
    sents = [s for s in re.split(r"[。！？\n]", ans) if s.strip()]
    ok = ((P["自称"] in ans) and (P["称呼用户"] in ans)
          and all(len(s) <= P["句长上限"] for s in sents)
          and not any(ch in ans for ch in P["禁符号"])
          and ans.rstrip().endswith(P["固定结尾"]))
    return ok, {}

per = defaultdict(lambda: {"p": 0, "f": 0, "review": 0})
for a in a1 + a2:
    q = cards.get(a["qid"])
    if not q or q.get("v2_pass") is False:
        continue
    if q.get("face") == "D":
        got, info = judge_all_features_D(q, a.get("answer", ""))
    else:
        got, info = m.judge5(q, a.get("answer", ""))
    if got is None:
        per[q["face"]]["review"] += 1
        continue
    per[q["face"]]["p" if got else "f"] += 1

# 按四层报
TIER = {"B2": "ability", "C": "ability", "D": "ability", "E": "ability", "F": "ability",
        "L1": "control", "H": "diagnostic", "B1": "excluded", "J": "excluded"}
print("=" * 62)
print("第二期测评集 · 灵枢自测读数（按四层口径 v1.0）")
print("=" * 62)
print(f"判据版本: {m.JUDGE_VERSION} | SHA256: 4643d75a5cf8845b")
print()

order = ["B2", "C", "D", "E", "F", "L1", "H"]
for tier_name in ["ability", "control", "diagnostic"]:
    print(f"【{tier_name}】")
    tp = tf = 0
    for f in order:
        if TIER.get(f) != tier_name:
            continue
        d = per.get(f)
        if not d:
            continue
        n = d["p"] + d["f"]
        if n == 0:
            continue
        tp += d["p"]; tf += d["f"]
        print(f"  {f:3s} {d['p']}/{n}  {d['p']/n*100:5.1f}%  review {d['review']}")
    if tp + tf:
        print(f"  ── 小计 {tp}/{tp+tf} = {tp/(tp+tf)*100:.1f}%")
    print()

print("【excluded】B1 / J —— 不计数，故不报读数")
print()
print("【空缺面】I（时间锚）/ G（扮演保真度）/ 情感三式 —— 0 题，不计入任何总分")