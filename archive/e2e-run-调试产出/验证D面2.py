# -*- coding: utf-8 -*-
import json, importlib.util
from pathlib import Path
spec = importlib.util.spec_from_file_location("judge", r"D:/1_ai/_hb_lab/r58/e2e/tools/judge.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
Q = Path(r"D:/1_ai/_hb_lab/r58/e2e/questions")
cards = {q["qid"]: q for q in json.loads((Q / "题目_人设.json").read_text(encoding="utf-8"))}

# 确认编号映射
print("=== qid → 特征 映射 ===")
from collections import defaultdict
byfeat = defaultdict(list)
for q in cards.values():
    byfeat[q["feature"]].append(q["qid"])
for f in ["自称", "称呼", "句长", "禁符号", "结尾"]:
    ids = sorted(byfeat[f])
    print(f"  {f:4s}: {ids[0]} … {ids[-1]}（{len(ids)} 题）")

print()
print("=== 按正确特征重测 ===")
GOOD = "旅人走了很远的路，在下听见了。先坐下歇歇脚罢。火还亮着。"
tests = [
  ("自称",   GOOD, True,  "全特征齐（自称在下）"),
  ("自称",   "旅人走了很远的路。火还亮着。", False, "缺「在下」"),
  ("称呼",   GOOD, True,  "含「旅人」"),
  ("称呼",   "在下听见了。先歇歇脚罢。火还亮着。", False, "缺「旅人」"),
  ("句长",   GOOD, True,  "每句≤40"),
  ("句长",   "在下听见旅人说走了很远的路，脚上想必辛苦，此刻先在这堆火边坐下歇一歇罢。火还亮着。", False, "首句超40"),
  ("禁符号", GOOD, True,  "无禁符号"),
  ("禁符号", "旅人来了！在下候着。火还亮着。", False, "含感叹号"),
  ("结尾",   GOOD, True,  "以固定结尾收"),
  ("结尾",   "旅人走了很远的路，在下听见了。", False, "缺固定结尾"),
]
ok = 0
for feat, ans, expect, why in tests:
    qid = sorted(byfeat[feat])[0]
    q = cards[qid]
    got, info = m.judge5(q, ans)
    good = (got == expect)
    ok += good
    print(f"  {feat:4s} {qid} {why:14s} 期望{'PASS' if expect else 'FAIL'} 实得{'PASS' if got else 'FAIL'} {'OK' if good else '★'}")
print(f"\n冒烟 {ok}/{len(tests)}")