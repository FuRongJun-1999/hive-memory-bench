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
  · 一致率：在**两判官共同作答的全部条目**上算（issue #33 第二项）——
    平均同分 ≥ 0.8 或 平均 kappa ≥ 0.6 ⇒ `可报值`；同分 ≥ 0.5 **且** kappa > `--kappa-floor`
    ⇒ `只报序`；否则 `不可测`。任一配对 kappa ≤ kappa_floor（默认 0，方向不一致/低于机会）
    即 `不可测`（issue #33 第三项）。作业里除锚之外没有别的条目时，报告模式**至多「只报序」**。
    锚上一致率另列 `anchor_agreement` 仅作参考；kappa 算在哪些条目上必须写进记录。
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


def _all_qids(judges: dict) -> list:
    """所有判官作答过的 qid（保持首次出现顺序）。"""
    seen = []
    for verdicts in judges.values():
        for q in verdicts:
            if q not in seen:
                seen.append(q)
    return seen


# ★ 一对判官至少要有这么多条**非锚**配对，才算「算在被测条目上」（issue #42-五 JA1／JA2）。
MIN_NONANCHOR_PAIRS = 1


def _pair_up(names: list, judges: dict, items: list, anchor_qids=None) -> list:
    """逐对判官在 `items` 上算同分率与 kappa。

    ★ issue #42-五（JA1／JA2）：逐对记 `n` 与 `n_nonanchor`。旧实现只记 `n`，而 `scope`
      是按**并集**（`_all_qids`）算的——两判官各答了不同的非锚条目时，并集里有非锚条目
      ⇒ 记 `scope="all"`、封顶失效，实际每一对都只在 40 个锚上配对，读数却写成「算在 140 条上」。
    """
    anchor_qids = anchor_qids or set()
    pairs = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            xs, ys, n_non = [], [], 0
            for q in items:
                va, vb = judges[names[i]].get(q), judges[names[j]].get(q)
                if va is not None and vb is not None:
                    xs.append(_norm(va))
                    ys.append(_norm(vb))
                    if q not in anchor_qids:
                        n_non += 1
            if not xs:
                continue
            pairs.append({"pair": [names[i], names[j]], "n": len(xs),
                          "n_nonanchor": n_non,
                          "identical": sum(1 for x, y in zip(xs, ys) if x == y) / len(xs),
                          "kappa": cohen_kappa(xs, ys)})
    return pairs


def _fold(pairs: list) -> dict:
    if not pairs:
        return {"pairs": [], "mean_identical": None, "mean_kappa": None, "min_kappa": None}
    return {"pairs": pairs,
            "mean_identical": sum(p["identical"] for p in pairs) / len(pairs),
            "mean_kappa": sum(p["kappa"] for p in pairs) / len(pairs),
            "min_kappa": min(p["kappa"] for p in pairs)}


def evaluate_agreement(anchors: list, judges: dict, items: list = None) -> dict:
    """逐对判官：同分率 + kappa；返回 {pairs, mean_identical, mean_kappa, min_kappa, scope}。

    ★ 一致率的**分母是两判官共同作答的全部条目**（issue #33 第二项）：此前只遍历
      `anchors`，被测条目一条不进 xs/ys ⇒ 二分类下锚上同分 ≥ a1 + a2 − 1，两判官锚上
      都 ≥90% ⇒ 同分 ≥ 0.8 ⇒ 直接「可报值」；锚上都 100% 时 kappa 恒为 1.000。
      `items` 缺省取全体判官作答过的 qid；`scope` 标出算在哪些条目上。
    """
    names = list(judges)
    if items is None:
        items = _all_qids(judges)
    items = list(items)
    anchor_qids = {a["qid"] for a in anchors}
    out = _fold(_pair_up(names, judges, items, anchor_qids))
    # ★ issue #42-五（JA1／JA2）：`scope` 按**配对交集**判，不按并集。任一对判官实际只在
    #   锚上配对（`n_nonanchor` 低于门槛）⇒ 整批按「锚上-only」封顶，至多只报序。
    #   旧实现按并集判：两判官各答了不同的非锚条目即记 `scope="all"`，封顶被绕过，
    #   `_print_record` 还打印「算在 140 条上」，而实际配对数是 40。
    if out["pairs"] and all(p["n_nonanchor"] >= MIN_NONANCHOR_PAIRS for p in out["pairs"]):
        out["scope"] = "all"
    else:
        out["scope"] = "anchors-only"
    out["n_items"] = len(items)
    out["n_anchor_items"] = sum(1 for q in items if q in anchor_qids)
    out["n_nonanchor_items"] = out["n_items"] - out["n_anchor_items"]
    out["n_paired_items"] = max((p["n"] for p in out["pairs"]), default=0)
    out["n_paired_nonanchor"] = max((p["n_nonanchor"] for p in out["pairs"]), default=0)
    # 锚上一致率：仅作参考，**不得**作为「可报值」的依据（issue #33 第二项）
    a_only = _fold(_pair_up(names, judges, [q for q in items if q in anchor_qids], anchor_qids))
    out["anchor_agreement"] = {"mean_identical": a_only["mean_identical"],
                               "mean_kappa": a_only["mean_kappa"]}
    return out


