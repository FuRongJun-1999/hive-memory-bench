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
  · 锚自证：判官在锚上的正确率 − 多数类基线 ≥ 15pp ⇒ 合格（`判分可靠性_v1.0.md` §3）；
  · 一致率：平均同分 ≥ 0.8 或 平均 kappa ≥ 0.6 ⇒ `可报值`；≥ 0.5 ⇒ `只报序`；否则 `不可测`；
  · 一致率必须连**样本档位**一起报（同一判官批 kappa 0.939↔0.552 的实测教训）——
    输出记录强制带 `stratum` 字段。
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


def _norm(v) -> str:
    return str(v).strip().lower()


# ------------------------------------------------------------------ 锚自证

def anchor_baseline(expected: list) -> float:
    """多数类基线：锚集里占比最大的那一档的频率。"""
    if not expected:
        return 0.0
    return max(Counter(expected).values()) / len(expected)


def evaluate_anchors(anchors: list, judges: dict, verdict_key: str = "verdict") -> dict:
    """逐判官锚自证：正确率 / 基线 / 差值 / 覆盖率。"""
    exp = {a["qid"]: _norm(a["expected"]) for a in anchors}
    base = anchor_baseline(list(exp.values()))
    out = {}
    for name, verdicts in judges.items():
        n = hit = 0
        for qid, e in exp.items():
            v = verdicts.get(qid)
            if v is None:
                continue
            n += 1
            if _norm(v) == e:
                hit += 1
        acc = hit / n if n else 0.0
        out[name] = {"n": n, "coverage": (n / len(exp)) if exp else 0.0,
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
    if ag.get("mean_identical") is None:
        return "不可测"
    if ag["mean_identical"] >= same_min or (ag["mean_kappa"] or 0) >= kappa_min:
        return "可报值"
    if ag["mean_identical"] >= same_floor:
        return "只报序"
    return "不可测"


# ------------------------------------------------------------------ 主流程

def build_job_from_summary(job: dict) -> dict:
    """汇总模式 → 与明细模式同构的中间结构（单判官批）。"""
    s = job["summary"]
    pos, neg = int(s["positives"]), int(s["negatives"])
    total = pos + neg
    base = max(pos, neg) / total if total else 0.0
    judges = {}
    for name, st in s["judges"].items():
        acc = (int(st["pos_hit"]) + (neg - int(st.get("neg_miss", 0)))) / total
        judges[name] = {"n": total, "coverage": 1.0, "accuracy": acc,
                        "baseline": base, "delta": acc - base}
    return {"anchors_shape": {"positives": pos, "negatives": neg, "baseline": base},
            "judges": judges}


def run_job(job: dict, *, min_delta: float, policy: str,
            same_min: float, kappa_min: float, same_floor: float) -> dict:
    """执行一次审计。返回记录 dict；`status` ∈ pass|void。"""
    rec = {"round": job.get("round"), "stratum": job.get("stratum"),
           "provenance": job.get("provenance"),
           "policy": policy, "min_delta": min_delta,
           "panel_size": int(job.get("panel_size", 1)),
           "thresholds": {"same_min": same_min, "kappa_min": kappa_min,
                          "same_floor": same_floor}}

    if "summary" in job:                                  # 汇总模式：无逐题明细，一致率引用已归档值
        mid = build_job_from_summary(job)
        rec["anchors"] = mid["anchors_shape"]
        rec["judges"] = mid["judges"]
        ag = None
        if job.get("agreement_recorded"):
            rec["agreement"] = {"source": "recorded", **job["agreement_recorded"]}
        else:
            rec["agreement"] = {"source": "not_recorded"}
    else:                                                 # 明细模式
        anchors, judges = job["anchors"], job["judges"]
        rec["anchors"] = {"n": len(anchors),
                          "baseline": anchor_baseline([_norm(a["expected"]) for a in anchors])}
        rec["judges"] = evaluate_anchors(anchors, judges)
        ag = evaluate_agreement(anchors, judges)

    for name, st in rec["judges"].items():
        st["qualified"] = st["delta"] >= min_delta
    unqualified = sorted(n for n, st in rec["judges"].items() if not st["qualified"])

    # —— 硬闸 ——
    if unqualified and policy == "void-all":
        rec.update(status="void", report_mode="不可测", reason=f"判官不合格：{unqualified}（整批作废）")
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
        rec["agreement"] = {"source": "computed", **ag}
        rec["report_mode"] = mode
        if mode == "不可测":
            rec.update(status="void", reason="判官间一致率不可测（低于报序下限）")
            return rec
    else:
        rec.setdefault("report_mode", "可报值")
    rec["status"] = "pass"
    return rec


def _print_record(rec: dict) -> None:
    print(f"—— 轮次：{rec['round']}｜样本档位：{rec['stratum']}")
    print(f"   锚集基线：{rec['anchors'].get('baseline', 0):.1%}"
          + (f"（正 {rec['anchors']['positives']}／负 {rec['anchors']['negatives']}）"
             if "positives" in rec["anchors"] else f"（n={rec['anchors'].get('n')}）"))
    for name, st in rec["judges"].items():
        mark = "✅" if st["qualified"] else "❌"
        print(f"   {mark} {name:<18} 正确率 {st['accuracy']:6.1%} − 基线 {st['baseline']:.1%}"
              f" = {st['delta']:+.1%}（覆盖 {st['coverage']:.0%}）")
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
    rec = run_job(job, min_delta=args.min_delta, policy=args.policy,
                  same_min=args.same_min, kappa_min=args.kappa_min,
                  same_floor=args.same_floor)
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

    sub.add_parser("selftest", help="含定点变异的自检（证明硬闸非恒真）")

    args = ap.parse_args()
    if args.cmd == "selftest":
        return selftest()
    return cmd_check(args)


if __name__ == "__main__":
    sys.exit(main())
