#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""判官协议机械件：锚自证 + 判官一致率 + 硬闸（协议定义见 `docs/判分可靠性_v1.0.md`）。

为什么有它（外部评审 issue #4）：这条协议是本库最主要的差异化卖点，此前只存在于
文档与人工流程里——外部无法复跑、"任一判官不合格 ⇒ 整批作废"只是人工承诺。
本件把协议落成可跑代码：输入＝锚集 + 判官输出（JSON），输出＝逐判官锚自证、
判官间一致率、`可报值/只报序/不可测` 判定；并把「不合格 ⇒ 整批作废」做成**硬闸**
（不合格时拒绝产出读数记录并非零退出）。

输入 JSON（两种模式）：
  ① 明细模式（首选，逐题明细）：
     {"round": "毛选轮", "stratum": "均衡样本",
      "anchors": [{"qid": "pos01", "expected": "correct"}, ...],
      "judges":  {"J1@t0": {"pos01": "correct", ...}, ...}}
  ② 汇总模式（回填已归档的聚合读数——逐题明细未存档时的合法路径，`provenance` 必填；
     `panel_size` 声明该条目背后的判官人数，默认 1）：
     {"round": "秦吏轮", "stratum": "均衡样本", "provenance": "docs/多语料复现_v1.0.md:57",
      "panel_size": 3,
      "summary": {"positives": 9, "negatives": 9,
                  "judges": {"判官批": {"pos_hit": 9, "neg_miss": 0}}}}

协议判据（默认值，命令行可调）：
  · 锚自证：判官在锚上的正确率 − 多数类基线 ≥ 15pp **且锚覆盖率 ≥ 90%** ⇒ 合格
    （`判分可靠性_v1.0.md` §3；覆盖率门与容差见 issue #14）；
  · 一致率：平均同分 ≥ 0.8 或 平均 kappa ≥ 0.6 ⇒ `可报值`；≥ 0.5 ⇒ `只报序`；否则 `不可测`；
  · 一致率必须连**样本档位**一起报（同一判官批 kappa 0.939↔0.552 的实测教训）——
    输出记录强制带 `stratum` 字段。
  · 汇总模式（issue #13）：`agreement_recorded` 必须是数值型 `mean_identical`／`mean_kappa`
    （区间取 `mean_identical_lower` 作下限），并走同一套 `classify_agreement`；
    未登记一致率时报告模式**至多「只报序」**，不得默认「可报值」。
    `panel_size` 只能由逐判官汇总数推出；`pos_hit`／`neg_miss` 越界即拒绝（exit 2）。
硬闸策略：
  · void-all（默认）：任一判官不合格 ⇒ 整批作废——**不写入读数记录、exit 1**；
  · keep-qualified：剔除不合格判官后继续，但合格判官 < 2 ⇒ 仍作废。
自检（含定点变异用例，证明硬闸不是恒真断言）：
  python judge_audit.py selftest
用法：
  python judge_audit.py check systems/judge_audit/毛选轮.json --out systems/judge_audit.json
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent

LABELS = ("correct", "incorrect")
DELTA_EPS = 1e-9            # 门槛比较容差（issue #14：19/20−16/20 = 0.1499999999999999）
COVERAGE_MIN = 0.9          # 锚覆盖率下限（issue #14：判官不能只答最有把握的几个锚）


class InputError(Exception):
    """输入契约被违反（issue #13）：越界读数、无凭据的 panel_size 等。"""


def _norm(v) -> str:
    return str(v).strip().lower()


# ------------------------------------------------------------------ 锚自证

def anchor_baseline(expected: list) -> float:
    """多数类基线：锚集里占比最大的那一档的频率。"""
    if not expected:
        return 0.0
    return max(Counter(expected).values()) / len(expected)


