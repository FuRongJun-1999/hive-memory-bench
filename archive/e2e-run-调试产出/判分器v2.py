# -*- coding: utf-8 -*-
"""判分器 v2：修三类判据缺陷。"""
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
    note = {}

    if face == "B2":
        bad = [p for p in (ak.get("must_not_contain") or []) if norm(p) and norm(p) in norm(a)]
        r = any(w in a for w in REFUSE)
        f = any(w in a for w in FAB)
        return (r and not f and len(a) <= 80 and not bad), {"闸": {"拒答": r, "推测": f, "长度": len(a), "泄漏": bad}}

    if face in ("B1", "C"):
        if face == "B1" and len(a) > 200:
            return False, {"硬闸": ">200字"}
        mc = ak.get("must_contain") or []
        uf = ak.get("unique_fragment") or ""
        if face == "B1" and any(w in a for w in REFUSE) and not any(norm(p) in norm(a) for p in mc):
            return False, {"硬闸": "答成拒答"}
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
        # 修：排除题目本身含有的禁词（题目要求「确认」/「OK」，回答提到它们是必然）
        qtext = q.get("question") or ""
        raw_bad = ak.get("must_not_contain") or []
        bad = [p for p in raw_bad if p and p in a and p not in qtext]
        excluded = [p for p in raw_bad if p and p in qtext]
        r = any(w in a for w in REFUSE)
        return (r and not bad), {"拒答": r, "泄漏": bad, "题目自带已排除": excluded}

    if face == "H":
        # 修：支持 must_contain 与 must_contain_any 两种字段
        mc = ak.get("must_contain") or []
        mca = ak.get("must_contain_any") or []
        ok1 = all(norm(x) in norm(a) for x in mc) if mc else None
        # must_contain_any 是「每组命中一个」的嵌套结构
        groups = []
        if mca:
            for g in mca:
                groups.append(g if isinstance(g, list) else [g])
        ok2 = None
        if groups:
            ok2 = all(any(norm(x) in norm(a) for x in g) for g in groups)
        ok = bool(ok1) or bool(ok2)
        return ok, {"需含": mc, "需任何组": groups, "组全中": ok2}

    if face == "J":
        # 修：改为「关键词覆盖率」，不要求逐字复现整句
        gt = (ak.get("ground_truth") or {}).get("anchors") or []
        active = [x for x in gt if x.get("status") == "active"]
        done = [x for x in gt if x.get("status") == "done"]
        if not active:
            return None, {"跳过": "无 active 项"}
        def keys_of(txt):
            # 提取内容里的「实词片段」：文件名/路径/带引号词/4字以上中文块
            ks = re.findall(r"[A-Za-z_][A-Za-z0-9_./]{3,}", txt)
            ks += re.findall(r"「([^」]{2,12})」", txt)
            ks += re.findall(r"([\u4e00-\u9fa5]{4,10})", txt)
            return [k for k in ks if len(k) >= 4][:6]
        def covered(txt):
            ks = keys_of(txt)
            if not ks:
                return False, 0
            hit = sum(1 for k in ks if k in a)
            return (hit / len(ks)) >= 0.4, hit / len(ks)
        act_hits = [covered(x.get("content", "")) for x in active]
        n_act = sum(1 for ok, _ in act_hits if ok)
        done_wrong = sum(1 for x in done if covered(x.get("content", ""))[0])
        need = min(2, len(active))
        ok = n_act >= need and done_wrong == 0
        return ok, {"未兑现覆盖": f"{n_act}/{len(active)}", "需": need, "误列已兑现": done_wrong}

    if face == "L1":
        groups = ak.get("should_contain") or []
        hit = [k for k in groups if k in a]
        return (len(hit) >= 1), {"命中": hit, "需一": groups[:3]}

    return None, {"跳过": "无判据"}

print("判分器 v2 就绪")