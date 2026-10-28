# -*- coding: utf-8 -*-
import json, hashlib
from pathlib import Path
from collections import Counter, defaultdict
R = Path(r"D:/1_ai/_hb_lab/r58")
Q = R / "e2e" / "questions"

print("=== 一、题卡 ===")
stat = defaultdict(lambda: Counter())
tot = 0
for p in sorted(Q.glob("题目_*.json")):
    if "残缺诊断" in p.name:
        continue
    for q in json.loads(p.read_text(encoding="utf-8")):
        f = q.get("face")
        if not f:
            continue
        tot += 1
        stat[f]["总"] += 1
        if q.get("v2_pass") is False:
            stat[f]["excused"] += 1
        else:
            stat[f]["可用"] += 1
for f in sorted(stat):
    s = stat[f]
    print("  %-4s 总%3d | excused %d | 可用 %3d" % (f, s["总"], s["excused"], s["可用"]))
print("  合计 %d" % tot)

print()
print("=== 二、判据 ===")
T = R / "e2e" / "tools" / "judge.py"
print("  judge.py:", T.stat().st_size, "B | SHA:", hashlib.sha256(T.read_bytes()).hexdigest()[:16])
import re
src = T.read_text(encoding="utf-8")
m = re.search(r"JUDGE_VERSION = \"(v[\d.]+)\"", src)
print("  JUDGE_VERSION:", m.group(1) if m else "?")
cl = R / "e2e" / "tools" / "judge_CHANGELOG.md"
print("  CHANGELOG:", cl.exists(), "|", cl.stat().st_size if cl.exists() else 0, "B")
cj = R / "e2e" / "tools" / "check_judge.py"
print("  check_judge.py:", cj.exists())
ca = R / "e2e" / "tools" / "check_all.py"
print("  check_all.py:", ca.exists())

print()
print("=== 三、覆盖声明 ===")
C = Q / "覆盖声明.json"
if C.exists():
    cov = json.loads(C.read_text(encoding="utf-8"))
    print("  面数:", len(cov.get("faces", {})), "| 空缺面:", list(cov.get("absent_faces", {}).keys()))
    print("  totals:", json.dumps(cov.get("totals", {}), ensure_ascii=False))

print()
print("=== 四、已产出的读数文件 ===")
for f in ("实跑记录.md", "第二期实测报告.md", "环境阻塞记录.md"):
    p = R / "e2e" / "run" / f
    print("  %-24s %s (%dB)" % (f, p.exists(), p.stat().st_size if p.exists() else 0))
for f in ("一致性探针协议.md", "README.md"):
    p = Q / f
    print("  %-24s %s (%dB)" % (f, p.exists(), p.stat().st_size if p.exists() else 0))