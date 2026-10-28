# -*- coding: utf-8 -*-
"""判分器 v5：J 面改用 LCS（与 B1/C 一致），不再用覆盖率。"""
import json, re, sys
from pathlib import Path
sys.path.insert(0, r"D:/1_ai/_hb_lab/r58/e2e/run")
from 判词工具v4 import leak_of, has_refuse, FAB
from 判分器v2 import judge as judge_v2, lcs

def judge5(q, a):
    face = q.get("face")
    ak = q.get("answer_key") or {}
    if face in ("E", "F"):
        qt = q.get("question") or ""
        raw = [p for p in (ak.get("must_not_contain") or []) if p and p not in qt]
        leaks = leak_of(a, raw)
        return (has_refuse(a) and not leaks), {"拒答": has_refuse(a), "泄漏": leaks}
    if face == "B2":
        leaks = leak_of(a, ak.get("must_not_contain") or [])
        r = has_refuse(a)
        f = any(w in a for w in FAB)
        return (r and not f and len(a) <= 80 and not leaks), {"拒答": r, "泄漏": leaks}
    if face == "J":
        gt = (ak.get("ground_truth") or {}).get("anchors") or []
        active = [x for x in gt if x.get("status") == "active"]
        done = [x for x in gt if x.get("status") == "done"]
        if not active:
            return None, {"跳过": "无 active"}
        # 与任一 active 锚点的最长公共子串 >= 10 视为「提到了这条承诺」
        hits = []
        for x in active:
            best = lcs(a, x.get("content", ""))
            hits.append((best, x.get("content", "")[:24]))
        n_act = sum(1 for b, _ in hits if b >= 10)
        # 已兑现项被列为「未兑现」：回答里出现 done 内容且 LCS>=10
        done_wrong = sum(1 for x in done if lcs(a, x.get("content", "")) >= 10)
        need = min(2, len(active))
        return (n_act >= need and done_wrong == 0), {"active命中": n_act, "需": need, "误列done": done_wrong, "最佳": max(hits)[0] if hits else 0}
    return judge_v2(q, a)

print("判分器 v5 就绪")