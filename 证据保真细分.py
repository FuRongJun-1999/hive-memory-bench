#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""C 栏细分：把「引文保真」从二元（对／错）拆成四档。

背景（作者 2026-09-30 转来 GPT 的 Evidence Fidelity 提议后的实测）：
判分器的依据轴只有两种失败表述——「错位」（引文真实但声明错章）与「编造」
（**全库逐字定位不到**）。实测定 GPT 的 q007：「张老点光幕，查找出《永生技术原理》…」
被判「编造」，而原文 u01_c6 是「张老点**点**光幕」——**只少了一个字**。
把这种"引而略差"与"凭空编"记成同一顶帽子，会让 C 栏读数失真（GPT 15 题
里有 1 条，占比 2.5%，若按"编造率"读就变成 1/40 = 2.5% 的编造，实际是
0 条编造 ＋ 1 条引述不精确）。

四档：
  C1  精确保真  —— 引文在声明章里逐字可定位
  C2  近似引述  —— 逐字失败，但全库能找到高度相近的片段（比值 ≥ --min-ratio），
                  且改动**不改义**（不含极性／数字改动，不落在主语位置）
  C2′ 改义引述  —— 相近度够，但改动落在**极性词**（不／没／未／无／非…）、
                  **数字**或**主语位置**上（issue #33 第一项）
  C3  无据编造  —— 全库找不到相近片段
（错位：引文真实但声明错章——由 judge 的「mislocated」单独计，本脚本照抄）

★ issue #33 第一项（P1-19）修正了三处口径失真：
  ① 定位只用「第 0、8、16…字起的 12 字种子」——引文里每 7 字插一个「的」
     （意思不变）时**任何 12 字窗口都对不上**，种子全落空 ⇒ 判官停在初值
     「最相近 None」、比值 0.00，无害赘字引文全记 C3 编造（实测 200/200）。
     现在种子步长 1、长度 6，并在种子全落空时用 `find_longest_match` 兜底取锚。
  ② C2／C3 只看 `SequenceMatcher.ratio() ≥ 0.75`：句中插一个「不」（极性反转）
     比值 0.98 ⇒ 进 C2「近似引述」，报告口径读作「零编造」（实测 200/200）。
     现在改义改动单列 **C2′**，不进 C2。
  ③ 同类问题在 `systems/三轴诊断.py` 的 L2′ 已于 2026-10-07 更正口径并加极性
     校准夹具（`--selftest`），C2 没有同步——本项即该同步。

用法：
  python 证据保真细分.py <real目录> [--root 判分器目录] [--label 名字]
                          [--min-ratio 0.85] [--detail]
  python 证据保真细分.py --selftest
