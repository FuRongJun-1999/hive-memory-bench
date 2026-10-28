# -*- coding: utf-8 -*-
import json
from pathlib import Path
R = Path(r"D:/1_ai/_hb_lab/r58")
cards = {q["qid"]: q for q in json.loads((R / "e2e/questions/题目_一致性探针.json").read_text(encoding="utf-8"))}
j = json.loads((R / "e2e/run/K面作答2.json").read_text(encoding="utf-8"))
r1 = {x["qid"]: x["score"] for x in j["round1"]}
r2 = {x["qid"]: x["score"] for x in j["round2"]}
r3 = {x["qid"]: x["score"] for x in j["round3"]}
print("=== D2-表达直接性 逐题 ===")
for qid, q in cards.items():
    if q["subface"] != "D2-表达直接性":
        continue
    s1 = r1.get(qid, "-"); s2 = r2.get(qid, "-"); s3 = r3.get(qid, "-")
    print("  %s [%s]" % (qid, q["polarity"]))
    print("    题: %s" % q["item"])
    print("    轮1: %s | 轮2: %s | 轮3: %s" % (s1, s2, s3))