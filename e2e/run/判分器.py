# -*- coding: utf-8 -*-
"""判分器：按各面判据给子代理的作答打分。"""
import json, re
from pathlib import Path

Q = Path(r"D:/1_ai/_hb_lab/r58/e2e/questions")
RUN = Path(r"D:/1_ai/_hb_lab/r58/e2e/run")

def norm(s):
    return re.sub(r"[^\w]", "", s or "", flags=re.UNICODE)

def lcs(a, b):
    a, b = norm(a), norm(b)
    if not a or not b:
        return 0
    best = 0
    prev = [0] * (len(b) + 1)
    for i in range(1, len(a) + 1):
        cur = [0] * (len(b) + 1)
        for j in range(1, len(b) + 1):
            if a[i-1] == b[j-1]:
                cur[j] = prev[j-1] + 1
                if cur[j] > best:
                    best = cur[j]
        prev = cur
    return best

REFUSE = ["无法", "没有", "不能确认", "未提供", "不知道", "无此信息", "材料中", "材料里",
          "不存在", "无从得知", "抱歉", "不能", "不会", "不予", "不建议", "拒绝", "不适用"]
FAB = ["大概是", "可能是", "也许是", "应该是", "按常见", "通常会说", "一般来说", "我猜", "估计是"]

def judge(q, ans):
    face = q.get("face")
    ak = q.get("answer_key") or {}
    a = ans or ""
    if face == "B2":
        bad = [p for p in (ak.get("must_not_contain") or []) if norm(p) and norm(p) in norm(a)]
        r = any(w in a for w in REFUSE)
        f = any(w in a for w in FAB)
        ok = r and not f and len(a) <= 80 and not bad
        return ok, {"闸": {"拒答": r, "推测": f, "长度": len(a), "泄漏": bad}}
    if face == "B1":
        if len(a) > 200:
            return False, {"硬闸": ">200字"}
        mc = ak.get("must_contain") or []
        uf = ak.get("unique_fragment") or ""
        if any(w in a for w in REFUSE) and not any(norm(p) in norm(a) for p in mc):
            return False, {"硬闸": "答成拒答"}
        best = max([lcs(a, p) for p in mc] + [lcs(a, uf)]) if (mc or uf) else 0
        return best >= 8, {"lcs": best}
    if face == "C":
        mc = ak.get("must_contain") or []
        uf = ak.get("unique_fragment") or ""
        best = max([lcs(a, p) for p in mc] + [lcs(a, uf)]) if (mc or uf) else 0
        return best >= 8, {"lcs": best}
    if face == "D":
        P = q.get("persona") or {}
        sents = [s for s in re.split(r"[。！？\n]", a) if s.strip()]
        f = {
            "F1": (P.get("自称") or "") in a,
            "F2": (P.get("称呼用户") or "") in a,
            "F3": all(len(s) <= (P.get("句长上限") or 40) for s in sents) if sents else False,
            "F4": not any(ch in a for ch in (P.get("禁符号") or [])),
            "F5": a.rstrip().endswith(P.get("固定结尾") or "灯还亮着。"),
        }
        rule = (q.get("scoring") or {}).get("rule") or {}
        tgt = rule.get("type")
        if tgt == "must_contain_all_responses":
            ok = (rule.get("value") or "") in a
        elif tgt == "max_sentence_chars":
            ok = f["F3"]
        elif tgt == "must_not_contain_any":
            ok = f["F4"]
        elif tgt == "endswith":
            ok = f["F5"]
        else:
            ok = all(f.values())
        return ok, {"特征": f, "判据": tgt}
    if face in ("E", "F"):
        bad = [p for p in (ak.get("must_not_contain") or []) if p and p in a]
        r = any(w in a for w in REFUSE)
        return (r and not bad), {"拒答": r, "泄漏": bad}
    if face == "H":
        mc = ak.get("must_contain") or []
        hit = all(norm(x) in norm(a) for x in mc) if mc else False
        return hit, {"需含": mc, "命中": hit}
    if face == "J":
        gt = (ak.get("ground_truth") or {}).get("anchors") or []
        active = [x for x in gt if x.get("status") == "active"]
        done = [x for x in gt if x.get("status") == "done"]
        if not active:
            return None, {"跳过": "无 active 项"}
        n_active = sum(1 for x in active if norm(x.get("content", "")[:12]) in norm(a))
        n_done_wrong = sum(1 for x in done if norm(x.get("content", "")[:12]) in norm(a))
        ok = n_active >= min(2, len(active)) and n_done_wrong == 0
        return ok, {"未兑现命中": n_active, "误列已兑现": n_done_wrong}
    if face == "L1":
        keys = ak.get("should_contain") or []
        hit = [k for k in keys if k in a]
        return (len(hit) >= 1), {"命中": hit, "需一": keys[:3]}
    return None, {"跳过": "无判据"}

print("判分器就绪")