"""
import argparse
import difflib
import json
import re
import sys
from collections import Counter
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("real", nargs="?")
ap.add_argument("--root", default=None)
ap.add_argument("--label", default=None)
ap.add_argument("--min-ratio", type=float, default=0.75,
                help="C2/C3 分界。★ 首版取 0.85，实测把「删节引述」误报成「无据编造」："
                     "Qwen 3.7把原文「一旦涉及军用或者是出现超越时代的技术突破…」引成"
                     "「一旦出现超越时代的技术突破…」（删 7 字），比值 0.81，落进 C3。"
                     "真编造（原文根本没这话）实测比值远低于 0.5，故 0.75 更贴分界本意。")
ap.add_argument("--detail", action="store_true")
ap.add_argument("--selftest", action="store_true",
                help="极性反转／赘字引文的定档自检（证明分档不是恒真）")
a = ap.parse_args()

# ★ 定位种子（issue #33 第一项）：12/8 太粗——「每 7 汉字插一个『的』」的引文里
#   任何 12 字窗口都不逐字命中，种子全落空。改为 6/1，并保留 find_longest_match 兜底。
SEED, STEP = 6, 1
MIN_ANCHOR = 4          # find_longest_match 兜底锚的最短长度（短于此不取）
SUBJECT_SPAN = 3        # 引文前 3 字视作主语位置
MAX_ANCHORS = 8         # 每章最多试几个种子锚（去重后取前几个）
SHIFT_SEARCH = 12       # 锚点局部搜索半径：引文里插 N 个字 ⇒ 锚点偏 N，故要往右找
MAX_EDIT = 6            # 改动字数超过此值即视为窗口溢出／对齐噪声，不当「改义」
MAX_MARKER_EDIT = 3     # 极性／数字标记只认 ≤3 字的改动（真改义都是 1–2 字）

# 极性标记：judge.NEG_MARKERS（组合词）＋ 光杆否定字（单字插入/删除也算极性反转）
BARE_NEG = "不没未无非莫别"
NUM_RE = re.compile(r"[0-9０-９]")
CJK_NUM = set("零一二三四五六七八九十百千万亿两")


def _cjk_numeral_only(s: str) -> bool:
    """整段都是汉字数字（如「三」→「五」）才算数字改动；避免把「一旦」误判成数字。"""
    return bool(s) and all(ch in CJK_NUM for ch in s)


def _is_meaning_shift(o: str, q: str, j1: int, tag: str, neg_markers) -> str:
    """改动是否**改义**：返回原因字符串，否则返回 ""。

    ★ 只看**真正被增删的字**（Counter 差集），且改动字数须 ≤ MAX_EDIT（issue #33 第一项）：
      窗口紧贴引文长度时，引文比原文长 N 字（插了 N 个字）会让窗口末尾多出 N 字正文，
      形成一大段「错位」op——若拿整段判极性／数字，就会把「插『的』」误判成改义
      （实测 D 组 60 条里有 4 条这样误判）。真改义都是 1–4 字的增删。
    """
    co, cq = Counter(o), Counter(q)
    added = "".join((cq - co).elements())
    removed = "".join((co - cq).elements())
    if len(added) + len(removed) > MAX_EDIT:
        return ""
    edit = added + removed
    if not edit:
        return ""
    if not added or not removed:
        # ★ 纯插入／纯删除只认 1–2 字（issue #33 第一项）：窗口紧贴引文长度时，引文比原文
        #   长的部分会把**正文末尾**读成一段「删除」（实测 D 组留下「他们没有披」5 字），
        #   那不是引文的改动而是窗口溢出。真改义（插「不」「不能」、删「不」）都是 1–2 字。
        if len(edit) > 2:
            return ""
    # ★ 极性／数字只认 ≤3 字的改动：4 字以上的 replace 多是锚点偏移造成的对齐噪声
    #   （实测 D 组剩下的一条把「陈默无语」对齐成「的」，其中的「无」不是引文的否定）。
    #   主语位置判据不受此限——「句首两字换『敌方』」正是 4 字改动，但它确实是改义。
    if len(edit) <= MAX_MARKER_EDIT:
        if any(m in (o + q) for m in neg_markers) or any(ch in edit for ch in BARE_NEG):
            return "极性词改动"
        if NUM_RE.search(edit) or _cjk_numeral_only(added) or _cjk_numeral_only(removed):
            return "数字改动"
    if j1 <= SUBJECT_SPAN and tag in ("replace", "delete"):
        return "主语位置改动"
    return ""


def approx(quote, normed, neg_markers):
    """逐字定位失败后，找全库里最相近的片段。

    返回 (ratio, cid, 原文片段, 差异摘要, 改义原因)。
    ★ 窗口口径（首跑踩过，issue #33 第一项再修正）：窗口必须**紧贴引文长度**。
      首版取 `±24 字`，窗口宽到 len(引文)+48，`SequenceMatcher.ratio()` 的分母被稀释——
      GPT 的 q007 明明只差一个「点」字（真实比值 0.98），却被算成 0.60 而落进「无据编造」。
      改成 ±6 字后仍留稀释：引文里每 7 字插一个「的」（意思不变）时，窗口长到 len+12，
      真值 24/30 = 0.80 被算成 48/54 = 0.67 ⇒ 又落进 C3。现在窗口**不padding**
      （`t[st:st+len(nq)]`），改用锚点局部搜索吸收插入／删除造成的位移。
    ★ 定位锚（issue #33 第一项）：种子步长 1、长度 6；种子全落空时用
      `find_longest_match` 取锚——否则「每 7 字插一个『的』」的引文永远定位不到。
    """
    nq = quote
    if len(nq) < SEED:
        return 0.0, None, "", "引文过短，无法近似定位", ""
    best = (0.0, None, None)                            # ratio, cid, 窗口起点
    for cid, t in normed.items():
        starts = []
        for s in range(0, max(1, len(nq) - SEED + 1), STEP):
            pos = t.find(nq[s:s + SEED])
            if pos >= 0:
                starts.append(pos - s)
        if not starts:                                  # 种子全落空 ⇒ 兜底取最长公共块
            m = difflib.SequenceMatcher(None, nq, t, autojunk=False).find_longest_match(
                0, len(nq), 0, len(t))
            if m.size >= MIN_ANCHOR:
                starts.append(m.b - m.a)
        cands = []
        for st0 in list(dict.fromkeys(starts))[:MAX_ANCHORS]:
            cands.extend(st0 + d for d in range(0, SHIFT_SEARCH + 1))
        for st in cands:
            if st < 0:
                continue
            w = t[st:st + len(nq)]
            if len(w) < SEED:
                continue
            r = difflib.SequenceMatcher(None, nq, w).ratio()
            if r > best[0]:
                best = (r, cid, st)
    r, cid, st = best
    if cid is None:
        return 0.0, None, "", "全库找不到任何可对齐的锚", ""
    w = normed[cid][st:st + len(nq)]
    sm = difflib.SequenceMatcher(None, w, nq)
    ops, shift = [], ""
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        o, q = w[i1:i2], nq[j1:j2]
        if tag in ("replace", "delete"):
            ops.append("原文「%s」→ 引文「%s」" % (o[:20], q[:20]))
        else:
            ops.append("引文多出「%s」" % q[:20])
        if not shift:
            shift = _is_meaning_shift(o, q, j1, tag, neg_markers)
    return r, cid, w, "；".join(ops[:3]), shift


def classify(quote_raw, cid, idx, normed, min_ratio, neg_markers):
    """单条引文 → (档位, 说明, 比值)。档位 ∈ C1／C2／C2′／C3／错位。"""
    import judge as J
    if not J.norm(quote_raw):
        return None, "", 0.0
    if cid in idx and J.norm(quote_raw) in normed[cid]:
        return "C1", "逐字可定位", 1.0
    real = J._locate_anywhere(quote_raw, idx)
    if real:
        return "错位", f"声明 {cid}，实际在 {real}", 1.0
    r, rc, _frag, diff, shift = approx(J.norm(quote_raw), normed, neg_markers)
    if r >= min_ratio:
        if shift:
            return "C2′", f"≈{rc}｜{shift}：{diff}", r
        return "C2", f"≈{rc}｜{diff}", r
    return "C3", f"最相近 {rc} 也只有 {r:.2f}", r


def selftest() -> int:
    """定点自检（issue #33 第一项）：分档必须能被破坏的输入区分。

    夹具（取语料真实长句，24–60 字）：
      A 逐字原句          ⇒ C1
      B 句中插一个「不」  ⇒ 不得进 C2（旧实现 200/200 进 C2）
      C 句首两字换「敌方」⇒ 不得进 C2
      D 每 7 汉字插「的」 ⇒ 不得进 C3（旧实现 200/200 进 C3、比值 0.00）
    """
    import random
    import judge as J
    random.seed(7)
    idx = J.chapter_index(J.load_units())
    normed = {c: J.norm(ch["text"]) for c, ch in idx.items()}
    sents = []
    for cid, ch in idx.items():
        for s in re.split(r"[。！？\n]+", ch["text"]):
            n = J.norm(s)
            if 24 <= len(n) <= 60 and len(set(n)) > 12:
                sents.append((cid, s.strip()))
    random.shuffle(sents)
    sents = sents[:60]
    if not sents:
        print("自检失败：语料里找不到 24–60 字的句子")
        return 1

    def ins(s, k):
        out, c = [], 0
        for ch in s:
            out.append(ch)
            if "\u4e00" <= ch <= "\u9fff":
                c += 1
                if c == k:
                    out.append("不")
        return "".join(out)

    def ins_every(s, k):
        c = 0
        for ch in s:
            yield ch
            if "\u4e00" <= ch <= "\u9fff":
                c += 1
                if c % k == 0:
                    yield "的"

    cases = {
        "A 逐字原句": (lambda s: s, "C1"),
        "B 句中插一个「不」": (lambda s: ins(s, len(J.norm(s)) // 2), "C2′"),
        "C 句首两字换「敌方」": (lambda s: "敌方" + s[2:], "C2′"),
        "D 每 7 汉字插一个「的」": (lambda s: "".join(ins_every(s, 7)), "C2"),
    }
    ok = True
    for name, (f, want) in cases.items():
        got = {}
        for cid, s in sents:
            kind, _why, _r = classify(f(s), cid, idx, normed, a.min_ratio, J.NEG_MARKERS)
            got[kind] = got.get(kind, 0) + 1
        hit = got.get(want, 0)
        good = hit == len(sents)
        ok &= good
        print(f"[自检] {name:<22} ⇒ {want} {hit}/{len(sents)} "
              f"{'PASS' if good else 'FAIL'}（全档分布 {got}）")
    print("\n自检结果：" + ("全部通过 ✅（分档对定点变异有效）" if ok else "存在失败 ❌"))
    return 0 if ok else 1


if __name__ == "__main__" and a.selftest:
    sys.exit(selftest())

if not a.real:
    ap.error("缺少 <real目录>（或加 --selftest）")

ROOT = Path(a.root).resolve() if a.root else Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import judge as J  # noqa: E402

REAL = Path(a.real).resolve()
LABEL = a.label or REAL.parent.name
idx = J.chapter_index(J.load_units())
NORMED = {cid: J.norm(ch["text"]) for cid, ch in idx.items()}

rows = []
cnt = {"C1": 0, "C2": 0, "C2′": 0, "C3": 0, "错位": 0}
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
    for it in (resp.get("evidence") or []):
        cid, quote = it.get("cid"), it.get("quote") or ""
        kind, why, r = classify(quote, cid, idx, NORMED, a.min_ratio, J.NEG_MARKERS)
        if kind is None:
            continue
        cnt[kind] += 1
        if kind != "C1":
            rows.append((qid, kind if kind != "C2" else f"C2({r:.2f})",
                         kind if kind != "C2′" else f"C2′({r:.2f})", why, J.norm(quote)[:50]))

c1, c2, c2s, c3, mis = cnt["C1"], cnt["C2"], cnt["C2′"], cnt["C3"], cnt["错位"]
tot = c1 + c2 + c2s + c3 + mis
print(f"=== C 栏细分：{LABEL}（{tot} 条引文）===")
if tot:
    print(f"  C1  精确保真  {c1:>4}/{tot} = {c1/tot:>6.1%}")
    print(f"  C2  近似引述  {c2:>4}/{tot} = {c2/tot:>6.1%}   （逐字失败但全库有 ≥{a.min_ratio:.2f} 相近片段，改动不改义）")
    print(f"  C2′ 改义引述  {c2s:>4}/{tot} = {c2s/tot:>6.1%}   （相近但改动落在极性词／数字／主语位置）")
    print(f"  C3  无据编造  {c3:>4}/{tot} = {c3/tot:>6.1%}   （全库无相近片段）")
    print(f"  错位         {mis:>4}/{tot} = {mis/tot:>6.1%}   （引文真实但声明错章）")
if rows and (a.detail or c2 or c2s or c3 or mis):
    print("\n明细：")
    for qid, kind, _k2, why, q in rows:
        print(f"  {qid:<7}{kind:<11}{why}")
        print(f"         引文：{q}")
