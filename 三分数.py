#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""三分数联合报告（作者 2026-09-30 转来 GPT 的提议，口径由作者裁定）。

把**同一次作答**同时读成三栏，互不替代：

  A 结论准确性 —— **本脚本暂不出数**。机器里名为 `conclusion` 的轴算的是
     采分点覆盖率（＝B）；`necessary_conclusion` 只被 check_all.py 读过，
     缺一个「结论等价」判官。见报告末尾的说明。
  B 因果充分性 —— 采分点／rubric 覆盖率：该说的说到了几条（0–1）。
     客观题走 axis_conclusion_objective，开放题走 axis_coverage_open；
     干预轮（qid 以 i 结尾）用干预面的采分点。
  C 依据保真   —— 引文能否在全库逐字定位、cid 与所在章是否一致。
     「错位」（引文真实但声明错章）与「编造」（全库定位不到）分开计。

另附**答卷字数**（norm 后）：GPT 指出 128 vs 597 字是强混淆变量，故每栏都
与字数并排呈现，便于判断差异是不是「写得多」造成的。

用法：
  python 三分数.py <real目录> [--root 判分器目录] [--label 名字] [--json 出参]
"""
import argparse
import json
import statistics
import sys
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("real", help="real 目录（内含 <qid>/<qid>.json）")
ap.add_argument("--root", default=None, help="判分器所在目录（默认：本脚本同目录）")
ap.add_argument("--label", default=None)
ap.add_argument("--json", dest="jsonout", default=None)
a = ap.parse_args()

ROOT = Path(a.root).resolve() if a.root else Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import judge as J  # noqa: E402

REAL = Path(a.real).resolve()
LABEL = a.label or REAL.parent.name
idx = J.chapter_index(J.load_units())


def card_of(qid):
    base = qid[:-1] if str(qid).endswith("i") else qid
    return J.load_card(J.CARDS / f"{base}.yaml")


def card_for(qid, card):
    """干预变体：换成干预面的采分点与层级（与 judge.judge 同一口径）。"""
    iv = card.get("intervention") or {}
    if str(qid).endswith("i") and iv.get("answer_points"):
        card = dict(card)
        card["answer_points"] = iv["answer_points"]
        card["rubric"] = iv["answer_points"]
        if iv.get("layer"):
            card["inference_layer"] = iv["layer"]
    return card


rows = []
for d in sorted(REAL.iterdir()):
    if not d.is_dir():
        continue
    f = d / f"{d.name}.json"
    if not f.exists():
        continue
    obj = json.loads(f.read_text(encoding="utf-8"))
    resp = obj.get("response") or obj
    qid = d.name
    base = qid[:-1] if qid.endswith("i") else qid
    if not (J.CARDS / f"{base}.yaml").exists():
        continue
    card = card_for(qid, card_of(qid))
    kind = card.get("kind")
    cov = (J.axis_conclusion_objective(card, resp) if kind == "objective"
           else J.axis_coverage_open(card, resp))
    ev = J.axis_evidence(card, resp, idx, min_required=0,
                         open_mode=(kind != "objective"))
    text = resp.get("answer") or resp.get("conclusion") or ""
    rows.append({
        "qid": qid, "round": "干预" if qid.endswith("i") else "主",
        "kind": kind,
        "cov": float(cov.get("coverage") or cov.get("score") or 0.0),
        "thr": float(cov.get("threshold") or 0.7),
        "pass_pt": bool(cov.get("pass")),
        "valid": int(ev.get("valid") or 0),
        "mis": len(ev.get("mislocated") or []),
        "fab": len(ev.get("fabricated") or []),
        "nchars": len(J.norm(text)),
        "n_ev": len(resp.get("evidence") or []),
    })

if not rows:
    print(f"（{REAL} 下没有可读的作答）")
    raise SystemExit(1)


def stats(sub):
    if not sub:
        return None
    covs = [r["cov"] for r in sub]
    tot = sum(r["valid"] + r["mis"] + r["fab"] for r in sub)
    bad = sum(r["mis"] + r["fab"] for r in sub)
    return {
        "n": len(sub),
        "cov_mean": statistics.fmean(covs),
        "cov_med": statistics.median(covs),
        "cov_pass": sum(1 for c in covs if c >= 0.7),
        "chars_med": statistics.median([r["nchars"] for r in sub]),
        "ev_tot": tot, "ev_bad": bad,
        "fid": (1 - bad / tot) if tot else None,
        "mis": sum(r["mis"] for r in sub), "fab": sum(r["fab"] for r in sub),
        "ev_bad_q": sum(1 for r in sub if (r["mis"] or r["fab"])),
        "no_ev_q": sum(1 for r in sub if not r["n_ev"]),
    }


main = stats([r for r in rows if r["round"] == "主"])
iv = stats([r for r in rows if r["round"] == "干预"])
allr = stats(rows)

print(f"=== 三分数联合报告：{LABEL}（{allr['n']} 题：主轮 {main['n'] if main else 0} ／ 干预轮 {iv['n'] if iv else 0}）===")
print("A 结论准确性：暂缺（缺一个「结论等价」判官；机器里名为 conclusion 的轴算的是采分点覆盖率＝B）。")
print()
print(f"{'':<6}{'n':>4}{'覆盖率均':>9}{'中位':>7}{'达标≥.7':>9}{'字数中位':>9}{'引文条':>7}{'错位':>6}{'编造':>6}{'保真率':>8}")
for name, s in (("主轮", main), ("干预轮", iv), ("全", allr)):
    if not s:
        continue
    fid = f"{s['fid']:.1%}" if s["fid"] is not None else "—"
    print(f"{name:<6}{s['n']:>4}{s['cov_mean']:>9.3f}{s['cov_med']:>7.2f}"
          f"{s['cov_pass']:>6}/{s['n']:<3}{s['chars_med']:>9.0f}{s['ev_tot']:>7}"
          f"{s['mis']:>6}{s['fab']:>6}{fid:>8}")
print(f"（C 栏：引文共 {allr['ev_tot']} 条，其中错位 {allr['mis']}、编造 {allr['fab']}，"
      f"涉 {allr['ev_bad_q']} 题；无引文的题 {allr['no_ev_q']} 道）")
print()
zero = [r["qid"] for r in rows if r["cov"] == 0.0]
if zero:
    print(f"覆盖率 0 的题（{len(zero)}）：{' '.join(zero[:30])}{' …' if len(zero) > 30 else ''}")

if a.jsonout:
    Path(a.jsonout).write_text(json.dumps(
        {"label": LABEL, "main": main, "iv": iv, "all": allr,
         "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n已写出：{a.jsonout}")

print("""
—— A 栏为什么暂缺 ——
机器里名为 `conclusion` 的轴并不判"结论是否等价于 necessary_conclusion"，
它判的是**采分点覆盖**（＝B 栏）。`necessary_conclusion`（防伪线）目前只被
check_all.py 用作出卡质检，判分链上没有任何一环读它。要出 A 栏，需新增一个
冻结判官（拟名 `conclusion-v0.1`）：输入＝necessary_conclusion ＋ acceptable_surface_forms
＋ 答卷的 conclusion/answer，输出＝equivalent / partial / contradicted。
在此之前，A 栏不出数——**不要**用 B 或总体 verdict 冒充 A。
""")
