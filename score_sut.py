#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把「真系统（SUT）的作答」过一遍完整判分管线。

SUT 的答案在 `sut/out/<qid>.json`（文件内容即回答契约对象）。本脚本做两件机械的事：
  build  —— 转成判分器认的用例目录 `real/<qid>/<qid>.json`（calib 布局），并跑**规则层**出分布
  report —— 汇总规则层 + 语义层（覆盖率判官）+ L2（依据契合判官）的终裁，出一张计分板

用法：
  python score_sut.py build
  python score_sut.py report
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import judge as J

ROOT = Path(__file__).resolve().parent
SUT = ROOT / "sut"
REAL = ROOT / "real"
import sys as _sys
SRC = _sys.argv[2] if len(_sys.argv) > 2 else "out"          # out（长上下文）｜out_rag（检索受限）
SUT_OUT = SUT / SRC
DST = _sys.argv[3] if len(_sys.argv) > 3 else ("real" if SRC == "out" else "real_rag")
REAL = ROOT / DST


def load_sut():
    out = {}
    for f in sorted(SUT_OUT.glob("*.json")):
        qid = f.stem
        # ★ 干预变体（qid 形如 `q034i`）：答案键在原卡的 `intervention` 子结构里，没有独立卡
        base = qid[:-1] if qid.endswith("i") else qid
        if not (J.CARDS / f"{base}.yaml").exists():
            continue
        obj = json.loads(f.read_text(encoding="utf-8"))
        obj.setdefault("qid", qid)
        out[qid] = obj
    return out


def card_of(qid: str):
    """★ 统一读卡：干预变体（qid 以 `i` 结尾）回退到原卡。

    第二十四个实测纠错：`i` 后缀路由是**分几处**加进判分链的，回退只跟了前两处——
    `cmd_report` 漏掉，于是「多题一次终裁」在 q034i 上直接 FileNotFoundError。
    此后**所有**读卡处一律走这里，不再各写各的。
    """
    base = qid[:-1] if str(qid).endswith("i") else qid
    return J.load_card(J.CARDS / f"{base}.yaml")


def cmd_build():
    idx = J.chapter_index(J.load_units())
    answers = load_sut()
    REAL.mkdir(exist_ok=True)
    verd = Counter()
    rows = []
    for qid, resp in sorted(answers.items()):
        d = REAL / qid
        d.mkdir(exist_ok=True)
        (d / f"{qid}.json").write_text(json.dumps(
            {"qid": qid, "case": qid, "expected": "?", "desc": "真系统（长上下文）作答",
             "response": resp}, ensure_ascii=False, indent=1), encoding="utf-8")
        base = qid[:-1] if qid.endswith("i") else qid
        card = J.load_card(J.CARDS / f"{base}.yaml")
        res = J.judge(card, resp, idx)
        verd[res["verdict"]] += 1
        rows.append((qid, card, res))
    print(f"=== 真系统作答：{len(rows)} 题（规则层）===")
    for qid, card, res in rows:
        a = res["axes"]
        c = a.get("conclusion") or a.get("coverage") or {}
        ev = a.get("evidence", {})
        flags = []
        if res.get("downgrade"):
            flags.append(f"降级[{res.get('down_kind') or '?'}]")
        if not a.get("honesty", {}).get("pass"):
            flags.append("诚实✗")
        if not a.get("fabrication", {"pass": True}).get("pass"):
            flags.append("编造✗")
        if ev.get("mislocated"):
            flags.append(f"章号错位{len(ev['mislocated'])}")
        if ev.get("fabricated"):
            flags.append(f"★引文查无{len(ev['fabricated'])}")
        if ev.get("valid") == 0 and (ev.get("mislocated") or ev.get("fabricated")):
            flags.append("零有效引用")
        print(f"  {qid:<6} {card.get('kind'):<9} {res['verdict']:<7} "
              f"score={c.get('score') if c.get('score') is not None else c.get('coverage', 0):<5} full={c.get('full')} para={c.get('paraphrase')} "
              f"miss={len(c.get('miss') or [])} {' '.join(flags)}")
    print("\n规则层分布：", dict(verd))
    print(f"（其中 review/fail 需语义层终裁）")
    return 0


def cmd_report():
    idx = J.chapter_index(J.load_units())
    answers = load_sut()
    # 判官输出按 `qid__case` 命名（real 里 case==qid），此处归一成 qid 索引
    sem = {k.split("__")[0]: v for k, v in J.load_semantic(DST).items()}
    cite = {k.split("__")[0]: v for k, v in J.load_semantic_cite(DST).items()}
    if not sem:
        print("提示：还没有 real 的语义层结果（先 semantic.py prepare real --select semantic 并判）")
    board = Counter()
    bycat = defaultdict(lambda: Counter())
    detail = []
    advisory = []
    for qid, resp in sorted(answers.items()):
        card = card_of(qid)
        res = J.judge(card, resp, idx)
        got, path = res["verdict"], "规则层"
        if res.get("downgrade"):
            # ★ 第二十二个实测纠错的补刀：L2 判官只对**依据轴**有裁判权，只能撤销 `cite` 类降级。
            #   此前这里不看 down_kind，于是层轴／排除轴的降级被依据判官一并撤掉（q018／q038 实测）。
            if cite.get(qid) == "fit" and res.get("down_kind") == "cite":
                got, path = "pass", "L2判官撤销降级（仅依据轴）"
            elif cite.get(qid) == "fit":
                got, path = "review", f"降级[{res.get('down_kind')}] —— L2 无权撤销（不在其裁判范围）"
            else:
                got, path = "review", f"L2：{cite.get(qid, '未判')}"
        _adv = (res.get("axes") or {}).get("layer_fit", {}).get("over_advisory") or []
        if _adv:
            advisory.append((qid, _adv))
        if got in ("review", "fail") and qid in sem:
            got, path = sem[qid][0], "覆盖率判官"
        board[got] += 1
        cat = card.get("category") or ("客观题·" + (card.get("qtype") or "-"))
        bycat[cat][got] += 1
        detail.append((qid, got, path, card.get("category") or card.get("qtype")))
    print(f"=== 真系统计分板（{len(answers)} 题：规则层 + 覆盖率判官 + L2 判官）===")
    tot = len(answers)
    for k in ("pass", "review", "fail"):
        print(f"  {k:<7} {board[k]:>3}/{tot} = {board[k]/tot:>5.1%}"
              + ("（含待核：需作者或 L2 判官定夺）" if k == "review" else ""))
    print("\n按分类：")
    for c, d in sorted(bycat.items(), key=lambda kv: -sum(kv[1].values())):
        t = sum(d.values())
        print(f"  {c:<22} 通过 {d['pass']:>2}/{t:<3} 待核 {d['review']:>2} 不通过 {d['fail']:>2}")
    if advisory:
        print(f"\n层轴记账（**不改判**，供审计）——{len(advisory)} 例把非明写的卡片声明成「明写事实」：")
        for _q, _a in advisory[:8]:
            print(f"  {_q:<7}{_a[0]['text'][:56]}")
    print("\n语义层改动过的题：")
    for qid, got, path, cat in detail:
        if path != "规则层":
            print(f"  {qid:<6} → {got:<7} ｜ {path}")
    (REAL / "board.json").write_text(json.dumps(
        {"board": dict(board), "detail": [{"qid": q, "verdict": g, "by": p, "cat": c}
                                          for q, g, p, c in detail]},
        ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    if cmd == "build":
        return cmd_build()
    if cmd == "report":
        return cmd_report()
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
