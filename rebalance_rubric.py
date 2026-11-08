# -*- coding: utf-8 -*-
"""rubric 题集「平衡掩码」重排（消除题序位置泄漏）

问题：生成器常把「3 真 3 假」排成 TFTFTF / TTTFFF 之类固定模式，位置本身就带答案。
做法：20 种「6 选 3」掩码全用一遍（题数不足 20 种时按池循环），掩码分配与题序无关（定种子）；
      要点内容与其真假标签一起搬到新槽位。判分口径不变（真假标签随点走）。

自检（脚本内断言）：掩码种类、每种出现次数、各槽位真点率、最热掩码占比。

用法：
  python rebalance_rubric.py --src archive/....json --dst mcq/reasoning/xxx.json --seed 20261109
"""
import json, random, itertools, collections, argparse


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--dst", required=True)
    ap.add_argument("--seed", type=int, default=20261109)
    args = ap.parse_args()

    qs = json.load(open(args.src, encoding="utf-8"))
    masks = sorted(itertools.combinations(range(6), 3))
    pool = masks * (len(qs) // len(masks)) + masks[: len(qs) % len(masks)]
    rnd = random.Random(args.seed)
    rnd.shuffle(pool)

    out = []
    for i, q in enumerate(qs):
        mask = set(pool[i])
        trues = [p for p in q["points"] if p["answer"]]
        falses = [p for p in q["points"] if not p["answer"]]
        r2 = random.Random(args.seed * 7 + i)
        r2.shuffle(trues)
        r2.shuffle(falses)
        ti = fi = 0
        pts = []
        for slot in range(6):
            if slot in mask:
                pts.append(dict(trues[ti])); ti += 1
            else:
                pts.append(dict(falses[fi])); fi += 1
        out.append({"qid": q["qid"],
                    "mask": "".join("T" if s in mask else "F" for s in range(6)),
                    "conclusion_elements": q.get("conclusion_elements", []),
                    "points": pts})

    for q in out:
        assert "".join("T" if p["answer"] else "F" for p in q["points"]) == q["mask"]
        assert len(q["points"]) == 6
    cnt = collections.Counter(q["mask"] for q in out)
    slot_rate = [sum(1 for q in out if q["points"][s]["answer"]) for s in range(6)]
    n = len(out)
    print("题数 %d | 掩码种类 %d | 每种 %d~%d 次 | 最热掩码 %.1f%%"
          % (n, len(cnt), min(cnt.values()), max(cnt.values()), 100.0 * max(cnt.values()) / n))
    print("槽位真点计数（应各 ≈ %d）:" % (n // 2), slot_rate)
    bad = [s for s, v in enumerate(slot_rate) if abs(v - n / 2.0) > max(3, 0.08 * n)]
    if bad:
        print("⚠ 槽位偏斜：", bad)
    json.dump(out, open(args.dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("已写:", args.dst)


if __name__ == "__main__":
    main()
