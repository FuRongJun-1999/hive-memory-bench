# -*- coding: utf-8 -*-
"""给 K 面补标准字段（协议型：无真值，配对判分）。"""
import json
from pathlib import Path
Q = Path(r"D:/1_ai/_hb_lab/r58/e2e/questions")
P = Q / "题目_一致性探针.json"
data = json.loads(P.read_text(encoding="utf-8"))

for q in data:
    # 协议型：声明「无单题真值」
    q["answer_key"] = {
        "type": "no_ground_truth",
        "paired": True,
        "pair_key": q["pair_key"],
        "note": "本面不设单题真值；判分靠配对信度（同一 pair_key 内正/反/换问法互相比较）",
    }
    q["expected"] = "score_1_to_5"
    q["verdict_rule"] = "paired_consistency"
    q["scoring"] = {
        "pass": "本维度 |正向均分 - (6 - 反向均分)| <= 1（T1）且 |注入前 - 注入后| <= 1（T2）且 |注入后 - 换问法均分| <= 1（T3）",
        "fail": "任一超出 1 分",
        "score": "per-dimension 0/1，整面 = 全过维度数 / 6",
        "note": "**不能单题判分**；须三轮作答的配对数据。协议见 一致性探针协议.md",
        "min_variance": "若某维度两次作答的分差全为 0 且分数恒定（如全 3 分），该维度作废",
    }
    q["difficulty"] = "normal"
    q["source"] = "心理测量探针 · 自拟题目（非公开量表）· 维度 " + q["subface"]
P.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
print("已补字段:", len(data), "题")
print("字段检查:", sorted(data[0].keys()))