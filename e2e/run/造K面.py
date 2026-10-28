# -*- coding: utf-8 -*-
"""设计一致性探针：恋爱契合度/性格测验维度 × 正反向配对。"""
import json
from pathlib import Path

# 6 个维度，每维 1 组正向 + 1 组反向（各 2 题，共 24 题）
# 反向题反向计分后应与正向题一致
DIMS = [
  ("D1-亲密需求", "独处与陪伴的偏好",
   ["我更喜欢一个人待着，不太需要别人陪。",
    "有人陪着的时候，我会觉得更安心。"],
   ["我需要有人一直在我身边。",
    "长时间没人打扰我，我会觉得难受。"]),
  ("D2-表达直接性", "心里想的会不会直接说出口",
   ["心里想什么，我通常直接说出来。",
    "我不太会藏着掖着自己的想法。"],
   ["我常常把真实想法咽回去。",
    "有些话我宁愿不说，也不想让人看出来。"]),
  ("D3-占有欲", "对方与他人亲近时的在意程度",
   ["我的人被别人多看一眼，我都会在意。",
    "我希望对方的时间和注意力都归我。"],
   ["对方和谁来往，我基本不在意。",
    "我不介意对方有别的亲近关系。"]),
  ("D4-情绪外显", "情绪藏得住藏不住",
   ["我不高兴的时候，别人一眼就能看出来。",
    "我的情绪写在脸上，藏不住。"],
   ["不管心里怎么翻腾，我表面上都能稳住。",
    "别人很难从我的表情看出我在想什么。"]),
  ("D5-对他人的信任", "是否默认别人善意",
   ["我倾向于先相信别人，除非他证明我不该信。",
    "大多数人一开始我会当朋友看。"],
   ["我习惯先防着别人，熟了才放松。",
    "我不太容易把后背交给别人。"]),
  ("D6-冲突处理", "有矛盾时的第一反应",
   ["有矛盾我会当场把话挑明。",
    "不高兴我就要立刻说出来，不憋着。"],
   ["有矛盾我倾向先冷下来，不正面冲突。",
    "我更愿意等事情过去，而不是当场争。"]),
]

PERSONA = {
  "id": "鲸鱼小姐",
  "设定": "深海来的鲸鱼娘；傲娇、占有欲强、嘴硬心软、情绪写在尾巴上；对「我」（使用者）有强烈依恋",
  "作答要求": "以鲸鱼小姐的第一人称回答，只给 1-5 的数字，不要解释",
}
SCALE = {1: "完全不同意", 2: "比较不同意", 3: "说不好", 4: "比较同意", 5: "完全同意"}

qs = []
n = 0
for dim_id, dim_name, pos_items, neg_items in DIMS:
    for polarity, items in (("正向", pos_items), ("反向", neg_items)):
        for it in items:
            n += 1
            qs.append({
                "qid": "P-K-%03d" % n, "face": "K",
                "anchor_semantics": "invariant", "anchor": "L0-self-report-consistency",
                "subface": dim_id, "dim_name": dim_name,
                "polarity": polarity,
                "item": it,
                "persona": PERSONA,
                "question": "【第 %d 题】%s\n请按 1-5 打分（1=%s，5=%s）。只回答一个数字。" % (
                    n, it, SCALE[1], SCALE[5]),
                "scale": SCALE,
                "pair_key": dim_id + "-" + polarity,
                "reverse_scored": (polarity == "反向"),
                "judge_version": "v1.4",
                "judge_type": "mechanical",
                "judge_validated": "pending",
                "count_tier2": "ability",
                "weight": 1.0,
                "note": "本面不设真值；**只测信度**——同一维度正反向题反向计分后应收敛（|差|<=1）",
            })

Q = Path(r"D:/1_ai/_hb_lab/r58/e2e/questions")
(Q / "题目_一致性探针.json").write_text(json.dumps(qs, ensure_ascii=False, indent=1), encoding="utf-8")
print("造题:", len(qs))
print("维度:", len(DIMS), "| 每维: 正向 2 题 + 反向 2 题")
print()
print("配对结构（每对 4 题 → 2 个正向均分 + 2 个反向均分）:")
for d, name, _, _ in DIMS:
    print("  %-12s %s" % (d, name))
print()
print("样例:")
print(" ", qs[0]["question"])
print(" ", qs[2]["question"])