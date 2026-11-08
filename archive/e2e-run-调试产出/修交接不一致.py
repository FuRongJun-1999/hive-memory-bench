# -*- coding: utf-8 -*-
"""修交接前的不一致：①覆盖声明 totals ②K 面判据版本标注。"""
import json, hashlib
from pathlib import Path
from collections import Counter, defaultdict
R = Path(r"D:/1_ai/_hb_lab/r58")
Q = R / "e2e" / "questions"
T = R / "e2e" / "tools" / "judge.py"
ver = "v1.4"
sha = hashlib.sha256(T.read_bytes()).hexdigest()[:16]

# 逐题统计
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
tot = sum(s["总"] for s in stat.values())
exc = sum(s["excused"] for s in stat.values())
avail = sum(s["可用"] for s in stat.values())

# ability 面（K 也算能力面，但走配对协议）
ABILITY = ["B2", "C", "D", "E", "F", "G", "I", "EMO", "K"]
ab = sum(stat[f]["可用"] for f in ABILITY if f in stat)
ctrl = stat["L1"]["可用"] if "L1" in stat else 0
diag = 3
excl = sum(stat[f]["可用"] for f in ("B1", "J") if f in stat) + (stat["H"]["可用"] - diag if "H" in stat else 0)

print("总计 %d | excused %d | 可用 %d" % (tot, exc, avail))
print("ability %d | control %d | diagnostic %d | excluded %d" % (ab, ctrl, diag, excl))
print("校验: %d + %d + %d + %d + %d = %d  %s" % (ab, ctrl, diag, excl, exc, ab+ctrl+diag+excl+exc, "OK" if ab+ctrl+diag+excl+exc == tot else "FAIL"))

# 更新覆盖声明
C = Q / "覆盖声明.json"
cov = json.loads(C.read_text(encoding="utf-8"))
cov["judge_version"] = ver
cov["judge_sha256"] = sha
cov["totals"] = {"题卡总数": tot, "标废excused": exc, "可用": avail,
                 "ability": ab, "control": ctrl, "diagnostic": diag, "excluded": excl}
for f, s in stat.items():
    if f in cov["faces"]:
        cov["faces"][f]["总"] = s["总"]
        cov["faces"][f]["可用"] = s["可用"]
        cov["faces"][f]["excused"] = s["excused"]
C.write_text(json.dumps(cov, ensure_ascii=False, indent=2), encoding="utf-8")
print("覆盖声明已更新")

# K 面：判据版本改为「配对协议，不走 judge.py」
P = Q / "题目_一致性探针.json"
k = json.loads(P.read_text(encoding="utf-8"))
n = 0
for q in k:
    if q.get("judge_version") == "v1.5":
        q["judge_version"] = "paired-protocol"
        q["judge_sha256"] = "N/A（配对协议，不走 judge.py）"
        n += 1
P.write_text(json.dumps(k, ensure_ascii=False, indent=1), encoding="utf-8")
print("K 面判据标注已改:", n, "题（v1.5 → paired-protocol）")

# 检查其他面版本一致性
vers = Counter()
for p in Q.glob("题目_*.json"):
    if "残缺诊断" in p.name: continue
    for q in json.loads(p.read_text(encoding="utf-8")):
        vers[q.get("judge_version")] += 1
print("全库判据版本分布:", dict(vers))