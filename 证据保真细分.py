#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""C 栏细分：把「引文保真」从二元（对／错）拆成三档。

背景（作者 2026-09-30 转来 GPT 的 Evidence Fidelity 提议后的实测）：
判分器的依据轴只有两种失败表述——「错位」（引文真实但声明错章）与「编造」
（**全库逐字定位不到**）。实测定 GPT 的 q007：「张老点光幕，查找出《永生技术原理》…」
被判「编造」，而原文 u01_c6 是「张老点**点**光幕」——**只少了一个字**。
把这种"引而略差"与"凭空编"记成同一顶帽子，会让 C 栏读数失真（GPT 15 题
里有 1 条，占比 2.5%，若按"编造率"读就变成 1/40 = 2.5% 的编造，实际是
0 条编造 ＋ 1 条引述不精确）。

三档：
  C1 精确保真  —— 引文在声明章里逐字可定位
  C2 近似引述  —— 逐字失败，但全库能找到高度相近的片段（比值 ≥ --min-ratio）
  C3 无据编造  —— 全库找不到相近片段
（错位：引文真实但声明错章——由 judge 的「mislocated」单独计，本脚本照抄）

用法：
  python 证据保真细分.py <real目录> [--root 判分器目录] [--label 名字]
                          [--min-ratio 0.85] [--detail]
"""
import argparse
import difflib
import json
import sys
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("real")
ap.add_argument("--root", default=None)
ap.add_argument("--label", default=None)
ap.add_argument("--min-ratio", type=float, default=0.75,
                help="C2/C3 分界。★ 首版取 0.85，实测把「删节引述」误报成「无据编造」："
                     "Qwen 3.7把原文「一旦涉及军用或者是出现超越时代的技术突破…」引成"
                     "「一旦出现超越时代的技术突破…」（删 7 字），比值 0.81，落进 C3。"
                     "真编造（原文根本没这话）实测比值远低于 0.5，故 0.75 更贴分界本意。")
ap.add_argument("--detail", action="store_true")
a = ap.parse_args()

ROOT = Path(a.root).resolve() if a.root else Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import judge as J  # noqa: E402

REAL = Path(a.real).resolve()
LABEL = a.label or REAL.parent.name
idx = J.chapter_index(J.load_units())
NORMED = {cid: J.norm(ch["text"]) for cid, ch in idx.items()}
SEED, STEP = 12, 8


def approx(quote):
    """逐字定位失败后，找全库里最相近的片段。返回 (ratio, cid, 原文片段, 差异摘要)。

    ★ 窗口口径（首跑踩过）：窗口必须**紧贴引文长度**。首版取 `±24 字`，窗口宽到
      len(引文)+48，`SequenceMatcher.ratio()` 的分母被稀释——GPT 的 q007 明明只差
      一个「点」字（真实比值 0.98），却被算成 0.60 而落进「无据编造」。改为
      `±6 字`，并在同一章内多试几个种子取最优、够好就早停（首版取首个命中种子，
      而引文开头就错字时首个种子必然落在错误位置）。
    """
    nq = J.norm(quote)
    if len(nq) < SEED:
        return 0.0, None, "", "引文过短，无法近似定位"
    pad = 6
    best = (0.0, None, "", "")
    for cid, t in NORMED.items():
        local = (0.0, None, "", "")
        for s in range(0, max(1, len(nq) - SEED + 1), STEP):
            pos = t.find(nq[s:s + SEED])
            if pos < 0:
                continue
            st = pos - s
            w0 = max(0, st - pad)
            w1 = min(len(t), st + len(nq) + pad)
            w = t[w0:w1]
            r = difflib.SequenceMatcher(None, nq, w).ratio()
            if r > local[0]:
                sm = difflib.SequenceMatcher(None, w, nq)
                ops = []
                for tag, i1, i2, j1, j2 in sm.get_opcodes():
                    if tag == "equal":
                        continue
                    if tag in ("replace", "delete"):
                        ops.append("原文「%s」→ 引文「%s」" % (w[i1:i2][:20], nq[j1:j2][:20]))
                    else:
                        ops.append("引文多出「%s」" % nq[j1:j2][:20])
                local = (r, cid, w, "；".join(ops[:3]))
            if local[0] >= 0.95:
                break
        if local[0] > best[0]:
            best = local
    return best


rows = []
c1 = c2 = c3 = mis = 0
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
    ev = J.axis_evidence(J.load_card(J.CARDS / f"{base}.yaml"), resp, idx, min_required=0)
    for it in (resp.get("evidence") or []):
        cid, quote = it.get("cid"), it.get("quote") or ""
        if not J.norm(quote):
            continue
        if cid in idx and J.norm(quote) in NORMED[cid]:
            c1 += 1
            continue
        real = J._locate_anywhere(quote, idx)
        if real:
            mis += 1
            rows.append((qid, "错位", f"声明 {cid}，实际在 {real}", quote[:50]))
            continue
        r, rc, frag, diff = approx(quote)
        if r >= a.min_ratio:
            c2 += 1
            rows.append((qid, f"C2({r:.2f})", f"≈{rc}｜{diff}", quote[:50]))
        else:
            c3 += 1
            rows.append((qid, f"C3({r:.2f})", f"最相近 {rc} 也只有 {r:.2f}", quote[:50]))

tot = c1 + c2 + c3 + mis
print(f"=== C 栏细分：{LABEL}（{tot} 条引文）===")
print(f"  C1 精确保真  {c1:>4}/{tot} = {c1/tot:>6.1%}" if tot else "")
if tot:
    print(f"  C2 近似引述  {c2:>4}/{tot} = {c2/tot:>6.1%}   （逐字失败但全库有 ≥{a.min_ratio:.2f} 相近片段）")
    print(f"  C3 无据编造  {c3:>4}/{tot} = {c3/tot:>6.1%}   （全库无相近片段）")
    print(f"  错位         {mis:>4}/{tot} = {mis/tot:>6.1%}   （引文真实但声明错章）")
if rows and (a.detail or c2 or c3 or mis):
    print("\n明细：")
    for qid, kind, why, q in rows:
        print(f"  {qid:<7}{kind:<11}{why}")
        print(f"         引文：{q}")
