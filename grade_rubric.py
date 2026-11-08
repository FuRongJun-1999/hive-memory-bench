# -*- coding: utf-8 -*-
"""六元素 rubric 判分器（rubric_92 / 476 通用）

两种协议都支持：
  single  每条断言单独作答（推荐）。判据 = 平衡准确率 (TPR+TNR)/2 与 φ。
          ——对「一律答否」这类偏置免疫：偏置只会把平衡准确率压回 50%，不会虚高。
  batch   每题 6 条一次作答。判据 = 整题全对率（随机 1/64 = 1.56%）。
          ——该口径读数对材料规模非单调（见 docs/多跳六元素rubric92_验证报告_v1.0.md），
            只适合做「闭卷约等于随机」的泄漏检查，不宜当上限读数。

输入 answers.jsonl 每行至少含：qid / arm / truth / got
  got 为 true(判「是」) / false(判「否」) / null(未解析)
  single 协议还需 pi（该点在题内的序号，0..5）
用法：
  python grade_rubric.py --set mcq/reasoning/题目_多跳六元素_rubric92_平衡掩码.json \
      --answers rbvs_s552.jsonl --protocol single
"""
import json, math, argparse, collections


def binom_p(k, n, p0):
    if n == 0:
        return 1.0
    pmf = lambda i: math.comb(n, i) * (p0 ** i) * ((1 - p0) ** (n - i))
    obs = pmf(k)
    return min(1.0, sum(pmf(i) for i in range(n + 1) if pmf(i) <= obs + 1e-15))


def conf(rs):
    tp = sum(1 for r in rs if r["truth"] and r["got"] is True)
    fn = sum(1 for r in rs if r["truth"] and r["got"] is False)
    fp = sum(1 for r in rs if not r["truth"] and r["got"] is True)
    tn = sum(1 for r in rs if not r["truth"] and r["got"] is False)
    return tp, fn, fp, tn


def score_single(recs, labels):
    out = {}
    for arm in labels:
        rs = [r for r in recs if r["arm"] == arm and r.get("got") is not None]
        if not rs:
            continue
        tp, fn, fp, tn = conf(rs)
        tpr = tp / max(1, tp + fn)
        tnr = tn / max(1, tn + fp)
        den = math.sqrt(float(tp + fp) * (tp + fn) * (tn + fp) * (tn + fn)) or 1.0
        byq = collections.defaultdict(list)
        for r in rs:
            byq[r.get("qid") or r.get("idx")].append(r)
        six = [v for v in byq.values() if len(v) == 6]
        q_all = (sum(1 for v in six if all((x["got"] is True) == x["truth"] for x in v))
                 if six else None)
        slot = collections.defaultdict(lambda: [0, 0])
        for r in rs:
            pi = r.get("pi", 0)
            slots = r.get("slots") or []
            sl = slots[pi] if len(slots) > pi else "?"
            slot[sl][1] += 1
            if (r["got"] is True) == r["truth"]:
                slot[sl][0] += 1
        out[arm] = {"n": len(rs), "tp": tp, "fn": fn, "fp": fp, "tn": tn,
                    "tpr": round(100 * tpr, 1), "tnr": round(100 * tnr, 1),
                    "balanced_acc": round(100 * (tpr + tnr) / 2, 1),
                    "phi": round((tp * tn - fp * fn) / den, 3),
                    "raw_acc": round(100.0 * (tp + tn) / max(1, len(rs)), 1),
                    "question_all6": ("%d/%d" % (q_all, len(six)) if q_all is not None
                                     else "n/a（该题集每问只有 1 条断言）"),
                    "p_vs_50pct": binom_p(tp + tn, len(rs), 0.5),
                    "slot": {k: round(100.0 * v[0] / v[1], 1) for k, v in slot.items()}}
    return out


def score_batch(recs, labels):
    out = {}
    qslots = {}
    for arm in labels:
        rs = [r for r in recs if r["arm"] == arm]
        if not rs:
            continue
        n = len(rs)
        allok = sum(1 for r in rs if r.get("got") == r["truth"])
        pts = sum(1 for r in rs for a, b in zip(r.get("got") or [], r["truth"]) if a == b)
        tot = sum(len(r["truth"]) for r in rs)
        yes = sum(1 for r in rs for g in (r.get("got") or []) if g is True)
        out[arm] = {"n": n, "question_all6": "%d/%d = %.1f%%" % (allok, n, 100.0 * allok / n),
                    "p_vs_1_64": binom_p(allok, n, 1 / 64.0),
                    "point_acc": "%.1f%% (%d/%d)" % (100.0 * pts / max(1, tot), pts, tot),
                    "yes_rate": "%.1f%%" % (100.0 * yes / max(1, tot))}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--answers", required=True)
    ap.add_argument("--set", default="")
    ap.add_argument("--protocol", default="single", choices=["single", "batch"])
    ap.add_argument("--arms", default="")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    recs = [json.loads(l) for l in open(args.answers, encoding="utf-8") if l.strip()]
    labels = ([a.strip() for a in args.arms.split(",") if a.strip()] if args.arms
              else sorted({r["arm"] for r in recs}))
    res = score_single(recs, labels) if args.protocol == "single" else score_batch(recs, labels)
    print(json.dumps(res, ensure_ascii=False, indent=1))
    if args.out:
        json.dump(res, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if args.protocol == "single" and len(labels) >= 2:
        a, b = labels[0], labels[1]
        if a in res and b in res:
            print("\n记忆信号：平衡准确率 %.1f%% → %.1f%%，差 %+.1f 点；φ %.3f → %.3f"
                  % (res[a]["balanced_acc"], res[b]["balanced_acc"],
                     res[b]["balanced_acc"] - res[a]["balanced_acc"], res[a]["phi"], res[b]["phi"]))


if __name__ == "__main__":
    main()
