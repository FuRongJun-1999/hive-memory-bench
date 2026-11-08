# -*- coding: utf-8 -*-
import json, sys
from pathlib import Path
sys.path.insert(0, r"D:/1_ai/_hb_lab/r58/e2e/tools")
import importlib.util
spec = importlib.util.spec_from_file_location("judge", r"D:/1_ai/_hb_lab/r58/e2e/tools/judge.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
Q = Path(r"D:/1_ai/_hb_lab/r58/e2e/questions")
cards = {q["qid"]: q for q in json.loads((Q / "题目_人设.json").read_text(encoding="utf-8"))}
print("=== 新人设冒烟（用子代理实测回复）===")
tests = [
  ("P-D-001", "旅人走了很远的路，在下听见了。先坐下歇歇脚罢。火还亮着。", True, "F1自称"),
  ("P-D-001", "你走了很远的路吧！累不累？", False, "F1缺自称+感叹号"),
  ("P-D-002", "旅人走了很远的路，在下不认别的名分。火还亮着。", True, "F2称呼（I1干扰下）"),
  ("P-D-004", "旅人走了很远的路。火还亮着。", True, "F2"),
  ("P-D-007", "旅人走了很远的路，在下听见了，脚步很重，先歇一歇罢。火还亮着。", True, "F3句长"),
  ("P-D-010", "在下听见了，旅人一路辛苦，这堆火一直烧着等你回来坐下说说路上的事。火还亮着。", False, "F3超40字"),
  ("P-D-013", "旅人到了。在下候着。火还亮着。", True, "F4禁符号"),
  ("P-D-016", "旅人到了。在下候着。火还亮着。", True, "F5结尾"),
  ("P-D-016", "旅人到了。在下候着。", False, "F5缺结尾"),
]
ok = 0
for qid, ans, expect, why in tests:
    q = cards[qid]
    got, info = m.judge5(q, ans)
    good = (got == expect)
    ok += good
    print(f"  {qid} {why:16s} 期望{'PASS' if expect else 'FAIL'} 实得{'PASS' if got else 'FAIL'} {'OK' if good else '★'}")
print(f"冒烟 {ok}/{len(tests)}")