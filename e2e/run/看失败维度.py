# -*- coding: utf-8 -*-
import json
from pathlib import Path
R = Path(r"D:/1_ai/_hb_lab/r58")
cards = {q["qid"]: q for q in json.loads((R / "e2e/questions/题目_一致性探针.json").read_text(encoding="utf-8"))}
j = json.loads((R / "e2e/run/K108作答.json").read_text(encoding="utf-8"))
r1 = {x["qid"]: x["score"] for x in j["round1"]}
for dim in ("K02-表达直接性", "K05-对他人的信任"):
    print("=" * 66)
    print(dim)
    print("=" * 66)
    for qid, q in cards.items():
        if q["subface"] != dim:
            continue
        print("  [%s] %s" % (q["polarity"], q["item"]))
        print("        第一轮: %s" % r1.get(qid, "-"))