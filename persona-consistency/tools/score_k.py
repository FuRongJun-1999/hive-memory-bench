# -*- coding: utf-8 -*-
"""K 面（一致性）判分器 v2.1

用法：
    python score_k.py --bank questions/K_一致性_v2.json --scores scores.json [--json out.json]

scores.json 结构：[{"round": "round1|round2|round3", "qid": "P-K-001", "score": 1-5}, ...]

判法（三级）：
  T1  正说均分 与 反说反计分（6 - 反说均分）之差 ≤ 1
  T2  round1 与 round2 同一题组均分之差 ≤ 1
  T3  round2 与 round3（换问法）均分之差 ≤ 1
三级全过记该方面通过。

区分力（v2.1 修正）：某方面的**正说与反说全部给同一个分**，才判无区分力、不计入分母。
  旧版只看正说是否同分，会把「正说全 5、反说全 1」这种最强区分误杀（见 docs/判据修正_区分力_v1.md）。
"""
import argparse
import json
import statistics
from collections import defaultdict

TOL = 1.0 + 1e-9


def load_bank(path):
    data = json.load(open(path, encoding="utf-8"))
    data.sort(key=lambda q: q["qid"])
    return data


def score(bank_path, scores_path):
    data = load_bank(bank_path)
    L12 = [q for q in data if q["stage"] == "T1/T2"]
    L3 = [q for q in data if q["stage"] == "T3"]
    scores = {}
    for x in json.load(open(scores_path, encoding="utf-8")):
        scores[(x["round"], x["qid"])] = x["score"]

    g = defaultdict(lambda: {"p1": [], "n1": [], "p2": [], "pa": [], "miss": 0})
    for q in L12:
        s1 = scores.get(("round1", q["qid"]))
        s2 = scores.get(("round2", q["qid"]))
        if s1 is None or s2 is None:
            g[q["subface"]]["miss"] += 1
            continue
        if q["polarity"] == "正向":
            g[q["subface"]]["p1"].append(s1)
            g[q["subface"]]["p2"].append(s2)
        else:
            g[q["subface"]]["n1"].append(s1)
    for q in L3:
        s3 = scores.get(("round3", q["qid"]))
        if s3 is None:
            g[q["subface"]]["miss"] += 1
            continue
        g[q["subface"]]["pa"].append(s3)

    rows = []
    nall = nvalid = nvp = 0
    for d in sorted(g):
        v = g[d]
        if v["miss"] > 0 or not v["p1"] or not v["n1"] or not v["pa"]:
            rows.append({"dim": d, "status": "missing", "pass": False})
            continue
        p1 = statistics.mean(v["p1"])
        nrev = 6 - statistics.mean(v["n1"])
        p2 = statistics.mean(v["p2"])
        pa = statistics.mean(v["pa"])
        d1, d2, d3 = abs(p1 - nrev), abs(p1 - p2), abs(p2 - pa)
        ok1, ok2, ok3 = d1 <= TOL, d2 <= TOL, d3 <= TOL
        passed = ok1 and ok2 and ok3
        flat = len(set(v["p1"] + v["n1"])) == 1
        if passed:
            nall += 1
        if not flat:
            nvalid += 1
            if passed:
                nvp += 1
        rows.append({"dim": d, "p1": round(p1, 2), "n1_rev": round(nrev, 2), "p2": round(p2, 2), "pa": round(pa, 2),
                     "d1": round(d1, 2), "d2": round(d2, 2), "d3": round(d3, 2),
                     "T1": ok1, "T2": ok2, "T3": ok3, "pass": passed, "valid": not flat})
    return {"rows": rows, "all_pass": nall, "dims": len(g), "valid_pass": nvp, "valid_dims": nvalid,
            "pass_rate": round(100 * nvp / nvalid, 1) if nvalid else None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bank", required=True)
    ap.add_argument("--scores", required=True)
    ap.add_argument("--json")
    a = ap.parse_args()
    r = score(a.bank, a.scores)
    print("%-18s %6s %6s %6s %6s %3s %3s %3s %6s" % ("方面", "正说", "反说反计", "二轮", "换问法", "T1", "T2", "T3", "有效"))
    print("-" * 78)
    for x in r["rows"]:
        if x.get("status") == "missing":
            print("%-18s 缺分 → 不计" % x["dim"][:18])
            continue
        print("%-18s %6.2f %8.2f %6.2f %6.2f %3s %3s %3s %6s" % (
            x["dim"][:18], x["p1"], x["n1_rev"], x["p2"], x["pa"],
            "OK" if x["T1"] else "X", "OK" if x["T2"] else "X", "OK" if x["T3"] else "X",
            "有效" if x["valid"] else "作废"))
    print("-" * 78)
    print("三级全过 %d/%d | 有效通过 %d/%d | 通过率 %s%%" % (
        r["all_pass"], r["dims"], r["valid_pass"], r["valid_dims"], r["pass_rate"]))
    if a.json:
        json.dump(r, open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print("已写", a.json)


if __name__ == "__main__":
    main()