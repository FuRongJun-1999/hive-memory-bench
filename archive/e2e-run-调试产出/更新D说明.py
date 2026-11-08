# -*- coding: utf-8 -*-
import json
from pathlib import Path
Q = Path(r"D:/1_ai/_hb_lab/r58/e2e/questions")
P = Q / "题目_人设.json"
data = json.loads(P.read_text(encoding="utf-8"))
for q in data:
    q["count_reason"] = ("五特征可机械判；人设已从「我·持灯人」换为自然自称「在下」"
                         "（子代理实测三种候选自称均可守住，判据冒烟 10/10）；"
                         "**待 45 题实跑复验后方可升 counted**")
P.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
print("D 面已更新 count_reason，保持 conditional")