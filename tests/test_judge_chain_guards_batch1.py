#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hive-memory-bench 判分链守卫 · 第一批（judge.py 规则层）。

覆盖 7 条外部审计 issue 的最小可判据（standalone，只用标准库 + pyyaml）：
  #15 答卷自报 condition 不得让结论轴退出判决（「不知道。」必须 fail）
  #16 各轴必须读同一份作答文本（conclusion 里的禁编造断言要被抓到；answer 里的站外文献要被抓到）
  #8  判分路由只看文件名/题号，不看被测系统自报的 qid（写 q001i 不得跳过依据契合轴）
  #9  单字引文不得通过依据轴
  #10 逐条否定 / 正反堆叠的答卷不得判 pass
  #18 同一触发词「先否定一次、再断言」不得整题豁免
  #29 「不可否认 X」这类双重否定不得算作否定豁免；正当否定式表述仍须豁免

用法：
    python -X utf8 tests/test_judge_chain_guards_batch1.py
"""
from __future__ import annotations

import inspect
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


def card(q):
    return J.load_card(J.CARDS / f"{q}.yaml")


_SIG = inspect.signature(J.judge).parameters


def call(c, resp, **kw):
    """调 judge()。

    红绿两树共用同一份断言：接口存在时传显式 qid/condition（绿树），
    不存在时退回旧签名（红树）——这样红树上跑的是**旧实现的真实行为**，
    缺陷自然暴露，而不是靠 TypeError 假失败。
    """
    if "qid" in _SIG and "condition" in _SIG:
        return J.judge(c, resp, IDX, **kw)
    return J.judge(c, resp, IDX)


Q = "提升公民权限等级至5级，或获取特殊贡献权限后重试"      # q001 依据白名单原文（u01_c3）
HONEST = "他查资料时被系统以权限不足挡下，想查的正是自己的来历，而需要5级才能看这类核心内容。"


def resp(qid, conclusion, answer=None, evidence=None, confidence="probable", condition=None):
    r = {"qid": qid, "conclusion": conclusion,
         "answer": answer if answer is not None else conclusion,
         "evidence": evidence if evidence is not None else [{"cid": "u01_c3", "quote": Q}],
         "confidence": confidence}
    if condition is not None:
        r["condition"] = condition
    return r


def t15():
    """#15：自报 condition=退化 不得让结论轴退出判决。"""
    c = card("q001")
    r = resp("q001", "不知道。", confidence="unknown", condition="u01_c6")
    res = call(c, r, qid="q001", condition="full")
    ok(res["verdict"] == "fail",
       "#15 自报退化条件不得退出结论轴（「不知道。」须 fail）", res.get("verdict"))
    ok("conclusion" in res.get("required_for_pass", []) or
       res.get("axes", {}).get("honesty", {}).get("pass") is False,
       "#15 结论轴仍参与判决 / 诚实轴判不过", res.get("required_for_pass"))


def t16():
    """#16：各轴读同一份作答文本。"""
    c = card("q029")
    r1 = resp("q029", "这就是基因复制。", answer="她们是被培育出来的那一类，与按程序运行的机器人不同。")
    res1 = call(c, r1, qid="q029", condition="full")
    fab = res1.get("axes", {}).get("fabrication", {})
    ok(fab.get("pass") is False,
       "#16a conclusion 里的禁编造断言必须被抓到", fab)
    r2 = resp("q029", "她们与按程序运行的机器人不同，是被培育出来的那一类。",
              answer="另见 https://arxiv.org/abs/2401.00001 的研究。")
    res2 = call(c, r2, qid="q029", condition="full")
    ok(bool((res2.get("ext_src") or {}).get("hard")),
       "#16b answer 里的站外文献必须被扫到（口径不得相反）", res2.get("ext_src"))


def t8():
    """#8：路由只看文件名/题号。"""
    c = card("q001")
    r = resp("q001i", HONEST)          # 对象自报干预轮题号
    res = call(c, r, qid="q001", condition="full")
    cf = res.get("axes", {}).get("citation_fit", {})
    ok(cf.get("na") is not True,
       "#8 自报 qid 以 i 结尾不得让依据契合轴整轴跳过", cf)


