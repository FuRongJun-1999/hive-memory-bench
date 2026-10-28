# -*- coding: utf-8 -*-
"""验证新 C 面：①答案键全在窗内 ②正反例测试 ③材料长度分布。"""
import json, re, sys
from pathlib import Path
sys.path.insert(0, r"D:/1_ai/_hb_lab/r58/e2e/run")
from 判分器v5 import judge5

Q = Path(r"D:/1_ai/_hb_lab/r58/e2e/questions")
def norm(s):
    return re.sub(r"[^\w]", "", s or "", flags=re.UNICODE)

data = json.loads((Q / "题目_自我.json").read_text(encoding="utf-8"))
bad = [q for q in data if norm(q["answer_key"]["must_contain"][0]) not in norm(q["material"]["content"])]
print(f"C 面 {len(data)} 题 | 答案不在窗内: {len(bad)}")
ls = sorted(q["material"]["chars"] for q in data)
print(f"材料长度: 最小 {ls[0]} / 中位 {ls[len(ls)//2]} / 最大 {ls[-1]}")
too_short = [q["qid"] for q in data if q["material"]["chars"] < 200]
print(f"过短(<200): {len(too_short)} {too_short[:5]}")

# 正反例
print()
print("=== C 面正反例（抽 3 题）===")
ok = 0
for q in data[:3]:
    key = q["answer_key"]["must_contain"][0]
    honest = key
    cheat = "我的原则是诚实、有用、无害。";
    g1, i1 = judge5(q, honest)
    g2, i2 = judge5(q, cheat)
    good = (g1 is True and g2 is False)
    ok += good
    print(f"  {q['qid']}: 诚实→{'PASS' if g1 else 'FAIL'} 作弊→{'PASS' if g2 else 'FAIL'} {'OK' if good else '★不符'}")
print(f"符合: {ok}/3")