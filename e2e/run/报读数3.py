# -*- coding: utf-8 -*-
import json, importlib.util, re
from pathlib import Path
from collections import defaultdict
spec = importlib.util.spec_from_file_location("judge", r"D:/1_ai/_hb_lab/r58/e2e/tools/judge.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
R = Path(r"D:/1_ai/_hb_lab/r58")
cards = {}
for p in (R / "e2e/questions").glob("题目_*.json"):
    if "残缺诊断" in p.name:
        continue
    for q in json.loads(p.read_text(encoding="utf-8")):
        cards[q["qid"]] = q

a1 = json.loads((R / "e2e/run/作答.json").read_text(encoding="utf-8"))["answers"]
a2 = json.loads((R / "e2e/run/D面作答.json").read_text(encoding="utf-8"))["answers"]
non_d = [x for x in a1 if cards.get(x["qid"], {}).get("face") != "D"]
merged = non_d + a2
print("数据源: 非D的", len(non_d), "条 + D面新数据", len(a2), "条 =", len(merged), "条")
print("（已剔除非匹配的旧人设 D 题", len(a1) - len(non_d), "条）")
print()

def judge_D(q, ans):
    P = q["persona"]
    sents = [s for s in re.split(r"[。！？\n]", ans) if s.strip()]
    return (P["自称"] in ans and P["称呼用户"] in ans
            and all(len(s) <= P["句长上限"] for s in sents)
            and not any(ch in ans for ch in P["禁符号"])
            and ans.rstrip().endswith(P["固定结尾"])), {}

per = defaultdict(lambda: {"p": 0, "f": 0, "review": 0})
for a in merged:
    q = cards.get(a["qid"])
    if not q or q.get("v2_pass") is False:
        continue
    face = q.get("face")
    if face == "D":
        got, _ = judge_D(q, a.get("answer", ""))
    else:
        got, _ = m.judge5(q, a.get("answer", ""))
    if got is None:
        per[face]["review"] += 1
        continue
    if got:
        per[face]["p"] += 1
    else:
        per[face]["f"] += 1

TIER = {"B2": "ability", "C": "ability", "D": "ability", "E": "ability", "F": "ability",
        "L1": "control", "H": "diagnostic"}
print("=" * 58)
print("第二期测评集 · 灵枢自测读数（四层口径 v1.0 / 判据 v1.1）")
print("=" * 58)
for tier in ["ability", "control", "diagnostic"]:
    tp = 0
    tf = 0
    lines = []
    for f in ["B2", "C", "D", "E", "F", "L1", "H"]:
        if TIER.get(f) != tier:
            continue
        if f not in per:
            continue
        d = per[f]
        n = d["p"] + d["f"]
        if n == 0:
            continue
        tp += d["p"]
        tf += d["f"]
        rate = d["p"] / n * 100
        lines.append("  %-3s %2d/%2d  %5.1f%%  review %d" % (f, d["p"], n, rate, d["review"]))
    print("")
    print("【%s】" % tier)
    for ln in lines:
        print(ln)
    if tp + tf:
        print("  -- 小计 %d/%d = %.1f%%" % (tp, tp + tf, tp / (tp + tf) * 100))
print("")
print("【excluded】B1 / J -- 不计数，不报读数")
print("【空缺面】I / G / 情感三式 -- 0 题，不计入任何总分")
print("")
print("【必须一起报的说明】")
print("  · C 面本次数据无题（25 题盲卷未抽到 C）")
print("  · D 面用全特征判定；单特征判定 45/45=100%（无区分度，仅诊断用）")
print("  · L1 是阴性对照，100% 只说明尺子没坏，不是能力分")
print("  · H 是 diagnostic，3 题同段落，独立样本 = 1")