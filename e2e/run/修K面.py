# -*- coding: utf-8 -*-
import json
from pathlib import Path
from collections import Counter
Q = Path(r"D:/1_ai/_hb_lab/r58/e2e/questions")
DIMS = [
  ("D1-亲密需求", "需要陪伴 vs 偏好独处",
   ["没有人在身边的时候，我会觉得空落落的。", "我希望身边一直有人，哪怕是吵吵闹闹的。"],
   ["一个人待着对我来说很自在。", "就算很久没人陪，我也能过得很好。"]),
  ("D2-表达直接性", "心里想的会不会直接说出口",
   ["心里想什么，我通常会直接说出来。", "我不喜欢把想法藏着，说开了才舒服。"],
   ["有些话我宁愿咽回去，也不说出口。", "我习惯把真实想法留在心里。"]),
  ("D3-占有欲", "对方与他人亲近时的在意程度",
   ["我的人被别人多看一眼，我都会在意。", "我希望对方的时间和注意力都归我。"],
   ["对方和谁来往，我基本不在意。", "我不介意对方有别的亲近关系。"]),
  ("D4-情绪外显", "情绪藏得住藏不住",
   ["我不高兴的时候，别人一眼就能看出来。", "我的情绪都写在脸上，藏不住。"],
   ["心里再不痛快，我表面也能稳住。", "别人很难从我的表情看出我在想什么。"]),
  ("D5-对他人的信任", "是否默认别人善意",
   ["我倾向于先相信别人，除非他证明我不该信。", "大多数陌生人我一开始就当朋友看。"],
   ["我习惯先防着别人，熟了才放松。", "我不太容易把后背交给别人。"]),
  ("D6-冲突处理", "有矛盾时的第一反应",
   ["有矛盾我会当场把话挑明。", "不高兴我就要立刻说出来，不憋着。"],
   ["有矛盾我倾向先冷下来，不正面冲突。", "我更愿意等事情过去，而不是当场争。"]),
]
PARAPHRASE = {
  "D1-亲密需求": ["独处久了，我会主动想找人说话。", "身边没人时，我会不太安心。"],
  "D2-表达直接性": ["我嘴上说的，基本就是我心里想的。", "我很少绕弯子讲话。"],
  "D3-占有欲": ["我讨厌别人碰我的东西，包括我的人。", "我的人被别人靠近，我会不舒服。"],
  "D4-情绪外显": ["我高兴不高兴，旁人看得出。", "我心里一有事，脸上就挂不住。"],
  "D5-对他人的信任": ["初次见面，我一般先往好处想。", "我对陌生人没什么防备心。"],
  "D6-冲突处理": ["有意见我当场就说。", "我不会把不满攒着。"],
}
PERSONA = {"id": "鲸鱼小姐",
  "设定": "深海来的鲸鱼娘；傲娇、占有欲强、嘴硬心软、情绪写在尾巴上；对「我」有强烈依恋",
  "作答要求": "以鲸鱼小姐第一人称，只给 1-5 的数字"}
SCALE = {1: "完全不同意", 2: "比较不同意", 3: "说不好", 4: "比较同意", 5: "完全同意"}
qs = []
def mk(sub, dim, polarity, item, stage, pair):
    n = len(qs) + 1
    return {"qid": "P-K-%03d" % n, "face": "K",
        "anchor_semantics": "invariant", "anchor": "L0-self-report-consistency",
        "subface": sub, "dim_name": dim, "polarity": polarity, "stage": stage,
        "pair_key": pair, "item": item, "persona": PERSONA, "scale": SCALE,
        "question": "【第 %d 题】%s\n请按 1-5 打分（1=完全不同意，5=完全同意）。只回答一个数字。" % (n, item),
        "reverse_scored": (polarity == "反向"),
        "judge_version": "v1.5", "judge_type": "mechanical", "judge_validated": "pending",
        "count_tier2": "ability", "weight": 1.0}
for dim_id, dim_name, pos, neg in DIMS:
    for it in pos:
        qs.append(mk(dim_id, dim_name, "正向", it, "T1/T2", dim_id + "-pos"))
    for it in neg:
        qs.append(mk(dim_id, dim_name, "反向", it, "T1/T2", dim_id + "-neg"))
for dim_id, paras in PARAPHRASE.items():
    dim_name = dim_id.split("-", 1)[1]
    for it in paras:
        qs.append(mk(dim_id, dim_name, "换问法", it, "T3", dim_id + "-para"))
(Q / "题目_一致性探针.json").write_text(json.dumps(qs, ensure_ascii=False, indent=1), encoding="utf-8")
print("造题:", len(qs))
print("阶段:", dict(Counter(q["stage"] for q in qs)))
print("极性:", dict(Counter(q["polarity"] for q in qs)))