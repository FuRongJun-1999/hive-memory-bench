# -*- coding: utf-8 -*-
import json
from pathlib import Path
Q = Path(r"D:/1_ai/_hb_lab/r58/e2e/questions")
P = Q / "题目_一致性探针.json"
data = json.loads(P.read_text(encoding="utf-8"))
FIX = {
  "P-K-027": "心里怎么想，我通常就怎么说出口。",
  "P-K-028": "我不爱把想法憋在心里。",
}
n = 0
for q in data:
    if q["qid"] in FIX:
        item = FIX[q["qid"]]
        q["item"] = item
        q["question"] = "【第 %d 题】%s\n请按 1-5 打分（1=完全不同意，5=完全同意）。只回答一个数字。" % (int(q["qid"].split("-")[-1]), item)
        q["fix_note"] = "原表述问的是「说的是否真实」，与原正向题「是否直接说出口」不等价；已改真同义"
        n += 1
P.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
print("修", n, "题")
for q in data:
    if q["subface"] == "D2-表达直接性" and q["polarity"] == "换问法":
        print("  ", q["qid"], q["item"])