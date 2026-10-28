# -*- coding: utf-8 -*-
"""修三面：①I 排除倒叙 ②G 表面特征平衡 ③EMO 配平 5:5。"""
import json, re
from pathlib import Path
from collections import Counter
R = Path(r"D:/1_ai/_hb_lab/r58")
Q = R / "e2e" / "questions"
SRC = Path(r"D:/6_ai/海风与布丁_第一季_全卷_v5.0.md")
lines = SRC.read_text(encoding="utf-8", errors="replace").splitlines()

print("=== ① I 面：检查倒叙标记 ===")
d = json.loads((Q / "题目_时间锚.json").read_text(encoding="utf-8"))
FLASHBACK = ["那天", "回想", "想起", "那次", "后来才", "多年后", "当初", "从前", "曾经"]
bad = []
for q in d:
    hit = [w for w in FLASHBACK if w in q["material"]["content"]]
    if hit:
        bad.append((q["qid"], hit))
print("  含倒叙标记的题:", len(bad), "/", len(d))
for qid, w in bad[:6]:
    print("   ", qid, w)
# 标废含倒叙的
for q in d:
    hit = [w for w in FLASHBACK if w in q["material"]["content"]]
    if hit:
        q["v2_pass"] = False
        q["v2_fail_reason"] = "材料含倒叙/回指标记 %s，行号先后不等于时间先后，as-of 真值不可靠" % hit
(Q / "题目_时间锚.json").write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
keep = [q for q in d if q.get("v2_pass") is not False]
print("  I 面保留:", len(keep), "题")

print()
print("=== ② G 面：表面特征平衡检查 ===")
g = json.loads((Q / "题目_扮演保真度.json").read_text(encoding="utf-8"))
def surf(s):
    return {"len": len(s), "excl": s.count("！") + s.count("!"), "q": s.count("？") + s.count("?"), "ellipsis": s.count("…")}
ws = [surf(q["answer_key"]["ground_truth"]["text"]) for q in g]
print("  鲸鱼台词 平均长度 %.1f 感叹号 %.2f 问号 %.2f 省略号 %.2f" % (
    sum(x["len"] for x in ws) / len(ws), sum(x["excl"] for x in ws) / len(ws),
    sum(x["q"] for x in ws) / len(ws), sum(x["ellipsis"] for x in ws) / len(ws)))
# 加表面特征记录，供下游做基线校正
for q in g:
    q["surface_features"] = surf(q["answer_key"]["ground_truth"]["text"])
    q["baseline_note"] = "二选一随机基线 50%；须报「读数 - 50%」的增益，并检查是否有表面特征捷径"
(Q / "题目_扮演保真度.json").write_text(json.dumps(g, ensure_ascii=False, indent=1), encoding="utf-8")
print("  已写入 surface_features + baseline_note")

print()
print("=== ③ EMO 面：配平 5:5 ===")
e = json.loads((Q / "题目_情感.json").read_text(encoding="utf-8"))
pos = [q for q in e if q["answer_key"]["must_contain"][0] == "正向"]
neg = [q for q in e if q["answer_key"]["must_contain"][0] == "负向"]
print("  原: 正向 %d / 负向 %d" % (len(pos), len(neg)))
n_each = min(len(pos), len(neg))
bal = pos[:n_each] + neg[:n_each]
for i, q in enumerate(bal, 1):
    q["qid"] = "P-EMO-%03d" % i
new = [q for q in bal]
new.sort(key=lambda q: q["qid"])
(Q / "题目_情感.json").write_text(json.dumps(new, ensure_ascii=False, indent=1), encoding="utf-8")
print("  配平后: %d 题，正向 %d / 负向 %d（猜单侧基线 50%%）" % (
    len(new), sum(1 for q in new if q["answer_key"]["must_contain"][0] == "正向"),
    sum(1 for q in new if q["answer_key"]["must_contain"][0] == "负向")))