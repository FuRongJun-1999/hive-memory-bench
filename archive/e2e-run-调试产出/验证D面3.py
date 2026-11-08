# -*- coding: utf-8 -*-
import json, importlib.util, re
from pathlib import Path
spec = importlib.util.spec_from_file_location("judge", r"D:/1_ai/_hb_lab/r58/e2e/tools/judge.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
Q = Path(r"D:/1_ai/_hb_lab/r58/e2e/questions")
cards = {q["qid"]: q for q in json.loads((Q / "题目_人设.json").read_text(encoding="utf-8"))}
q = cards["P-D-019"]  # 句长特征

long_sent = "在下听见旅人说今天走了很远很远的山路，脚上想必辛苦得很，此刻先在这堆火边坐下好好歇一歇罢，别急着说话。"
short_ans = "在下听见了。旅人先歇。火还亮着。"

print("长句长度:", len(long_sent), "字")
print("短答分句:", [len(s) for s in re.split(r"[。！？\n]", short_ans) if s.strip()])
print()
for label, ans, expect in [("超40字句", long_sent + "火还亮着。", False), ("短句", short_ans, True)]:
    got, info = m.judge5(q, ans)
    print(f"  {label:8s} 期望{'PASS' if expect else 'FAIL'} 实得{'PASS' if got else 'FAIL'} {'OK' if got == expect else '★'} {info}")