def evaluate_anchors(anchors: list, judges: dict, verdict_key: str = "verdict") -> dict:
    """逐判官锚自证：正确率 / 基线 / 差值 / 覆盖率。

    ★ 覆盖率的**分母**是全部锚（issue #14）：漏答的锚记进 `missing`，
    由 `run_job` 的覆盖率门决定是否合格——否则「判官只答最有把握的几个锚」
    就是让判官自己挑题（实测两名判官各答 40 锚中的 2 个仍「✅ 100%（覆盖 5%）」）。
    """
    exp = {a["qid"]: _norm(a["expected"]) for a in anchors}
    base = anchor_baseline(list(exp.values()))
    out = {}
    for name, verdicts in judges.items():
        n = hit = 0
        missing = []
        for qid, e in exp.items():
            v = verdicts.get(qid)
            if v is None:
                missing.append(qid)
                continue
            n += 1
            if _norm(v) == e:
                hit += 1
        acc = hit / n if n else 0.0
        out[name] = {"n": n, "coverage": (n / len(exp)) if exp else 0.0,
                     "missing": missing,
                     "accuracy": acc, "baseline": base, "delta": acc - base}
    return out


# ------------------------------------------------------------------ 一致率

def cohen_kappa(a: list, b: list) -> float:
    """两列名义标签的 Cohen's kappa（标准公式）。"""
    n = len(a)
    if n == 0:
        return 0.0
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum((ca[k] / n) * (cb[k] / n) for k in set(ca) | set(cb))
    if pe >= 1.0:
        return 1.0
    return (po - pe) / (1 - pe)


def evaluate_agreement(anchors: list, judges: dict) -> dict:
    """逐对判官：同分率 + kappa；返回 {pairs, mean_identical, mean_kappa}。"""
    names = list(judges)
    pairs = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            xs, ys = [], []
            for a in anchors:
                q = a["qid"]
                va, vb = judges[names[i]].get(q), judges[names[j]].get(q)
                if va is not None and vb is not None:
                    xs.append(_norm(va))
                    ys.append(_norm(vb))
            if not xs:
                continue
            pairs.append({"pair": [names[i], names[j]], "n": len(xs),
                          "identical": sum(1 for x, y in zip(xs, ys) if x == y) / len(xs),
                          "kappa": cohen_kappa(xs, ys)})
    if not pairs:
        return {"pairs": [], "mean_identical": None, "mean_kappa": None}
    return {"pairs": pairs,
            "mean_identical": sum(p["identical"] for p in pairs) / len(pairs),
            "mean_kappa": sum(p["kappa"] for p in pairs) / len(pairs)}


def classify_agreement(ag: dict, same_min: float, kappa_min: float, same_floor: float) -> str:
    """一致率 → 报告模式。

    ★ 两路都可单独成立（issue #13）：汇总模式回填的历史值可能只登记了同分率、
      也可能只登记了 kappa。此前只认同分率，`mean_identical` 缺失即「不可测」，
      于是「只登记 kappa 0.9」这种明显够格的读数反而被判不可测。
    """
    mi, mk = ag.get("mean_identical"), ag.get("mean_kappa")
    if mi is None and mk is None:
        return "不可测"
    if (mi is not None and mi >= same_min) or (mk is not None and mk >= kappa_min):
        return "可报值"
    if mi is not None and mi >= same_floor:
        return "只报序"
    if mi is None:
        return "只报序"          # 只有 kappa、未达 kappa_min：无同分下限可判 ⇒ 至多报序
    return "不可测"


# ------------------------------------------------------------------ 主流程

def build_job_from_summary(job: dict) -> dict:
    """汇总模式 → 与明细模式同构的中间结构。

    ★ 输入契约（issue #13）：`pos_hit` / `neg_miss` 必须在
      `0 ≤ x ≤ positives/negatives` 之内——此前不校验，于是 `pos_hit=30` 而
      `positives=9` 能算出「正确率 216.7%」并判「可报值」。
    """
    s = job["summary"]
    pos, neg = int(s["positives"]), int(s["negatives"])
    total = pos + neg
    base = max(pos, neg) / total if total else 0.0
    judges = {}
    for name, st in s["judges"].items():
        ph, nm = int(st["pos_hit"]), int(st.get("neg_miss", 0))
        if not (0 <= ph <= pos):
            raise InputError(f"{name}: pos_hit={ph} 越界（应在 0..{pos}）")
        if not (0 <= nm <= neg):
            raise InputError(f"{name}: neg_miss={nm} 越界（应在 0..{neg}）")
        acc = (ph + (neg - nm)) / total
        judges[name] = {"n": total, "coverage": 1.0, "missing": [],
                        "accuracy": acc, "baseline": base, "delta": acc - base}
    return {"anchors_shape": {"positives": pos, "negatives": neg, "baseline": base},
            "judges": judges}


