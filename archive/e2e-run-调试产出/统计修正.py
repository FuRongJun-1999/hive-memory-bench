# -*- coding: utf-8 -*-
import json
from pathlib import Path
from collections import Counter, defaultdict
R = Path(r"D:/1_ai/_hb_lab/r58")
Q = R / "e2e/questions"

# 按每题自己的 face 统计
stat = defaultdict(lambda: Counter())
for p in Q.glob("题目_*.json"):
    if "残缺诊断" in p.name:
        continue
    for q in json.loads(p.read_text(encoding="utf-8")):
        f = q.get("face")
        if not f:
            continue
        stat[f]["总"] += 1
        if q.get("v2_pass") is False:
            stat[f]["excused"] += 1
        else:
            stat[f]["可用"] += 1

print("=== 按面（逐题统计）===")
for f in sorted(stat):
    s = stat[f]
    print("  %-4s 总%3d | excused %d | 可用 %3d" % (f, s["总"], s["excused"], s["可用"]))
tot = sum(s["总"] for s in stat.values())
exc = sum(s["excused"] for s in stat.values())
avail = sum(s["可用"] for s in stat.values())
print("  合计: 总%d | excused %d | 可用 %d" % (tot, exc, avail))

# ability 面
ABILITY = ["B2", "C", "D", "E", "F", "I", "G", "EMO"]
ab = sum(stat[f]["可用"] for f in ABILITY if f in stat)
ctrl = stat["L1"]["可用"] if "L1" in stat else 0
diag = sum(1 for p in [Q/"题目_状态锚.json"] for q in json.loads(p.read_text(encoding="utf-8")) if q.get("validity") == "true-state-anchor")
excl = sum(stat[f]["可用"] for f in ("B1", "J") if f in stat) + (stat["H"]["可用"] - diag if "H" in stat else 0)
print()
print("ability = %d" % ab)
print("control = %d (L1)" % ctrl)
print("diagnostic = %d (H 真状态锚)" % diag)
print("excluded = %d" % excl)
print("excused = %d" % exc)
sum_all = ab + ctrl + diag + excl + exc
print("校验: %d + %d + %d + %d + %d = %d  %s" % (ab, ctrl, diag, excl, exc, sum_all, "OK" if sum_all == tot else "FAIL"))

# 写回覆盖声明
C = Q / "覆盖声明.json"
cov = json.loads(C.read_text(encoding="utf-8"))
cov["totals"] = {"题卡总数": tot, "标废excused": exc, "可用": avail,
                 "ability": ab, "control": ctrl, "diagnostic": diag, "excluded": excl}
for f, s in stat.items():
    if f in cov["faces"]:
        cov["faces"][f]["总"] = s["总"]
        cov["faces"][f]["可用"] = s["可用"]
C.write_text(json.dumps(cov, ensure_ascii=False, indent=2), encoding="utf-8")
print()
print("覆盖声明已更新")