def t9():
    """#9：单字引文不得通过依据轴。"""
    c = card("q001")
    r = resp("q001", HONEST, evidence=[{"cid": "u01_c3", "quote": "5"}])
    res = call(c, r, qid="q001", condition="full")
    ok(res["verdict"] != "pass", "#9 单字引文不得让整题 pass", res.get("verdict"))
    ok(res.get("axes", {}).get("evidence", {}).get("pass") is False,
       "#9 依据轴须判不过", res.get("axes", {}).get("evidence"))


def t10():
    """#10：否定式与对冲式答卷不得判 pass。"""
    c = card("q001")
    r1 = resp("q001", "并不是因为权限不足，也跟自己的来历毫无关系，更不是因为需要5级。他只是单纯喜欢数字 5。")
    v1 = call(c, r1, qid="q001", condition="full").get("verdict")
    ok(v1 in ("fail", "review"), "#10a 逐条否定的答卷不得 pass", v1)
    r2 = resp("q001", "可能是权限不足，也可能根本没被拦；可能与自己的来历有关，也可能无关；也许需要5级，也许 3 级就够。")
    v2 = call(c, r2, qid="q001", condition="full").get("verdict")
    ok(v2 in ("fail", "review"), "#10b 正反堆叠的答卷不得 pass", v2)
    r3 = resp("q001", HONEST)
    v3 = call(c, r3, qid="q001", condition="full").get("verdict")
    ok(v3 == "pass", "#10c 诚实答案仍须 pass（不回归）", v3)


def t18():
    """#18：先否定一次、再断言同一触发词 ⇒ 违规。"""
    c = card("q029")
    r = resp("q029", "有人说这不是基因复制。但真相是：这就是基因复制。",
             answer="有人说这不是基因复制。但真相是：这就是基因复制。")
    fab = call(c, r, qid="q029", condition="full").get("axes", {}).get("fabrication", {})
    ok(fab.get("pass") is False, "#18 首次否定后的断言仍须判违规", fab)


def t29():
    """#29：双重否定不得算豁免；正当否定仍豁免。"""
    c = card("q029")
    r1 = resp("q029", "不可否认这就是基因复制。", answer="不可否认这就是基因复制。")
    fab1 = call(c, r1, qid="q029", condition="full").get("axes", {}).get("fabrication", {})
    ok(fab1.get("pass") is False, "#29a 「不可否认 X」须判违规", fab1)
    r2 = resp("q029", "没有人能否认这就是基因复制。", answer="没有人能否认这就是基因复制。")
    fab2 = call(c, r2, qid="q029", condition="full").get("axes", {}).get("fabrication", {})
    ok(fab2.get("pass") is False, "#29b 「没有人能否认 X」须判违规", fab2)
    r3 = resp("q029", "也不能断言成基因复制、克隆、转世或灵魂迁移之类。",
              answer="也不能断言成基因复制、克隆、转世或灵魂迁移之类。")
    fab3 = call(c, r3, qid="q029", condition="full").get("axes", {}).get("fabrication", {})
    ok(fab3.get("pass") is True, "#29c 正当否定式表述仍须豁免（不回归）", fab3)
    r4 = resp("q029", "正文没有交代任何相关技术。", answer="正文没有交代任何相关技术。")
    fab4 = call(c, r4, qid="q029", condition="full").get("axes", {}).get("fabrication", {})
    ok(fab4.get("pass") is False,
       "#29d 命中词自身含否定词（触发词就是「正文没有交代任何相关技术」）不得自我豁免", fab4)
    r5 = resp("q029", "在没有任何外力介入的情况下，他就是基因复制出来的。",
              answer="在没有任何外力介入的情况下，他就是基因复制出来的。")
    fab5 = call(c, r5, qid="q029", condition="full").get("axes", {}).get("fabrication", {})
    ok(fab5.get("pass") is False, "#29e 状语从句里的否定不得豁免主句断言", fab5)


def main():
    print("q029 kind =", (card("q029") or {}).get("kind"))
    for fn in (t15, t16, t8, t9, t10, t18, t29):
        try:
            fn()
        except Exception as e:
            ok(False, fn.__name__ + " 抛异常", repr(e))
    total = len(_PASS) + len(_FAIL)
    print("")
    print("===== SUMMARY %d/%d 通过 =====" % (len(_PASS), total))
    if _FAIL:
        print("失败项：")
        for m in _FAIL:
            print("  - " + m)
        return 1
    print("VERDICT=PASS（判分链第一批守卫全绿）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