def run_job(job: dict, *, min_delta: float, policy: str,
            same_min: float, kappa_min: float, same_floor: float,
            coverage_min: float = COVERAGE_MIN) -> dict:
    """执行一次审计。返回记录 dict；`status` ∈ pass|void。

    ★ 汇总模式与明细模式对**同样的一致率**必须给出同样的报告模式（issue #13）：
      此前汇总模式 `ag = None`，直接 `setdefault("report_mode", "可报值")`——
      登记一致率 30% 也判「可报值」，`classify_agreement` 从不被调用。
    """
    rec = {"round": job.get("round"), "stratum": job.get("stratum"),
           "provenance": job.get("provenance"),
           "policy": policy, "min_delta": min_delta, "coverage_min": coverage_min,
           "panel_size": int(job.get("panel_size", 1)),
           "thresholds": {"same_min": same_min, "kappa_min": kappa_min,
                          "same_floor": same_floor}}

    if "summary" in job:                                  # 汇总模式：无逐题明细，一致率引用已归档值
        mid = build_job_from_summary(job)                 # 越界读数在此被拒（InputError）
        rec["anchors"] = mid["anchors_shape"]
        rec["judges"] = mid["judges"]
        # ★ panel_size 只能由判官数推出（issue #13）：此前它直接取输入，单个「判官批」
        #   写 panel_size: 2 即满足「合格判官 ≥ 2」，等于自报人数。要声明多判官，
        #   必须给出**逐判官**汇总。
        declared = int(job.get("panel_size", 1) or 1)
        if declared > len(rec["judges"]):
            raise InputError(
                f"panel_size={declared} 与逐判官汇总数 {len(rec['judges'])} 不符——"
                f"汇总模式要声明多判官必须给出逐判官汇总（issue #13）")
        rec["panel_size"] = len(rec["judges"])
        arec = job.get("agreement_recorded") or {}
        mi, mk = arec.get("mean_identical"), arec.get("mean_kappa")
        if mi is None and mk is None:
            ag = None
            rec["agreement"] = {"source": "not_recorded"}
        else:
            # ★ 区间按**下限**取值（issue #13）：登记「60–90%」时按 0.60 判。
            lo = arec.get("mean_identical_lower")
            mi = float(lo) if lo is not None else (float(mi) if mi is not None else None)
            ag = {"pairs": [], "mean_identical": mi,
                  "mean_kappa": float(mk) if mk is not None else None}
            rec["agreement"] = {"source": "recorded", **arec}
            if lo is not None:
                rec["agreement"]["mean_identical_lower"] = float(lo)
    else:                                                 # 明细模式
        anchors, judges = job["anchors"], job["judges"]
        rec["anchors"] = {"n": len(anchors),
                          "baseline": anchor_baseline([_norm(a["expected"]) for a in anchors])}
        rec["judges"] = evaluate_anchors(anchors, judges)
        ag = evaluate_agreement(anchors, judges)

    # ★ 合格判据 = 锚自证达门槛 **且** 覆盖率达标（issue #14）：
    #   此前覆盖率只记录、不设门，判官只答最有把握的几个锚就能过闸。
    #   门槛比较加容差：19/20 − 16/20 在浮点下是 0.1499999999999999（恰在 15pp 上却被判不合格）。
    for name, st in rec["judges"].items():
        st["delta_ok"] = st["delta"] >= min_delta - DELTA_EPS
        st["coverage_ok"] = st["coverage"] >= coverage_min
        st["qualified"] = st["delta_ok"] and st["coverage_ok"]
    unqualified = sorted(n for n, st in rec["judges"].items() if not st["qualified"])

    # —— 硬闸 ——
    if unqualified and policy == "void-all":
        why = []
        for n in unqualified:
            st = rec["judges"][n]
            why.append(n + ("（覆盖不足）" if not st["coverage_ok"] else "（锚自证不足）"))
        rec.update(status="void", report_mode="不可测",
                   reason=f"判官不合格：{why}（整批作废）")
        return rec
    survivors = {n: st for n, st in rec["judges"].items() if st["qualified"]}
    panel = rec["panel_size"]
    if len(survivors) * panel < 2:
        rec.update(status="void", report_mode="不可测",
                   reason=f"合格判官（含 panel_size 折算）{len(survivors)}×{panel} < 2（作废）")
        return rec
    if unqualified:
        rec["voided_judges"] = unqualified

    if ag is not None:
        mode = classify_agreement(ag, same_min, kappa_min, same_floor)
        if rec.get("agreement", {}).get("source") != "recorded":
            rec["agreement"] = {"source": "computed", **ag}
        rec["report_mode"] = mode
        if mode == "不可测":
            rec.update(status="void", reason="判官间一致率不可测（低于报序下限）")
            return rec
    else:
        # ★ 无一致率 ⇒ **不得**默认「可报值」（issue #13）：一致率是「可报值」的必要条件，
        #   缺它就等于这道门不存在。至多「只报序」。
        rec["report_mode"] = "只报序"
        rec["note"] = "未登记一致率 ⇒ 至多只报序（issue #13）"
    rec["status"] = "pass"
    return rec


