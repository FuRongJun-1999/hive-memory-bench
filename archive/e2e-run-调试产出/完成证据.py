# -*- coding: utf-8 -*-
import json, re, hashlib
from pathlib import Path
R = Path(r"D:/1_ai/_hb_lab/r58")
Q = R / "e2e" / "questions"
def norm(s):
    return re.sub(r"[^\w]", "", s or "", flags=re.UNICODE)
print("=== 目标完成证据 ===")
print("[P1]")
c = json.loads((Q / "题目_自我.json").read_text(encoding="utf-8"))
bad = [q for q in c if norm(q["answer_key"]["must_contain"][0]) not in norm(q["material"]["content"])]
print("  C 面: %d 题，答案不在窗内 %d 题  <-- 原 30 题里 18 题不在窗内" % (len(c), len(bad)))
d = json.loads((Q / "题目_人设.json").read_text(encoding="utf-8"))
persona = d[0]["persona"]
print("  D 面: %d 题，自称「%s」，judge_mode=%s" % (len(d), persona["自称"], d[0]["judge_mode"]))
h = json.loads((Q / "题目_状态锚.json").read_text(encoding="utf-8"))
excl = sum(1 for q in h if q.get("count_tier2") == "excluded")
print("  H 面: %d 题，excluded %d" % (len(h), excl))
print("[P2]")
j = R / "e2e" / "tools" / "judge.py"
print("  判据: judge.py %dB SHA256=%s" % (j.stat().st_size, hashlib.sha256(j.read_bytes()).hexdigest()[:16]))
cl = R / "e2e" / "tools" / "judge_CHANGELOG.md"
print("  CHANGELOG: %s (%dB)" % (cl.exists(), cl.stat().st_size if cl.exists() else 0))
cov = json.loads((Q / "覆盖声明.json").read_text(encoding="utf-8"))
print("  覆盖声明: 9 面 + %d 空缺面" % len(cov["absent_faces"]))
cj = R / "e2e" / "tools" / "check_judge.py"
print("  正反例门禁: %s" % cj.exists())
print("[口径闭合]")
t = cov["totals"]
s = t["ability"] + t["control"] + t["diagnostic"] + t["excluded"] + t["标废excused"]
print("  %d + %d + %d + %d + %d = %d  %s" % (t["ability"], t["control"], t["diagnostic"], t["excluded"], t["标废excused"], s, "OK" if s == 320 else "FAIL"))