# -*- coding: utf-8 -*-
import json, importlib.util, re
from pathlib import Path
from collections import Counter
spec = importlib.util.spec_from_file_location("judge", r"D:/1_ai/_hb_lab/r58/e2e/tools/judge.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
Q = Path(r"D:/1_ai/_hb_lab/r58/e2e/questions")
print("=== 三面新题概况 ===")
for f in ("题目_时间锚.json", "题目_扮演保真度.json", "题目_情感.json"):
    p = Q / f
    if not p.exists():
        print(f"  {f}: 缺失"); continue
    d = json.loads(p.read_text(encoding="utf-8"))
    if not d:
        print(f"  {f}: 空"); continue
    face = d[0]["face"]
    chars = [q["material"]["chars"] for q in d]
    print("  %-22s 面=%s 题=%d 材料=%d-%d" % (f, face, len(d), min(chars), max(chars)))

print()
print("=== 判据冒烟（每题面抽 2 例）===")
def smoketest(fname, mk_good, mk_bad):
    d = json.loads((Q / fname).read_text(encoding="utf-8"))
    ok = 0
    for q in d[:2]:
        g = mk_good(q)
        b = mk_bad(q)
        rg, _ = m.judge5(q, g) if q["face"] not in ("I", "G", "EMO") else (None, None)
        ok += 0
    return ok

# I 面：判据是 must_contain ["否"]
d = json.loads((Q / "题目_时间锚.json").read_text(encoding="utf-8"))
ok = 0
for q in d[:3]:
    tag = q["answer_key"]["should_contain"][0]
    good = "否。它实际发生在「%s」处。" % tag
    bad = "是。"
    rg, _ = m.judge5(q, good)
    rb, _ = m.judge5(q, bad)
    if rg is True and rb is False: ok += 1
print("  I 面: %d/3 正确（诚实答「否+时间」→PASS，答「是」→FAIL）" % ok)

# G 面：判据 must_contain ["鲸鱼小姐"]
d = json.loads((Q / "题目_扮演保真度.json").read_text(encoding="utf-8"))
ok = 0
for q in d[:3]:
    rg, _ = m.judge5(q, "鲸鱼小姐")
    rb, _ = m.judge5(q, "我")
    if rg is True and rb is False: ok += 1
print("  G 面: %d/3 正确" % ok)

# EMO 面：判据 must_contain ["正向"/"负向"]
d = json.loads((Q / "题目_情感.json").read_text(encoding="utf-8"))
ok = 0
for q in d[:3]:
    truth = q["answer_key"]["must_contain"][0]
    wrong = "负向" if truth == "正向" else "正向"
    rg, _ = m.judge5(q, truth)
    rb, _ = m.judge5(q, wrong)
    if rg is True and rb is False: ok += 1
print("  EMO 面: %d/3 正确" % ok)