def _print_record(rec: dict) -> None:
    print(f"—— 轮次：{rec['round']}｜样本档位：{rec['stratum']}")
    print(f"   锚集基线：{rec['anchors'].get('baseline', 0):.1%}"
          + (f"（正 {rec['anchors']['positives']}／负 {rec['anchors']['negatives']}）"
             if "positives" in rec["anchors"] else f"（n={rec['anchors'].get('n')}）"))
    for name, st in rec["judges"].items():
        mark = "✅" if st["qualified"] else "❌"
        miss = st.get("missing") or []
        print(f"   {mark} {name:<18} 正确率 {st['accuracy']:6.1%} − 基线 {st['baseline']:.1%}"
              f" = {st['delta']:+.1%}（覆盖 {st['coverage']:.0%}"
              + (f"，漏答 {len(miss)} 锚" if miss else "") + "）")
    ag = rec.get("agreement") or {}
    if ag.get("source") == "computed":
        print(f"   一致率：同分 {ag['mean_identical']:.1%}／kappa {ag['mean_kappa']:.3f}"
              f"  ⇒ {rec['report_mode']}")
    elif ag.get("source") == "recorded":
        print(f"   一致率（已归档回填）：{ag.get('note') or ag}")
    if rec["status"] == "void":
        print(f"   ⛔ 整批作废：{rec['reason']}")
    else:
        print(f"   ⇒ 状态 pass｜报告模式 {rec['report_mode']}")


def cmd_check(args) -> int:
    job = json.loads(Path(args.input).read_text(encoding="utf-8"))
    try:
        rec = run_job(job, min_delta=args.min_delta, policy=args.policy,
                      same_min=args.same_min, kappa_min=args.kappa_min,
                      same_floor=args.same_floor, coverage_min=args.coverage_min)
    except InputError as e:
        print(f"⛔ 输入不合契约（exit 2）：{e}")
        return 2
    _print_record(rec)
    if rec["status"] == "void":
        print("\n[硬闸] 拒绝产出读数记录（exit 1）。修正判官/锚集后重跑。")
        return 1
    if args.out:
        out = Path(args.out)
        if out.exists():
            data = json.loads(out.read_text(encoding="utf-8"))
        else:
            data = {"generated_by": "judge_audit.py v1", "rounds": {}}
        data["rounds"][rec["round"]] = rec
        out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"记录已写入 → {out}")
    return 0


# ------------------------------------------------------------------ 自检

def _anchors(n_pos: int, n_neg: int) -> list:
    return ([{"qid": f"pos{i:02d}", "expected": "correct"} for i in range(1, n_pos + 1)]
            + [{"qid": f"neg{i:02d}", "expected": "incorrect"} for i in range(1, n_neg + 1)])


def _judge_from_wrongset(anchors: list, wrong: set) -> dict:
    out = {}
    for a in anchors:
        base = "correct" if a["expected"] == "correct" else "incorrect"
        if a["qid"] in wrong:
            base = "incorrect" if base == "correct" else "correct"
        out[a["qid"]] = base
    return out


