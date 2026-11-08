# -*- coding: utf-8 -*-
"""按四层口径报读数（修正：D 面只用新人设的 45 题数据，剔除旧人设 3 题）。"""
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

# D 面只用新数据（a2）；其余用 a1
merged = [x for x in a1 if cards.get(x["qid"], {}).get("face") != "D"] + a2
print(f"数据源：a1 中非 D 的 {len([x for x in a1 if cards.get(x['qid'], {}).get('face') != 'D'])} 条 + D 面新数据 {len(a2)} 条 = {len(merged)}")
print(f"  （已剔除 a1 里 3 道旧人设 D 题：{len(a1) - len([x for x in a1 if cards.get(x['qid'], {}).get('face') != 'D']) } 条）")
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
    got, _ = judge_D(q, a.get("answer", "")) if q.get("face") == "D" else m.judge5(q, a.get("answer", ""))
    if got is None:
        per[q["face"]]["review"] += 1; continue
    per[q["face"]]["p" if got else "f"] += 1

TIER = {"B2": "ability", "C": "ability", "D": "ability", "E": "ability", "F": "ability",
        "L1": "control", "H": "diagnostic"}
print("=" * 60)
print("第二期测评集 · 灵枢自测读数（四层口径 v1.0，判据 v1.1）")
print("=" * 60)
for tier in ["ability", "control", "diagnostic"]:
    tp = tf = 0
    rows = []
    for f in ["B2", "C", "D", "E", "F", "L1", "H"]:
        if TIER.get(f) != tier or f not in per:
            continue
        d = per[f]; n = d["p"] + d["f"]
        if not n:
            continue
        tp += d["p"]; tf += d["f"]
        rows.append(f"  {f:3s} {d['p']:2d}/{n:2d}  {d['p']/n*100:5.1f}%  review {d['review']}")
    print(f"
【{tier}】")
    for r in rows:
        print(r)
    if tp + tf:
        print(f"  ── 小计 {tp}/{tp+tf} = {tp/(tp+tf)*100:.1f}%")
print()
print("【excluded】B1 / J —— 不计数，不报读数")
print("【空缺面】I / G / 情感三式 —— 0 题，不计入任何总分")
print()
notes = []
if "C" not in per:
    notes.append("C 面：本次数据无 C 题（25 题盲卷未抽到 C）")
notes.append("D 面：全特征判定；单特征判定为 45/45=100%（无区分度，作诊断用）")
notes.append("L1 是阴性对照，100% 只说明「尺子没坏」，不是能力分")
notes.append("H 是 diagnostic，3 题同段落，独立样本=1")
print("【必须一起报的说明】")
for n in notes:
    print("  ·", n)