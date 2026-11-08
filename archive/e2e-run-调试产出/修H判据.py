# -*- coding: utf-8 -*-
"""修 H 判据：must_contain_any 由「所有组全中」改为「任一组命中」。"""
from pathlib import Path
T = Path(r"D:/1_ai/_hb_lab/r58/e2e/tools/judge.py")
src = T.read_text(encoding="utf-8")
old = "        ok2 = all(any(norm(x) in norm(a) for x in g) for g in groups)"
new = ("        # 修：任一组命中即算对（旧版要求所有组全中，过严——只答\"白墙蓝顶的房子\"已足够）" + chr(10) +
       "        ok2 = any(all(norm(x) in norm(a) for x in g) if len(g) == 1 else any(norm(x) in norm(a) for x in g) for g in groups)")
if old in src:
    src = src.replace(old, new)
    print("已修 H 判据：all → any（任一组命中）")
else:
    # 尝试匹配实际行
    import re
    m = re.search(r"\s*ok2 = .*", src)
    print("未匹配，实际行:", m.group(0)[:120] if m else "无")
    if m:
        src = src.replace(m.group(0), new)
        print("已按正则替换")
T.write_text(src, encoding="utf-8")

# 重验
import importlib.util, hashlib, json
spec = importlib.util.spec_from_file_location("judge", str(T))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
print("SHA256:", hashlib.sha256(T.read_bytes()).hexdigest()[:16])

Q = Path(r"D:/1_ai/_hb_lab/r58/e2e/questions")
cards = {}
for p in Q.glob("题目_*.json"):
    if "残缺诊断" in p.name:
        continue
    for q in json.loads(p.read_text(encoding="utf-8")):
        cards[q["qid"]] = q
print()
tests = [
  ("P-H-S01", "她住在小镇边缘两层白墙蓝顶的房子。", True, "只答房子+白墙"),
  ("P-H-S01", "她现在住在小镇边缘海崖下的两层白墙蓝顶房子，有院子与秋千。", True, "完整答案"),
  ("P-H-S01", "她还住在帐篷里。", False, "旧居所"),
  ("P-H-S02", "搬家之前她住在浅滩上的帐篷里。", True, "帐篷"),
  ("P-H-S03", "否，昨天那里还只有一片礁石。", True, "否定"),
]
ok = 0
for qid, ans, expect, why in tests:
    q = cards[qid]
    got, info = m.judge5(q, ans)
    good = (got == expect)
    ok += good
    print(f"  {qid:10s} {why:14s} 期望{'PASS' if expect else 'FAIL'} 实得{'PASS' if got else 'FAIL'} {'OK' if good else '★'}")
print(f"H 面测试 {ok}/{len(tests)}")