def selftest() -> int:
    """定点变异用例：硬闸必须拒绝被人为破坏的判官——证明它不是恒真断言。"""
    ok = True
    anchors = _anchors(20, 20)

    def run(job, **kw):
        return run_job(job, min_delta=0.15, policy=kw.get("policy", "void-all"),
                       same_min=0.8, kappa_min=0.6, same_floor=0.5)

    # 用例 1：三名合格判官 → 必须放行
    j1 = _judge_from_wrongset(anchors, set())
    j2 = _judge_from_wrongset(anchors, {"pos01", "pos02", "neg01", "neg02"})
    j3 = _judge_from_wrongset(anchors, {"pos03", "pos04", "neg03", "neg04"})
    rec = run({"round": "自检·合格", "stratum": "均衡", "anchors": anchors,
               "judges": {"J1": j1, "J2": j2, "J3": j3}})
    c1 = rec["status"] == "pass" and rec["report_mode"] == "可报值"
    print(f"[自检1] 合格批放行 … {'PASS' if c1 else 'FAIL'}（{rec['status']}/{rec.get('report_mode')}）")
    ok &= c1

    # 用例 2：定点变异——J2 正确率打到 50%（基线 50% ⇒ +0pp < 15pp）→ 硬闸必须拒绝
    j2_mut = {q: "correct" for q in j2}          # 全判 correct：对半分锚集下正确率恰 50%
    rec2 = run({"round": "自检·变异", "stratum": "均衡", "anchors": anchors,
                "judges": {"J1": j1, "J2": j2_mut, "J3": j3}})
    c2 = rec2["status"] == "void" and "J2" in rec2["reason"]
    print(f"[自检2] 定点变异被拒 … {'PASS' if c2 else 'FAIL'}（{rec2['status']}：{rec2.get('reason')}）")
    ok &= c2
    # 同一变异在 keep-qualified 策略下：剔除 J2、余两名合格继续
    rec2b = run({"round": "自检·变异·保留", "stratum": "均衡", "anchors": anchors,
                 "judges": {"J1": j1, "J2": j2_mut, "J3": j3}}, policy="keep-qualified")
    c2b = rec2b["status"] == "pass" and rec2b.get("voided_judges") == ["J2"]
    print(f"[自检2b] 保留策略剔除变异判官 … {'PASS' if c2b else 'FAIL'}"
          f"（{rec2b['status']}／剔除 {rec2b.get('voided_judges')}）")
    ok &= c2b

    # 用例 3：尺度塌缩（假一致）——三判官全判 correct：同分 100%，锚上全部只到基线 ⇒ 必须作废
    collapse = {"J1": {q: "correct" for q in j1}, "J2": {q: "correct" for q in j1},
                "J3": {q: "correct" for q in j1}}
    rec3 = run({"round": "自检·塌缩", "stratum": "均衡", "anchors": anchors, "judges": collapse})
    c3 = rec3["status"] == "void"
    print(f"[自检3] 假一致（100% 同分但锚上退化）被拒 … {'PASS' if c3 else 'FAIL'}（{rec3.get('reason')}）")
    ok &= c3

    # 用例 4：两名判官各自合格（80%）但互相不合（同分 60%/kappa≈0.2）⇒ 只报序，不得报值
    jA = _judge_from_wrongset(anchors, {"pos17", "pos18", "pos19", "pos20",
                                        "neg17", "neg18", "neg19", "neg20"})
    jB = _judge_from_wrongset(anchors, {"pos13", "pos14", "pos15", "pos16",
                                        "neg01", "neg02", "neg03", "neg04"})
    rec4 = run({"round": "自检·低一致", "stratum": "均衡", "anchors": anchors,
                "judges": {"A": jA, "B": jB}})
    c4 = rec4["status"] == "pass" and rec4["report_mode"] == "只报序"
    print(f"[自检4] 合格但低一致 ⇒ 只报序 … {'PASS' if c4 else 'FAIL'}"
          f"（同分 {rec4.get('agreement', {}).get('mean_identical'):.1%}／"
          f"kappa {rec4.get('agreement', {}).get('mean_kappa'):.2f} ⇒ {rec4.get('report_mode')}）")
    ok &= c4

    # 用例 5：漏答锚——两名判官各只答 40 锚中的 2 个（正确率 100%／覆盖 5%）⇒ 必须作废
    few = {q: j1[q] for q in ("pos01", "neg01")}
    rec5 = run({"round": "自检·漏答", "stratum": "均衡", "anchors": anchors,
                "judges": {"J1": few, "J2": dict(few)}})
    c5 = rec5["status"] == "void" and "覆盖不足" in rec5.get("reason", "")
    print(f"[自检5] 漏答锚（覆盖 5%）被拒 … {'PASS' if c5 else 'FAIL'}（{rec5.get('reason')}）")
    ok &= c5

    # 用例 6：恰在门槛——基线 80%、判官 95%（= +15pp，浮点下 0.1499999999999999）⇒ 必须放行
    anc6 = _anchors(16, 4)
    jj = {}
    for tag, wrong in (("J1", {"pos01"}), ("J2", {"pos02"})):
        d = _judge_from_wrongset(anc6, wrong)
        jj[tag] = d
    rec6 = run({"round": "自检·恰在门槛", "stratum": "偏正", "anchors": anc6, "judges": jj})
    c6 = rec6["status"] == "pass"
    print(f"[自检6] 恰在 15pp 门槛放行 … {'PASS' if c6 else 'FAIL'}"
          f"（{rec6['status']}／{rec6.get('reason', rec6.get('report_mode'))}）")
    ok &= c6

    # 用例 7：汇总模式必须与明细模式同口径（issue #13）——登记一致率 30% 不得判「可报值」
    def sm(rec_ag, **kw):
        job = {"round": "自检·汇总", "stratum": "均衡", "provenance": "自检",
               "summary": {"positives": 9, "negatives": 9,
                           "judges": {"甲批": {"pos_hit": 9, "neg_miss": 0},
                                      "乙批": {"pos_hit": 8, "neg_miss": 0}}}, **kw}
        if rec_ag is not None:
            job["agreement_recorded"] = rec_ag
        return run(job)
    r7a = sm({"mean_identical": 0.30, "mean_kappa": 0.05})
    r7b = sm(None)
    r7c = sm({"mean_identical": 0.90, "mean_kappa": 0.80})
    c7 = (r7a["report_mode"] in ("只报序", "不可测") and r7b["report_mode"] in ("只报序", "不可测")
          and r7c["report_mode"] == "可报值")
    print(f"[自检7] 汇总模式一致率同口径 … {'PASS' if c7 else 'FAIL'}"
          f"（30%→{r7a['report_mode']}／未登记→{r7b['report_mode']}／90%→{r7c['report_mode']}）")
    ok &= c7

    # 用例 8：汇总模式输入契约（issue #13）——越界读数与自报 panel_size 必须被拒
    def reject(**kw):
        job = {"round": "自检·越界", "stratum": "均衡", "provenance": "自检",
               "summary": {"positives": 9, "negatives": 9,
                           "judges": {"批": {"pos_hit": kw.pop("pos_hit", 9),
                                             "neg_miss": kw.pop("neg_miss", 0)}}}, **kw}
        try:
            run(job)
            return False
        except InputError:
            return True
    c8 = reject(pos_hit=30) and reject(panel_size=2) and reject(neg_miss=99)
    print(f"[自检8] 汇总模式越界读数／自报 panel_size 被拒 … {'PASS' if c8 else 'FAIL'}")
    ok &= c8

    print(f"\n自检结果：{'全部通过 ✅（硬闸对定点变异有效）' if ok else '存在失败 ❌'}")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="判官协议机械件：锚自证 + 一致率 + 硬闸")
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("check", help="对一轮输入执行审计并（合格时）写入记录")
    c.add_argument("input")
    c.add_argument("--out", default=None, help="读数记录 JSON（默认不写）")
    c.add_argument("--min-delta", type=float, default=0.15, help="锚自证差值门槛（默认 0.15）")
    c.add_argument("--policy", choices=("void-all", "keep-qualified"), default="void-all")
    c.add_argument("--same-min", type=float, default=0.8)
    c.add_argument("--kappa-min", type=float, default=0.6)
    c.add_argument("--same-floor", type=float, default=0.5, help="低于此值判 不可测")
    c.add_argument("--coverage-min", type=float, default=COVERAGE_MIN,
                   help=f"锚覆盖率下限（默认 {COVERAGE_MIN}）")

    sub.add_parser("selftest", help="含定点变异的自检（证明硬闸非恒真）")

    args = ap.parse_args()
    if args.cmd == "selftest":
        return selftest()
    return cmd_check(args)


if __name__ == "__main__":
    sys.exit(main())
