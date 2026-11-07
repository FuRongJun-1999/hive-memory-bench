#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""五选一判分器 grade_mcq.py

设计目标（对齐 Ornn8 的 grade.py，但判分零噪声）：
  1. 计分：pick == answer，字符串相等，无判官
  2. 分组：有答案题 / 资料不足题（答案=E）分别报
  3. 错误分类：乱说（资料不足选A-D）/ 过度谨慎（有答案选E）/ 选错实质项
  4. 统计检验：对随机基线（1/选项数）做二项检验
  5. 混淆矩阵 + 弃答率 + 格式校验

用法：
  python grade_mcq.py --questions q.json --answers a.jsonl [--out report.json]
      [--baseline auto|0.2] [--verbose]
"""
import argparse, json, math, os, sys
from collections import Counter, defaultdict

def load_questions(path):
    data = json.load(open(path, encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("questions") or data.get("items") or []
    out = {}
    for x in data:
        qid = x.get("id") or x.get("qid")
        ans = x.get("answer") or x.get("ans")
        if not qid or not ans:
            raise ValueError("题目缺 id 或 answer: %s" % str(x)[:80])
        opts = x.get("options") or x.get("opts") or {}
        out[qid] = {"answer": str(ans).strip().upper(), "n_options": len(opts) or 5,
                    "is_unknown": bool(x.get("is_unknown") or x.get("unk"))}
    return out

def load_answers(path):
    rows = {}
    dup = []
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line: continue
        r = json.loads(line)
        qid = r.get("id") or r.get("qid")
        pick = (r.get("pick") or r.get("answer") or "").strip().upper()
        if qid in rows: dup.append(qid)
        rows[qid] = pick[:1] if pick else ""
    return rows, dup

def binom_sf(k, n, p):
    """P(X >= k) under Binomial(n, p) — 单侧检验。"""
    if n == 0: return 1.0
    total = sum(math.comb(n, i) * p**i * (1-p)**(n-i) for i in range(k, n+1))
    return min(1.0, total)

# ── 原榜口径支持（v1.1）─────────────────────────────────────────────
# 设计：分类(content_tags/persona/interval_days)与判分语义照抄 Ornn8，
#       只把「LLM 判官」换成「选项字符串相等」——去掉不可复现的判官干扰。

def load_meta(answer_key_path, exam_inputs_path):
    """从 Ornn8 的 answer-key + exam-inputs 取分类元数据。"""
    meta = {}
    for line in open(exam_inputs_path, encoding="utf-8"):
        line = line.strip()
        if not line: continue
        q = json.loads(line)
        meta[q["id"]] = {"persona": q.get("persona"), "cutoff_turn": q.get("cutoff_turn"),
                         "now": q.get("now")}
    for line in open(answer_key_path, encoding="utf-8"):
        line = line.strip()
        if not line: continue
        k = json.loads(line)
        m = meta.setdefault(k["id"], {})
        m["content_tags"] = k.get("content_tags") or []
        m["interval_days"] = k.get("interval_days")
        m["kind"] = k.get("kind")
        m["rubric"] = k.get("rubric")
    return meta

def summarize_like_ornn(rows, meta):
    """与 Ornn8 grade.py 的 summarize() 同构：persona / content_tags / interval_days。"""
    groups = {"persona": {}, "content_tags": {}, "interval_days": {}}
    for row in rows:
        m = meta.get(row["id"]) or {}
        dims = [("persona", [str(m.get("persona"))]),
                ("content_tags", m.get("content_tags") or ["(未标注)"]),
                ("interval_days", [str(m.get("interval_days"))])]
        for name, values in dims:
            for v in values:
                g = groups[name].setdefault(v, {"total": 0, "passed": 0})
                g["total"] += 1
                g["passed"] += int(row["pass"])
    return groups

def render_groups(groups, top=None):
    L = []
    for dim, label in (("persona", "按人物"), ("content_tags", "按考点"),
                       ("interval_days", "按间隔天数")):
        g = groups.get(dim) or {}
        if not g: continue
        L.append("-- %s（%d 组）--" % (label, len(g)))
        items = sorted(g.items(), key=lambda kv: (-kv[1]["total"], kv[0]))
        for k, v in (items[:top] if top else items):
            rate = v["passed"] / v["total"] if v["total"] else 0
            L.append("  %-16s %d/%d = %.1f%%" % (k, v["passed"], v["total"], 100*rate))
        L.append("")
    return L

def grade(questions, answers, baseline=None, verbose=False):
    valid = [q for q in questions if q in answers]
    missing = [q for q in questions if q not in answers]
    extra = [q for q in answers if q not in questions]

    groups = {"known": {"n": 0, "pass": 0}, "unknown": {"n": 0, "pass": 0}}
    errors = Counter()
    confusion = defaultdict(Counter)
    abstain = 0
    rows = []

    for qid in valid:
        q = questions[qid]; pick = answers[qid]
        g = "unknown" if q["is_unknown"] else "known"
        groups[g]["n"] += 1
        ok = (pick == q["answer"])
        if ok: groups[g]["pass"] += 1
        if pick == "": abstain += 1
        confusion[q["answer"]][pick or "(空)"] += 1
        if not ok:
            if pick == "": errors["abstain"] += 1
            elif q["is_unknown"] and pick in "ABCD": errors["fabricate"] += 1
            elif (not q["is_unknown"]) and pick == "E": errors["over_cautious"] += 1
            else: errors["wrong_substantive"] += 1
        rows.append({"id": qid, "group": g, "pick": pick, "answer": q["answer"], "pass": ok})

    n = len(valid); passed = sum(1 for r in rows if r["pass"])
    p0 = baseline
    if p0 is None:
        nopt = Counter(q["n_options"] for q in questions.values()).most_common(1)[0][0]
        p0 = 1.0 / nopt
    pval = binom_sf(passed, n, p0) if n else 1.0

    report = {
        "questions_total": len(questions), "scored": n,
        "pass": passed, "rate": round(passed / n, 4) if n else 0.0,
        "baseline_random": round(p0, 4),
        "expected_by_chance": round(n * p0, 2),
        "binomial_p_onesided": round(pval, 6),
        "显著高于随机": pval < 0.05,
        "by_group": {k: {"n": v["n"], "pass": v["pass"],
                         "rate": round(v["pass"] / v["n"], 4) if v["n"] else 0.0}
                     for k, v in groups.items()},
        "errors": dict(errors),
        "abstain": abstain,
        "missing_ids": missing[:20], "missing_count": len(missing),
        "extra_ids": extra[:20], "extra_count": len(extra),
        "confusion": {a: dict(c) for a, c in confusion.items()},
    }
    if verbose:
        report["rows"] = rows
    return report

def render(r):
    L = []
    L.append("=" * 58)
    L.append("五选一判分报告")
    L.append("=" * 58)
    L.append("计分口径      : pick == answer（字符串相等，无判官）")
    L.append("题库/已答     : %d / %d" % (r["questions_total"], r["scored"]))
    L.append("通过          : %d (%.1f%%)" % (r["pass"], 100*r["rate"]))
    L.append("随机基线      : %.1f%%（期望 %.1f 题）" % (100*r["baseline_random"], r["expected_by_chance"]))
    L.append("二项检验 p    : %.2e  → %s" % (r["binomial_p_onesided"],
             "显著高于随机" if r["显著高于随机"] else "未能排除随机"))
    L.append("")
    L.append("-- 分组 --")
    for k, label in (("known","有答案题"), ("unknown","资料不足题(答案=E)")):
        g = r["by_group"][k]
        L.append("  %-18s %d/%d = %.1f%%" % (label, g["pass"], g["n"], 100*g["rate"]))
    L.append("")
    L.append("-- 错误分类 --")
    e = r["errors"]
    L.append("  乱说(资料不足选A-D)   : %d" % e.get("fabricate", 0))
    L.append("  过度谨慎(有答案选E)   : %d" % e.get("over_cautious", 0))
    L.append("  选错实质项            : %d" % e.get("wrong_substantive", 0))
    L.append("  弃答(空)              : %d" % e.get("abstain", 0))
    L.append("")
    L.append("-- 混淆(答案→选择) --")
    for a in sorted(r["confusion"]):
        L.append("  正确=%-2s → %s" % (a, r["confusion"][a]))
    if r["missing_count"] or r["extra_count"]:
        L.append("")
        L.append("-- 对齐 --")
        L.append("  缺答 %d 题（未计入分母）: %s" % (r["missing_count"], r["missing_ids"][:5]))
        L.append("  多余 %d 题（不在题库）  : %s" % (r["extra_count"], r["extra_ids"][:5]))
    L.append("=" * 58)
    return "\n".join(L)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--questions", required=True)
    ap.add_argument("--answers", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--baseline", default="auto")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--answer-key", default=None, help="Ornn8 的 answer-key.jsonl（取 content_tags/interval_days）")
    ap.add_argument("--exam-inputs", default=None, help="Ornn8 的 exam-inputs.jsonl（取 persona）")
    ap.add_argument("--groups", action="store_true", help="输出原榜口径分组")
    a = ap.parse_args()
    q = load_questions(a.questions)
    ans, dup = load_answers(a.answers)
    base = None if a.baseline == "auto" else float(a.baseline)
    r = grade(q, ans, baseline=base, verbose=a.verbose)
    if dup: r["duplicate_ids"] = dup[:20]; r["duplicate_count"] = len(dup)
    if a.groups and a.answer_key and a.exam_inputs:
        meta = load_meta(a.answer_key, a.exam_inputs)
        rows_for_group = r.get("rows") or [{"id": k, "pass": (ans[k] == q[k]["answer"])} for k in q if k in ans]
        r["groups"] = summarize_like_ornn(rows_for_group, meta)
    print(render(r))
    if a.groups and r.get("groups"):
        print("\n".join(render_groups(r["groups"])))
    if a.out:
        json.dump(r, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("\nJSON 已写:", a.out)

if __name__ == "__main__":
    main()