def classify_agreement(ag: dict, same_min: float, kappa_min: float, same_floor: float,
                       kappa_floor: float = 0.0) -> str:
    """一致率 → 报告模式。

    ★ 两路都可单独成立（issue #13）：汇总模式回填的历史值可能只登记了同分率、
      也可能只登记了 kappa。此前只认同分率，`mean_identical` 缺失即「不可测」，
      于是「只登记 kappa 0.9」这种明显够格的读数反而被判不可测。

    ★ kappa 参与「只报序」的下限（issue #33 第三项）：此前只看 `mean_identical >= same_floor`，
      kappa 不参与、方向不查 ⇒ kappa 0.000、−0.250（恰在机会水平／低于机会、方向不一致）
      也能「只报序」并 exit 0，与协议「≥2 名判官**方向上一致**才可报序」不符。
      现在任一配对 kappa ≤ kappa_floor（默认 0）即「不可测」。
    """
    mi, mk = ag.get("mean_identical"), ag.get("mean_kappa")
    if mi is None and mk is None:
        return "不可测"
    worst = ag.get("min_kappa")
    if worst is None:
        worst = mk
    if worst is not None and worst <= kappa_floor:
        return "不可测"          # 低于机会水平／方向不一致 ⇒ 连序也不报
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
            coverage_min: float = COVERAGE_MIN, kappa_floor: float = 0.0) -> dict:
    """执行一次审计。返回记录 dict；`status` ∈ pass|void。

    ★ 汇总模式与明细模式对**同样的一致率**必须给出同样的报告模式（issue #13）：
      此前汇总模式 `ag = None`，直接 `setdefault("report_mode", "可报值")`——
      登记一致率 30% 也判「可报值」，`classify_agreement` 从不被调用。
    """
    rec = {"round": job.get("round"), "stratum": job.get("stratum"),
           "provenance": job.get("provenance"),
           "policy": policy, "min_delta": min_delta, "coverage_min": coverage_min,
           "panel_size": 1,
           "thresholds": {"same_min": same_min, "kappa_min": kappa_min,
                          "same_floor": same_floor, "kappa_floor": kappa_floor}}
    anchors = judges = None            # 明细模式留用：keep-qualified 剔除后要重算一致率

    if "summary" in job:                                  # 汇总模式：无逐题明细，一致率引用已归档值
        mid = build_job_from_summary(job)                 # 越界读数在此被拒（InputError）
        rec["anchors"] = mid["anchors_shape"]
        rec["judges"] = mid["judges"]
        # ★ panel_size 只能由判官数推出（issue #13）：此前它直接取输入，单个「判官批」
        #   写 panel_size: 2 即满足「合格判官 ≥ 2」，等于自报人数。要声明多判官，
        #   必须给出**逐判官**汇总。
        declared = int(job.get("panel_size", 1) or 1)
        # ★ issue #42-五（JA4）：**单条批汇总 + 声明人数**的旧格式另走契约——输入必须显式
        #   写 `summary_kind: "panel_batch"`，人数才按声明记（并注明为自报）。此前该格式
        #   一律被 `declared > 逐判官汇总数` 拒掉（仓内两份自带输入 exit 2），而归档里却
        #   写着 `panel_size: 3 / status: pass`——归档无法由工具复现。
        rec["panel_kind"] = "batch" if str(job.get("summary_kind") or "") == "panel_batch" \
            else "per_judge"
        if rec["panel_kind"] == "batch":
            rec["panel_size"] = max(1, declared)
            rec["note_panel"] = (f"批汇总格式（summary_kind=panel_batch）：人数 {rec['panel_size']}"
                                 f" 由输入自报，无逐判官明细可核（issue #42-五）")
        elif declared > len(rec["judges"]):
            raise InputError(
                f"panel_size={declared} 与逐判官汇总数 {len(rec['judges'])} 不符——"
                f"汇总模式要声明多判官必须给出逐判官汇总（issue #13）；"
                f"单条批汇总请显式写 summary_kind=panel_batch（issue #42-五）")
        else:
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
        # ★ 明细模式 panel_size 固定为 1（issue #33 第四项）：此前直接取输入的
        #   `panel_size`（模块说明只把它写在汇总模式下），于是一份合格判官 + 输入里写
        #   `panel_size: 2` 就绕过「合格判官 < 2 ⇒ 作废」，与「禁止单判官出结论」相反。
        rec["panel_kind"] = "per_judge"
        if int(job.get("panel_size", 1) or 1) != 1:
            rec["panel_size_ignored"] = int(job.get("panel_size", 1) or 1)
            rec["note_panel"] = ("明细模式的 panel_size 取输入自报，不可信 ⇒ 固定按 1 计"
                                 "（issue #33 第四项）")

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
    # ★ issue #42-五（JA3）：`panel_size` 现在**由判官数推出**（逐判官汇总 = 汇总条数，
    #   明细模式固定 1），再乘一次等于同一个人被数两遍——2 名判官里 1 名合格即 1×2 = 2
    #   过门（旧树 1×1 < 2 作废）。只有显式声明的**批汇总**格式才乘自报人数。
    n_eff = len(survivors) * panel if rec.get("panel_kind") == "batch" else len(survivors)
    if n_eff < 2:
        rec.update(status="void", report_mode="不可测",
                   reason=(f"合格判官 {len(survivors)}"
                           + (f"×{panel}（批汇总自报人数）" if rec.get("panel_kind") == "batch" else "")
                           + " < 2（作废）"))
        return rec
    if unqualified:
        rec["voided_judges"] = unqualified
        # ★ keep-qualified 剔除后必须**重算**一致率（issue #33 第四项）：此前 ag 是在判定
        #   合格**之前**对**全部**判官算的，剔掉不合格者后仍拿旧值分档——实测 10 份不合格
        #   副本把 0.600 抬到 0.842「可报值」，且 pairs 里 66 对有 65 对含被剔判官。
        if policy == "keep-qualified" and anchors is not None:
            ag = evaluate_agreement(anchors, {n: judges[n] for n in survivors})
            rec["agreement_recomputed"] = "keep-qualified 剔除后仅在合格判官间重算（issue #33）"

    if ag is not None:
        mode = classify_agreement(ag, same_min, kappa_min, same_floor, kappa_floor)
        if rec.get("agreement", {}).get("source") != "recorded":
            rec["agreement"] = {"source": "computed", **ag}
        # ★ 只算在锚上 ⇒ 至多「只报序」（issue #33 第二项）：锚自证门槛本身就能推出
        #   锚上高一致（二分类下两判官锚上各 ≥90% ⇒ 同分 ≥ 0.8），不能由它推出「可报值」。
        if ag.get("scope") == "anchors-only" and mode == "可报值":
            mode = "只报序"
            rec["note_scope"] = ("一致率只在锚上算（无非锚条目）⇒ 至多只报序"
                                 "（issue #33 第二项）")
        rec["report_mode"] = mode
        if mode == "不可测":
            rec.update(status="void", reason="判官间一致率不可测（低于报序下限或方向不一致）")
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
        # ★ pairs 为空时 mean_identical 是 None（issue #33 第四项附带）：
        #   此前直接 f"{None:.1%}" 抛 traceback，而不是走硬闸输出。
        mi, mk = ag.get("mean_identical"), ag.get("mean_kappa")
        if mi is None and mk is None:
            print("   一致率：无可用配对 ⇒ 不可测")
        else:
            print("   一致率："
                  + (f"同分 {mi:.1%}" if mi is not None else "同分 —")
                  + "／"
                  + (f"kappa {mk:.3f}" if mk is not None else "kappa —")
                  + f"  ⇒ {rec['report_mode']}")
        scope = ag.get("scope")
        if scope == "anchors-only":
            print(f"     （★ 配对只在锚上：每对实际配对 {ag.get('n_paired_items')} 条、"
                  f"其中非锚 {ag.get('n_paired_nonanchor')} 条 ⇒ 至多只报序，issue #33／#42-五）")
        elif scope == "all":
            print(f"     （配对 {ag.get('n_paired_items')} 条／对：锚 {ag.get('n_anchor_items')} ＋ "
                  f"被测 {ag.get('n_paired_nonanchor')}；并集 {ag.get('n_items')} 条）")
        if rec.get("agreement_recomputed"):
            print(f"     （{rec['agreement_recomputed']}）")
        if rec.get("voided_judges"):
            print(f"     （已剔除不合格判官：{'、'.join(rec['voided_judges'])}）")
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
                      same_floor=args.same_floor, coverage_min=args.coverage_min,
                      kappa_floor=args.kappa_floor)
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
    """定点变异用例：硬闸必须拒绝被人为破坏的判官——证明它不是恒真断言。

    ★ 作业形态（issue #33 第二项）：真实作业是「掺锚」的——锚集之外还有被测条目。
      一致率只在锚上算时，锚自证门槛本身就能推出「锚上高一致」（二分类下两判官锚上
      各 ≥90% ⇒ 同分 ≥ 0.8），于是「可报值」变成锚自证的推论。下面所有放行用例都带
      非锚条目，并单独有用例证明「只在锚上算 ⇒ 至多只报序」。
    """
    ok = True
    anchors = _anchors(20, 20)
    # 非锚的被测条目：正负各半（避免标签分布单边把 kappa 压到机会水平以下）
    items = [f"x{i:02d}" for i in range(1, 41)]
    item_exp = {q: ("correct" if i % 2 == 0 else "incorrect") for i, q in enumerate(items)}

    def ext(judge, wrong=()):
        """把非锚条目并按 `wrong` 翻转后并入判官作答。"""
        d = dict(judge)
        for q in items:
            d[q] = item_exp[q] if q not in wrong else (
                "incorrect" if item_exp[q] == "correct" else "correct")
        return d

    def run(job, **kw):
        return run_job(job, min_delta=0.15, policy=kw.get("policy", "void-all"),
                       same_min=0.8, kappa_min=0.6, same_floor=0.5)

    # 用例 1：三名合格判官 → 必须放行
    j1 = ext(_judge_from_wrongset(anchors, set()))
    j2 = ext(_judge_from_wrongset(anchors, {"pos01", "pos02", "neg01", "neg02"}), {"x01", "x02"})
    j3 = ext(_judge_from_wrongset(anchors, {"pos03", "pos04", "neg03", "neg04"}), {"x03", "x04"})
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

    # 用例 4：两名判官各自合格（80%）但互相不合（同分 60%、kappa 0.20 > 0）⇒ 只报序，
    #   不得报值；kappa 参与下限后仍应放行到「只报序」而不是误杀（issue #33 第三项）
    jA = _judge_from_wrongset(anchors, {"pos17", "pos18", "pos19", "pos20",
                                        "neg17", "neg18", "neg19", "neg20"})
    jB = _judge_from_wrongset(anchors, {"pos13", "pos14", "pos15", "pos16",
                                        "neg01", "neg02", "neg03", "neg04"})
    rec4 = run({"round": "自检·低一致", "stratum": "均衡", "anchors": anchors,
                "judges": {"A": jA, "B": jB}})
    c4 = rec4["status"] == "pass" and rec4["report_mode"] == "只报序"
    print(f"[自检4] 合格但低一致（kappa > 0）⇒ 只报序 … {'PASS' if c4 else 'FAIL'}"
          f"（同分 {rec4.get('agreement', {}).get('mean_identical'):.1%}／"
          f"kappa {rec4.get('agreement', {}).get('mean_kappa'):.2f} ⇒ {rec4.get('report_mode')}）")
    ok &= c4

    # 用例 4b：kappa 参与「只报序」下限（issue #33 第三项）——旧实现只看同分 ≥ 0.5，
    #   于是 kappa 0.000（恰在机会水平）与 −0.250（低于机会、方向不一致）也能「只报序」并 exit 0，
    #   与协议「≥2 名判官**方向上一致**才可报序」相反。
    def sm_ag(mi, mk):
        return run({"round": "自检·kappa 下限", "stratum": "均衡", "provenance": "自检",
                    "panel_size": 2,
                    "summary": {"positives": 9, "negatives": 9,
                                "judges": {"甲": {"pos_hit": 9, "neg_miss": 0},
                                           "乙": {"pos_hit": 9, "neg_miss": 0}}},
                    "agreement_recorded": {"mean_identical": mi, "mean_kappa": mk}})
    k_pos, k_zero, k_neg = sm_ag(0.60, 0.20), sm_ag(0.60, 0.00), sm_ag(0.60, -0.25)
    c4b = (k_pos["report_mode"] == "只报序"
           and k_zero["status"] == "void" and k_neg["status"] == "void")
    print(f"[自检4b] kappa ≤ 0 连序也不报 … {'PASS' if c4b else 'FAIL'}"
          f"（kappa 0.20→{k_pos['report_mode']}／0.00→{k_zero['report_mode']}／"
          f"−0.25→{k_neg['report_mode']}）")
    ok &= c4b

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

    # 用例 9：一致率必须在**非锚条目**上也算（issue #33 第二项）——锚上两判官全对，
    #   被测 100 条完全相反。旧实现只看锚 ⇒ 同分 100%／kappa 1.000 ⇒「可报值」。
    n_items = [f"n{i:03d}" for i in range(1, 101)]
    jp = dict(j1)
    jq = dict(j1)
    for q in n_items:
        jp[q], jq[q] = "correct", "incorrect"
    rec9 = run({"round": "自检·锚外相反", "stratum": "均衡", "anchors": anchors,
                "judges": {"J1": jp, "J2": jq}})
    a9 = rec9.get("agreement", {})
    c9 = (rec9["status"] == "void" and rec9["report_mode"] == "不可测"
          and a9.get("scope") == "all" and (a9.get("mean_identical") or 1) < 0.5
          and (a9.get("anchor_agreement") or {}).get("mean_identical") == 1.0)
    print(f"[自检9] 锚上 100%／被测 100 条相反 ⇒ 不可测 … {'PASS' if c9 else 'FAIL'}"
          f"（整批同分 {a9.get('mean_identical'):.3f}／锚上 {a9.get('anchor_agreement', {}).get('mean_identical'):.1%}"
          f" ⇒ {rec9.get('report_mode')}）")
    ok &= c9

    # 用例 10：只在锚上算 ⇒ 至多「只报序」（issue #33 第二项）——锚自证门槛本身就能推出
    #   锚上高一致，故「可报值」不能由它推出。
    anchor_qids = {a["qid"] for a in anchors}
    rec10 = run({"round": "自检·仅锚", "stratum": "均衡", "anchors": anchors,
                 "judges": {"J1": {q: v for q, v in j1.items() if q in anchor_qids},
                            "J2": {q: v for q, v in j2.items() if q in anchor_qids}}})
    a10 = rec10.get("agreement", {})
    c10 = (rec10["status"] == "pass" and rec10["report_mode"] == "只报序"
           and a10.get("scope") == "anchors-only")
    print(f"[自检10] 一致率只在锚上算 ⇒ 至多只报序 … {'PASS' if c10 else 'FAIL'}"
          f"（同分 {a10.get('mean_identical'):.1%} ⇒ {rec10.get('report_mode')}）")
    ok &= c10

    # 用例 11：keep-qualified 剔除不合格判官后必须**重算**一致率（issue #33 第四项）——
    #   旧实现拿剔除前对**全部**判官算的 ag 分档：10 份不合格副本把 0.600 抬到 0.842「可报值」。
    kA = _judge_from_wrongset(anchors, {"pos17", "pos18", "pos19", "pos20",
                                        "neg17", "neg18", "neg19", "neg20"})
    kB = _judge_from_wrongset(anchors, {"pos13", "pos14", "pos15", "pos16",
                                        "neg01", "neg02", "neg03", "neg04"})
    kX = _judge_from_wrongset(anchors, {"pos17", "pos18", "pos19", "pos20",
                                        "neg17", "neg18", "neg19", "neg20",
                                        "pos05", "pos06", "pos07", "pos08",
                                        "neg05", "neg06", "neg07"})
    jr = {"A": kA, "B": kB}
    for i in range(10):
        jr[f"X{i}"] = dict(kX)
    rec11 = run({"round": "自检·剔除后重算", "stratum": "均衡", "anchors": anchors,
                 "judges": jr}, policy="keep-qualified")
    a11 = rec11.get("agreement", {})
    pairs11 = a11.get("pairs") or []
    c11 = (len(pairs11) == 1 and pairs11[0]["pair"] == ["A", "B"]
           and abs(pairs11[0]["identical"] - 0.6) < 1e-9
           and len(rec11.get("voided_judges") or []) == 10)
    print(f"[自检11] keep-qualified 剔除后重算一致率 … {'PASS' if c11 else 'FAIL'}"
          f"（pairs {len(pairs11)} 对，含被剔判官 {sum(1 for p in pairs11 if any(n.startswith('X') for n in p['pair']))} 对；"
          f"同分 {pairs11[0]['identical']:.3f} ⇒ {rec11.get('report_mode')}）")
    ok &= c11

    # 用例 12：明细模式的 panel_size 取输入自报、不可信 ⇒ 固定按 1 计（issue #33 第四项）
    rec12 = run({"round": "自检·自报人数", "stratum": "均衡", "anchors": anchors,
                 "panel_size": 2, "judges": {"J1": j1}})
    c12 = (rec12["status"] == "void" and rec12["panel_size"] == 1
           and rec12.get("panel_size_ignored") == 2)
    print(f"[自检12] 明细模式自报 panel_size 被忽略 … {'PASS' if c12 else 'FAIL'}"
          f"（panel_size={rec12.get('panel_size')}／自报 {rec12.get('panel_size_ignored')} ⇒ {rec12['status']}）")
    ok &= c12

    # 用例 13：pairs 为空时输出不得抛 traceback（issue #33 第四项附带）
    try:
        _print_record({"round": "自检·空 pairs", "stratum": "均衡", "anchors": {"n": 0},
                       "judges": {}, "panel_size": 1, "status": "void",
                       "report_mode": "不可测", "reason": "无可用配对",
                       "agreement": {"source": "computed", "pairs": [], "mean_identical": None,
                                     "mean_kappa": None, "min_kappa": None}})
        c13 = True
    except Exception as e:                                   # noqa: BLE001
        c13 = False
        print(f"       （异常：{e!r}）")
    print(f"[自检13] pairs 为空不抛 traceback … {'PASS' if c13 else 'FAIL'}")
    ok &= c13


    # 用例 14（issue #42-五 JA1／JA2）：两判官各答了**不同**的非锚条目 —— 并集里有非锚条目，
    #   但每一对实际只在锚上配对 ⇒ 必须按「锚上-only」封顶，至多只报序。
    _ax = {a["qid"]: a["expected"] for a in anchors}
    jx, jy = dict(_ax), dict(_ax)
    for q in n_items[:50]:
        jx[q] = "correct"
    for q in n_items[50:]:
        jy[q] = "correct"
    rec14 = run({"round": "自检·并集有非锚但配对全在锚上", "stratum": "均衡", "anchors": anchors,
                 "judges": {"J1": jx, "J2": jy}})
    a14 = rec14.get("agreement", {})
    c14 = (rec14["status"] == "pass" and rec14["report_mode"] == "只报序"
           and a14.get("scope") == "anchors-only"
           and a14.get("n_nonanchor_items", 0) == 100
           and a14.get("n_paired_nonanchor") == 0)
    print(f"[自检14] 并集有非锚／配对全在锚上 ⇒ 至多只报序 … {'PASS' if c14 else 'FAIL'}"
          f"（并集非锚 {a14.get('n_nonanchor_items')} 条／每对非锚配对 {a14.get('n_paired_nonanchor')} 条"
          f" ⇒ {rec14.get('report_mode')}）")
    ok &= c14

    # 用例 15（issue #42-五 JA3）：逐判官汇总模式下，2 名判官里 1 名合格 —— 不得因 panel_size
    #   被算两遍（1×2 = 2）而放行；旧树 `len(survivors) * panel` 正是这么过门的。
    rec15 = run({"round": "自检·逐判官汇总一人合格", "stratum": "均衡",
                 "summary": {"positives": 18, "negatives": 18,
                             "judges": {"J1": {"pos_hit": 18, "neg_miss": 0},
                                        "J2": {"pos_hit": 9, "neg_miss": 9}}}})
    c15 = (rec15["status"] == "void" and rec15["report_mode"] == "不可测"
           and rec15.get("panel_kind") == "per_judge")
    print(f"[自检15] 逐判官汇总仅 1 名合格 ⇒ 作废（panel 不重复折算） … {'PASS' if c15 else 'FAIL'}"
          f"（{rec15.get('reason')}）")
    ok &= c15

    # 用例 16（issue #42-五 JA4）：**单条批汇总 + 声明人数**的旧格式须显式写 summary_kind，
    #   写了才按声明人数记（并注明为自报）；没写仍被拒（exit 2）。
    batch = {"round": "自检·批汇总", "stratum": "均衡", "summary_kind": "panel_batch",
             "panel_size": 3,
             "summary": {"positives": 18, "negatives": 18,
                         "judges": {"判官批（3 判官均值）": {"pos_hit": 18, "neg_miss": 0}}}}
    try:
        rec16 = run(batch)
        c16a = (rec16["status"] == "pass" and rec16["panel_size"] == 3
                and rec16.get("panel_kind") == "batch" and rec16.get("note_panel"))
    except InputError:
        c16a = False
        rec16 = {}
    try:
        run({k: v for k, v in batch.items() if k != "summary_kind"})
        c16b = False
    except InputError:
        c16b = True
    c16 = bool(c16a) and c16b
    print(f"[自检16] 批汇总须显式声明人数格式 … {'PASS' if c16 else 'FAIL'}"
          f"（声明后 {rec16.get('status')}／人数 {rec16.get('panel_size')}；未声明被拒 {c16b}）")
    ok &= c16
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
    c.add_argument("--kappa-floor", type=float, default=0.0,
                   help="任一配对 kappa ≤ 此值即判 不可测（默认 0，方向不一致/低于机会）")
    c.add_argument("--coverage-min", type=float, default=COVERAGE_MIN,
                   help=f"锚覆盖率下限（默认 {COVERAGE_MIN}）")

    sub.add_parser("selftest", help="含定点变异的自检（证明硬闸非恒真）")

    args = ap.parse_args()
    if args.cmd == "selftest":
        return selftest()
    return cmd_check(args)


if __name__ == "__main__":
    sys.exit(main())
