# -*- coding: utf-8 -*-
"""check_all.py —— 第二期测评集门禁（非零退出=不合格）。"""
import json, re, sys
from pathlib import Path
from collections import Counter

R = Path(r"D:/1_ai/_hb_lab/r58")
Q = R / "e2e" / "questions"
REQUIRED = ["qid", "face", "question", "answer_key", "expected", "verdict_rule", "scoring", "difficulty", "source"]
FACES = {"B1", "B2", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L1", "EMO"}
MAX_WIN = 8000

def norm(s):
    return re.sub(r"[^\w]", "", s or "", flags=re.UNICODE)

errs, warns = [], []
seen, face_cnt, total, excluded = {}, Counter(), 0, 0

for p in sorted(Q.glob("题目_*.json")):
    if "残缺诊断" in p.name:
        continue
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        errs.append("%s: 顶层不是数组" % p.name); continue
    for i, q in enumerate(data):
        total += 1
        tag = "%s[%d] %s" % (p.name, i, q.get("qid", "?"))
        miss = [k for k in REQUIRED if k not in q]
        if miss:
            errs.append("%s: 缺字段 %s" % (tag, miss))
        qid = q.get("qid")
        if qid in seen:
            errs.append("%s: qid 重复" % tag)
        seen[qid] = p.name
        face_cnt[q.get("face")] += 1
        if q.get("face") not in FACES:
            errs.append("%s: face 不在白名单" % tag)
        if q.get("v2_pass") is False:
            excluded += 1
        mat = (q.get("material") or {}).get("content") or ""
        if len(mat) > MAX_WIN:
            if q.get("v2_pass") is False:
                warns.append("%s: 材料窗 %d>%d（已标 v2_pass=false，排除计数）" % (tag, len(mat), MAX_WIN))
            else:
                errs.append("%s: 材料窗 %d>%d 且未标 v2_pass=false" % (tag, len(mat), MAX_WIN))
        if q.get("face") in ("H", "J", "C", "B1") and not mat:
            errs.append("%s: 需要材料窗但为空" % tag)
        gt = (q.get("answer_key") or {}).get("ground_truth") or {}
        if q.get("face") == "H":
            anchors = gt.get("anchors") or []
            if not anchors:
                errs.append("%s: 面 H 缺 ground_truth.anchors" % tag)
            elif not any(a.get("status") for a in anchors):
                errs.append("%s: 面 H anchors 缺 status" % tag)
        if q.get("face") == "J":
            sts = set(a.get("status") for a in (gt.get("anchors") or []))
            if "done" not in sts:
                errs.append("%s: 面 J 无 done 项（测不出销账）" % tag)
            if "active" not in sts:
                errs.append("%s: 面 J 无 active 项" % tag)
        mn = (q.get("answer_key") or {}).get("must_not_contain") or []
        for probe in mn:
            if norm(probe) and norm(probe) in norm(mat):
                warns.append("%s: must_not_contain 出现在材料窗" % tag)

print("=== 第二期测评集门禁 ===")
print("题卡总数:", total, "| 已排除(v2_pass=false):", excluded, "| 可用:", total - excluded)
print("按面:", dict(sorted(face_cnt.items(), key=lambda x: str(x[0]))))
print()
print("错误 %d 条" % len(errs))
for e in errs[:20]:
    print("  ✗", e)
if warns:
    print("警告 %d 条（不阻断）" % len(warns))
    for w in warns[:6]:
        print("  ⚠", w)
print()
print("结论:", "不合格" if errs else "通过")
sys.exit(1 if errs else 0)