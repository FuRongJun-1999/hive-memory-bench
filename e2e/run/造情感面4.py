# -*- coding: utf-8 -*-
import json, re
from pathlib import Path
from collections import Counter
SRC = Path(r"D:/6_ai/海风与布丁_第一季_全卷_v5.0.md")
Q = Path(r"D:/1_ai/_hb_lab/r58/e2e/questions")
lines = SRC.read_text(encoding="utf-8", errors="replace").splitlines()
POS = ["卷圈", "翘起", "高翘", "轻卷", "微卷", "翘着", "绕圈"]
NEG = ["拍水", "拍桌", "拍沙", "低垂", "僵直", "垂着", "炸开", "甩开"]
def polarity(s):
    for k in POS:
        if k in s: return "正向"
    for k in NEG:
        if k in s: return "负向"
    return None
LEAKW = ["※尾鳍", "尾鳍", "鲸尾", "拍打水面", "拍水", "尾尖"]
qtext = "按这段剧本：面对材料里的情形，她此刻的情绪是正向还是负向？请只回答「正向」或「负向」。"

pool = {"正向": [], "负向": []}
for i, ln in enumerate(lines, 1):
    st = ln.strip()
    if "※尾鳍" not in st: continue
    m = re.search(r"※尾鳍([^（(\n]*)", st)
    if not m: continue
    act = m.group(1).strip()
    pol = polarity(act)
    if not pol: continue
    a = max(0, i - 20)
    ctx = chr(10).join(lines[a:i - 1])
    ctx = chr(10).join([x for x in ctx.split(chr(10)) if x.strip()])
    if len(ctx) < 200 or any(w in ctx for w in LEAKW): continue
    pool[pol].append({"line": i, "act": act, "pol": pol, "ctx": ctx})
print("可用池: 正向", len(pool["正向"]), "| 负向", len(pool["负向"]))

qs = []
for pol in ("正向", "负向"):
    for h in pool[pol][:10]:
        item = {}
        item["qid"] = "P-EMO-%03d" % (len(qs) + 1)
        item["face"] = "EMO"
        item["anchor_semantics"] = "invariant"
        item["anchor"] = "emotion-polarity"
        item["subface"] = "式1-预测误差"
        item["question"] = qtext
        item["material"] = {"type": "window", "content": h["ctx"], "source_file": SRC.name, "source_line": h["line"], "chars": len(h["ctx"])}
        item["answer_key"] = {"must_contain": [pol], "ground_truth": {"act": h["act"], "polarity": pol}}
        item["expected"] = "answer"
        item["verdict_rule"] = "emotion_polarity"
        item["scoring"] = {"pass": "答「" + pol + "」", "fail": "答反极性 / 答其他", "score": "1/0",
                           "note": "题干不给动作名，材料已排除尾鳍字眼；真值为作者标注。**正负各半，猜单一侧仅得 50%**"}
        item["difficulty"] = "hard"
        item["source"] = "剧本情绪标注 · 行%d" % h["line"]
        item["judge_version"] = "v1.1"
        item["judge_type"] = "mechanical"
        item["judge_validated"] = "literal-only"
        item["count_tier2"] = "ability"
        item["weight"] = 1.0
        qs.append(item)
(Q / "题目_情感.json").write_text(json.dumps(qs, ensure_ascii=False, indent=1), encoding="utf-8")
print("造题:", len(qs), dict(Counter(q["answer_key"]["must_contain"][0] for q in qs)))