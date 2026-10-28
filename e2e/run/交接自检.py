# -*- coding: utf-8 -*-
"""交接文档自检：逐条核对文档里写死的数字。"""
import json, hashlib, re
from pathlib import Path
from collections import Counter, defaultdict
R = Path(r"D:/1_ai/_hb_lab/r58")
Q = R / "e2e" / "questions"
T = R / "e2e" / "tools" / "judge.py"

ok = []
def chk(name, got, want):
    good = str(got) == str(want)
    ok.append(good)
    print("  %s %-34s 文档=%-10s 实际=%s" % ("OK" if good else "X ", name, want, got))

print("=== 交接文档自检 ===")
# 1 题数
stat = defaultdict(lambda: Counter())
for p in Q.glob("题目_*.json"):
    if "残缺诊断" in p.name: continue
    for q in json.loads(p.read_text(encoding="utf-8")):
        f = q.get("face")
        if not f: continue
        stat[f]["总"] += 1
        if q.get("v2_pass") is False: stat[f]["excused"] += 1
        else: stat[f]["可用"] += 1
tot = sum(s["总"] for s in stat.values())
chk("题卡总数", tot, 470)
chk("标废", sum(s["excused"] for s in stat.values()), 9)
chk("面数", len(stat), 13)

# 2 判据
sha = hashlib.sha256(T.read_bytes()).hexdigest()[:16]
m = re.search(r"JUDGE_VERSION = \"(v[\d.]+)\"", T.read_text(encoding="utf-8"))
chk("judge 版本", m.group(1) if m else "?", "v1.4")
chk("judge SHA16", sha, "fc6908c63ae855f8")

# 3 各面题数
for f, want in [("B1",79),("B2",87),("C",39),("D",45),("E",10),("F",10),("G",20),
                ("H",18),("I",11),("J",17),("K",108),("L1",7),("EMO",10)]:
    chk("面 %s 可用" % f, stat[f]["可用"], want)

# 4 口径
ABILITY = ["B2","C","D","E","F","G","I","EMO","K"]
ab = sum(stat[f]["可用"] for f in ABILITY)
ctrl = stat["L1"]["可用"]
diag = 3
excl = stat["B1"]["可用"] + stat["J"]["可用"] + (stat["H"]["可用"] - diag)
exc = sum(s["excused"] for s in stat.values())
chk("ability", ab, 340)
chk("control", ctrl, 7)
chk("diagnostic", diag, 3)
chk("excluded", excl, 111)
chk("口径闭合", ab+ctrl+diag+excl+exc, tot)

# 5 覆盖声明与实测一致
cov = json.loads((Q / "覆盖声明.json").read_text(encoding="utf-8"))
chk("覆盖声明 totals.题卡总数", cov["totals"]["题卡总数"], 470)
chk("覆盖声明 ability", cov["totals"]["ability"], 340)

# 6 判据版本分布
vers = Counter()
for p in Q.glob("题目_*.json"):
    if "残缺诊断" in p.name: continue
    for q in json.loads(p.read_text(encoding="utf-8")):
        vers[q.get("judge_version")] += 1
chk("v1.4 题数", vers.get("v1.4", 0), 362)
chk("paired-protocol 题数", vers.get("paired-protocol", 0), 108)

# 7 文件存在
for fn in ["docs/第二期测评集_交接文档_v1.0.md", "e2e/questions/覆盖声明.json",
           "e2e/questions/一致性探针协议.md", "e2e/tools/judge.py",
           "e2e/tools/judge_CHANGELOG.md", "e2e/tools/check_all.py", "e2e/tools/check_judge.py",
           "e2e/run/对照评估2.py", "e2e/run/第二期实测报告.md"]:
    chk("文件 " + fn.split("/")[-1], (R / fn).exists(), True)

print()
print("自检: %d/%d 通过" % (sum(ok), len(ok)))