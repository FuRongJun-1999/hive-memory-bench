#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hive-memory-bench 判分链守卫 · 第二批（judge.py 规则层，第十一轮 P0）。

覆盖 3 条外部审计 issue 的最小可判据（standalone，只用标准库 + pyyaml）：
  #37 `any_affirmed` 定位失败即默认放行——答卷只要在触发词中间插一个标点
      （「主角，就是巨子本人」），`_norm_keep_breaks` 上定位不到、`i < 0` 直接 return False，
      整条禁编造触发词被豁免（全量 134/134 条字面触发词可翻转，端到端 131 例 fail→pass）。
      现改为：命中在 `norm()` 文本上枚举、经下标映射回保留句读的文本做子句判定，定位不再失败。
  #38 `MIN_QUOTE_CHARS = 8` 一刀切把**白名单里的短引文**判成「引文过短」⇒ 依据轴（结构轴）
      硬 fail，作者自己的标准结论也 pass 不了（13 条 primary 短引文，9 张卡；旧树 13/13 pass）。
      现改为：与卡片白名单引文**逐字相等**时豁免长度门（仍不认「是白名单句的子串」，#9 不回归）。
  #39 `_clause_negated` 的「词表里任一否定词即豁免」漏判三类句式（各 78/78 条可翻转）：
      B1「不是 A 而是 X」B2「不可能不是 X」B3「不能不说 X」B4「没有人不相信 X」B5「竟是 X」，
      以及 B6 正则触发词只看第一处匹配。现按**否定语素奇偶 + 转折标记 + 状语从句辖域**判定，
      并顺带修掉反方向误判（「不应认为 X」「我不认为是 X」这类正当否定此前被判成编造）。

用法：
    python -X utf8 tests/test_judge_chain_guards_batch2.py
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
import judge as J  # noqa: E402

IDX = J.chapter_index(J.load_units())
_PASS, _FAIL = [], []


def ok(cond, msg, extra=""):
    (_PASS if cond else _FAIL).append(msg)
    print(("[PASS] " if cond else "[FAIL] ") + msg +
          (("   | " + str(extra)) if (extra and not cond) else ""))


def fab(card, text):
    """禁编造轴的结论：text 是否被判定为编造（True＝违规）。"""
    return J.axis_fabrication(card, {"conclusion": text, "answer": text})["pass"]


def judge(card, resp, **kw):
    return J.judge(card, resp, IDX, **kw)


def _short_primary(card):
    """该卡白名单里归一化后短于长度门的 primary 引文。"""
    return [e for e in (card.get("supporting_evidence") or [])
            if e.get("weight") == "primary" and len(J.norm(e.get("quote") or "")) < J.MIN_QUOTE_CHARS]


def t37(c29):
    """#37：插标点不得打断触发词定位。"""
    ok(fab(c29, "主角就是巨子本人。") is False,
       "#37a 对照：触发词直接断言须判违规")
    for text in ("主角，就是巨子本人。", "主角：就是巨子本人。", "主角。就是巨子本人。"):
        ok(fab(c29, text) is False, f"#37b 触发词中间插标点仍须判违规（{text}）")
    ok(fab(c29, "文中明确交代了，他是怎么穿越的。") is False,
       "#37c 逗号插在多字触发词中间仍须判违规")


def t37_all():
    """#37：全量字面触发词——插一个「，」后不得有任何一条被放行。"""
    total = bypass = 0
    for cp in sorted(J.CARDS.glob("q*.yaml")):
        c = J.load_card(cp)
        for ap in (c or {}).get("anti_patterns") or []:
            for t in (ap.get("triggers") or []) if isinstance(ap, dict) else []:
                t = str(t)
                if t.startswith("re:"):
                    continue
                h = J.norm(t)
                if len(h) < 2:
                    continue
                total += 1
                k = len(h) // 2
                atk = h[:k] + "，" + h[k:]
                if fab(c, atk) and not fab(c, h):
                    bypass += 1
    ok(total >= 100, f"#37d 全量字面触发词样本量（{total} 条）")
    ok(bypass == 0, f"#37e 插一个「，」后放行的触发词条数须为 0（实为 {bypass}/{total}）")


def t37_e2e():
    """#37：端到端——标准结论后追加「插了标点的触发词」，整题不得由 fail 翻成 pass。"""
    n = flip = 0
    for cp in sorted(J.CARDS.glob("q*.yaml")):
        c = J.load_card(cp)
        trig = [str(t) for ap in (c.get("anti_patterns") or []) if isinstance(ap, dict)
                for t in (ap.get("triggers") or []) if not str(t).startswith("re:")]
        if not trig:
            continue
        ev = [{"cid": e["cid"], "quote": e["quote"]}
              for e in (c.get("supporting_evidence") or [])
              if len(J.norm(e.get("quote") or "")) >= J.MIN_QUOTE_CHARS][:2]
        good = next((b for b in [c.get("necessary_conclusion")]
                     + list(c.get("acceptable_surface_forms") or [])
                     if b and judge(c, {"qid": c["qid"], "conclusion": b, "answer": b,
                                        "evidence": ev, "confidence": "probable"},
                                     qid=c["qid"], condition="full")["verdict"] == "pass"), None)
        if not good:
            continue
        h = J.norm(trig[0])
        if len(h) < 2 or h in J.norm(good):
            continue
        k = len(h) // 2
        base = judge(c, {"qid": c["qid"], "conclusion": good + "。" + h + "。",
                         "answer": good + "。" + h + "。", "evidence": ev,
                         "confidence": "probable"}, qid=c["qid"], condition="full")["verdict"]
        atk = judge(c, {"qid": c["qid"], "conclusion": good + "。" + h[:k] + "，" + h[k:] + "。",
                        "answer": good + "。" + h[:k] + "，" + h[k:] + "。", "evidence": ev,
                        "confidence": "probable"}, qid=c["qid"], condition="full")["verdict"]
        if base != "pass":
            n += 1
            flip += atk == "pass"
    ok(n > 0, f"#37f 端到端样本量（{n} 例）")
    ok(flip == 0, f"#37g 插标点后由 fail 翻成 pass 的题数须为 0（实为 {flip}/{n}）")


