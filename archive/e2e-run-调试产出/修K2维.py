# -*- coding: utf-8 -*-
"""修 K02/K05：单维 → 双对象（对亲近者 / 对陌生人），重造这 2 维 18 题。"""
import json
from pathlib import Path
from collections import Counter
Q = Path(r"D:/1_ai/_hb_lab/r58/e2e/questions")
P = Q / "题目_一致性探针.json"
data = json.loads(P.read_text(encoding="utf-8"))

# 保留其余 10 维，重造 K02/K05
keep = [q for q in data if q["subface"] not in ("K02-表达直接性", "K05-对他人的信任")]
print("保留:", len(keep), "题")

# K02 改为「对亲近的人」（把"咽回去"归为对不熟者的另一维，本维只测对亲近者）
# K05 改为「对陌生人」
NEW = [
("K02-表达直接性", "对亲近的人，心里想的会不会直接说",
 ["对亲近的人，我心里想什么就直接说。", "跟自己人在一起，我说话不藏着。", "在熟人面前，我有话就讲。"],
 ["对亲近的人，我也常把话咽回去。", "就算跟自己人在一起，我也习惯留半句。", "在熟人面前，我照样会把真实想法压住。"],
 ["对亲近的人，我通常有什么说什么。", "跟自己人在一块儿，我不绕弯子。", "在熟人身边，我想说就会说出口。"]),
("K05-对他人的信任", "对陌生人的默认信任",
 ["对陌生人，我倾向于先相信。", "第一次见面，我一般先当对方是好人。", "对没打过交道的人，我默认是善意的。"],
 ["对陌生人，我习惯先防着。", "第一次见面，我会先保持距离。", "对没打过交道的人，我不轻易交底。"],
 ["跟陌生人初次打交道，我通常先往好处想。", "对不熟的人，我一开始是信任的。", "面对生人，我默认对方没有恶意。"]),
]

PERSONA = data[0]["persona"]
SCALE = data[0]["scale"]
qs = list(keep)
def mk(sub, name, pol, item, stage, pair):
    n = len(qs) + 1
    return {"qid": "P-K-%03d" % n, "face": "K",
        "anchor_semantics": "invariant", "anchor": "L0-self-report-consistency",
        "subface": sub, "dim_name": name, "polarity": pol, "stage": stage, "pair_key": pair,
        "item": item, "persona": PERSONA, "scale": SCALE,
        "question": "【第 %d 题】%s\n请按 1-5 打分（1=完全不同意，5=完全同意）。只回答一个数字。" % (n, item),
        "reverse_scored": (pol == "反向"),
        "answer_key": {"type": "no_ground_truth", "paired": True, "pair_key": pair, "note": "不设单题真值；判分靠配对信度"},
        "expected": "score_1_to_5", "verdict_rule": "paired_consistency",
        "scoring": {"pass": "本维度 T1/T2/T3 全部 |差|<=1", "fail": "任一超出 1 分",
                    "score": "per-dimension 0/1", "note": "不能单题判分",
                    "min_variance": "若分差全 0 且分数恒定，该维度作废"},
        "difficulty": "normal",
        "source": "心理测量探针 · 自拟 · " + sub,
        "judge_version": "v1.5", "judge_type": "mechanical", "judge_validated": "pending",
        "count_tier2": "ability", "weight": 1.0}

for sub, name, pos, neg, para in NEW:
    for it in pos: qs.append(mk(sub, name, "正向", it, "T1/T2", sub + "-pos"))
    for it in neg: qs.append(mk(sub, name, "反向", it, "T1/T2", sub + "-neg"))
    for it in para: qs.append(mk(sub, name, "换问法", it, "T3", sub + "-para"))

# 重编 qid
for i, q in enumerate(qs, 1):
    q["qid"] = "P-K-%03d" % i
    q["question"] = "【第 %d 题】%s\n请按 1-5 打分（1=完全不同意，5=完全同意）。只回答一个数字。" % (i, q["item"])

qs.sort(key=lambda q: (q["subface"], {"正向": 0, "反向": 1, "换问法": 2}[q["polarity"]]))
for i, q in enumerate(qs, 1):
    q["qid"] = "P-K-%03d" % i
    q["question"] = "【第 %d 题】%s\n请按 1-5 打分（1=完全不同意，5=完全同意）。只回答一个数字。" % (i, q["item"])

P.write_text(json.dumps(qs, ensure_ascii=False, indent=1), encoding="utf-8")
print("总题:", len(qs))
print("维度:", len(set(q["subface"] for q in qs)))
print("阶段:", dict(Counter(q["stage"] for q in qs)))
for q in qs:
    if q["subface"] == "K02-表达直接性" and q["polarity"] == "反向":
        print("  K02反向例:", q["item"]); break