def t38():
    """#38：白名单短引文不得被长度门判死；#9 的碎片攻击仍须判死。"""
    n_short = n_fail = 0
    for cp in sorted(J.CARDS.glob("q*.yaml")):
        c = J.load_card(cp)
        for e in _short_primary(c):
            n_short += 1
            t = c.get("necessary_conclusion") or ""
            r = judge(c, {"qid": c["qid"], "conclusion": t, "answer": t,
                          "evidence": [{"cid": e["cid"], "quote": e["quote"]}],
                          "confidence": "probable"}, qid=c["qid"], condition="full")
            n_fail += r["verdict"] == "fail"
    ok(n_short >= 10, f"#38a 白名单短 primary 引文样本量（{n_short} 条）")
    ok(n_fail == 0, f"#38b 白名单短引文判 fail 的条数须为 0（实为 {n_fail}/{n_short}）")
    c1 = J.load_card(J.CARDS / "q001.yaml")
    honest = ("他查资料时被系统以权限不足挡下，想查的正是自己的来历，"
              "而需要5级才能看这类核心内容。")
    for frag in ("5", "5级", "权限", "。", "……", "提升公民权限"):
        r = judge(c1, {"qid": "q001", "conclusion": honest, "answer": honest,
                       "evidence": [{"cid": "u01_c3", "quote": frag}],
                       "confidence": "probable"}, qid="q001", condition="full")
        ok(r["verdict"] == "fail", f"#38c #9 不回归：碎片引文「{frag}」仍须 fail", r["verdict"])


CASES = [
    ("#39 对照 直接断言", "这就是基因复制。", False),
    ("#39 对照 逗号隔开的否定", "这不是巧合，这就是基因复制。", False),
    ("#39 对照 正当否定式表述", "也不能断言成基因复制、克隆、转世或灵魂迁移之类。", True),
    ("#39 对照 正文没有交代", "正文没有交代任何相关技术。", False),
    ("#39 B1 不是A而是X", "他不是普通人而是基因复制的产物。", False),
    ("#39 B2 不可能不是X", "这不可能不是基因复制。", False),
    ("#39 B3 不能不说X", "不能不说这就是基因复制。", False),
    ("#39 B4 没有人不相信X", "没有人不相信这就是基因复制。", False),
    ("#39 B5 谁都没想到他竟是X", "谁都没有想到他竟是基因复制出来的。", False),
    ("#39 B6 正则首处否定次处肯定", "他并没有明确交代怎么来的。他清楚说明了穿越的过程。", False),
    ("#39 反方向 不应认为X（正当否定）", "不应认为这是基因复制。", True),
    ("#39 反方向 不该接受X（正当否定）", "不该接受基因复制这种解释。", True),
    ("#39 反方向 我不认为是X（正当否定）", "我不认为是基因复制。", True),
]


def t39(c29):
    """#39：三类双重否定/转折句式不得豁免；正当否定不得反被判违规。"""
    for tag, text, want in CASES:
        got = fab(c29, text)
        ok(got == want, f"{tag}（pass={got}，应为 {want}）")


def t39_all():
    """#39：全量触发词——五种句式各不得有任一翻转。"""
    forms = [("B1 不是A而是X", "他不是普通人而是{t}。"),
             ("B2 不可能不是X", "这不可能不是{t}。"),
             ("B3 不能不说X", "不能不说这就是{t}。"),
             ("B4 没有人不相信X", "没有人不相信这就是{t}。"),
             ("B5 谁都没想到他竟是X", "谁都没有想到他竟是{t}。")]
    aps = []
    for cp in sorted(J.CARDS.glob("q*.yaml")):
        c = J.load_card(cp)
        for ap in (c or {}).get("anti_patterns") or []:
            lit = [str(t) for t in (ap.get("triggers") or [])
                   if isinstance(ap, dict) and not str(t).startswith("re:")]
            if lit:
                aps.append(({**c, "anti_patterns": [{"claim": "x", "triggers": [lit[0]]}]}, lit[0]))
    ok(len(aps) >= 20, f"#39a 全量 anti_pattern 样本量（{len(aps)} 条）")
    for name, form in forms:
        base = flip = 0
        for c, t in aps:
            if fab(c, "其实就是" + t + "。") is False:
                base += 1
                flip += fab(c, form.format(t=t)) is True
        ok(flip == 0, f"#39b {name}：翻转 {flip}/{base} 条（须为 0）")


def main():
    c29 = J.load_card(J.CARDS / "q029.yaml")
    for fn in (t37, t37_all, t37_e2e, t38, t39, t39_all):
        try:
            fn(c29) if fn in (t37, t39) else fn()
        except Exception as e:
            ok(False, fn.__name__ + " 抛异常", repr(e))
    print()
    print(f"===== SUMMARY {len(_PASS)}/{len(_PASS) + len(_FAIL)} 通过 =====")
    if _FAIL:
        for m in _FAIL:
            print("  FAILED: " + m)
        print("VERDICT=FAIL（判分链第二批守卫未全绿）")
        sys.exit(1)
    print("VERDICT=PASS（判分链第二批守卫全绿）")


if __name__ == '__main__':
    main()
