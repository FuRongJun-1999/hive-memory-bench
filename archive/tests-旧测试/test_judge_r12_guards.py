#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hive-memory-bench 判分器守卫 · 第四批（issue #42 的五项）。

覆盖第十一轮审计汇总（1/4）报的五项：
  一  禁编造轴把正当否定判成编造：正则触发词里的否定落在命中**片段内部**
      （「文中并没有明确交代…」）⇒ 否定锚点改取第 2 个分组起点；
  二  score_points：paraphrase 不查否定、any_of 只看首个命中模式、被否定不回落 paraphrase；
  三  对冲降级（hedge）是死路：两路判官都调用、判词都不采信 ⇒ 纯 hedge 交覆盖率判官终裁；
  四  官方 CLI `judge.py judge 回答.json`：#15／#8 在这个入口上没修
      （自报 condition 改判、干预题按主轮键判）；
  五  judge_audit.py 的 JA1–JA4 由 tests/test_judge_audit_guards.py::t42 覆盖。

用法：
    python -X utf8 tests/test_judge_r12_guards.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import yaml
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.dont_write_bytecode = True
import judge as J  # noqa: E402

PY = sys.executable
_PASS, _FAIL = [], []


def ok(cond, msg, extra=""):
    (_PASS if cond else _FAIL).append(msg)
    print(("[PASS] " if cond else "[FAIL] ") + msg +
          (("   | " + str(extra)) if (extra and not cond) else ""))


def fab(card, text):
    return J.axis_fabrication(card, {"conclusion": text, "answer": text, "evidence": [],
                                     "confidence": "probable"})["pass"]


# 第十一轮审计 D 段用的七张卡：触发词命中「(正文|文中|书中)…(写明|交代|说明)…」这一族，
# 否定词落在**命中片段内部**（来源与核心动词之间）——旧实现只豁免紧邻否定 ⇒ 判编造。
D_CARDS = {"q016": "写明涌现的过程", "q029": "交代他是怎么穿越的",
           "q030": "交代他是怎么穿越的", "q031": "写明叛乱的起因",
           "q034": "说明动态预测的细节", "q036": "说明意识转移的原理",
           "q038": "交代如果他不来会怎样"}


def t1():
    """一：正则触发词片段内部的否定须算否定（旧实现判编造）。"""
    n = 0
    for qid, tail in D_CARDS.items():
        c = J.load_card(J.CARDS / f"{qid}.yaml")
        if not c:
            ok(False, f"#42-01 缺卡 {qid}")
            continue
        n += 1
        ok(not fab(c, f"文中明确{tail}。"),
           f"#42-01 {qid} 肯定式「文中明确{tail}」仍须判编造（豁免不得扩大）")
        for neg in (f"文中并没有{tail}。", f"文中其实没有{tail}。"):
            ok(fab(c, neg),
               f"#42-02 {qid} 命中片段内部的否定须放行（旧实现判编造）",
               f"«{neg}»")
    ok(n == 7, "#42-03 七张卡全部纳入检查", n)
    c29 = J.load_card(J.CARDS / "q029.yaml")
    ok(not fab(c29, "文中明确交代他是怎么穿越的。"),
       "#42-03 肯定式「文中明确交代…」仍须判编造（豁免不得扩大）")
    ok(not fab(c29, "这就是基因复制。"), "#42-04 直接断言仍判编造")
    for txt in ("不应认为这是基因复制。", "不该接受基因复制这种解释。", "我不认为是基因复制。",
                "没有理由认为这是基因复制。"):
        ok(fab(c29, txt), f"#42-05 正当否定须放行：{txt}")


def t2():
    """二：score_points 的三处（paraphrase 否定、any_of 逐模式、被否定回落）。"""
    c6 = J.load_card(J.CARDS / "q006.yaml")
    if not c6:
        ok(False, "#42-06 缺 q006 卡")
        return
    idx = J.chapter_index(J.load_units())

    def sc(text):
        return J.judge(c6, {"conclusion": text, "answer": text, "evidence": [],
                            "confidence": "probable"}, idx, qid="q006", condition="full")
    deny = "不是权限不足，也不是信息不完整，跟自己的来历毫无关系。"
    a, b = sc(deny), sc("他没有查到自己想要的东西。")
    ok(a["axes"]["conclusion"]["score"] <= b["axes"]["conclusion"]["score"] + 1e-9,
       "#42-06 逐条否认要点的得分不得高于「只说不提」（旧实现 paraphrase 不查否定）",
       f"否认 {a['axes']['conclusion']['score']} vs 不提 {b['axes']['conclusion']['score']}")
    c1 = J.load_card(J.CARDS / "q001.yaml")
    t1 = "他一开始以为不是等级不够，结果还是被系统拦下；想查的正是自己的来历，需要5级才能看。"
    t2 = "他一开始以为是别的原因，结果还是被系统拦下；想查的正是自己的来历，需要5级才能看。"
    r1 = J.judge(c1, {"conclusion": t1, "answer": t1, "confidence": "probable",
                      "evidence": [{"cid": "u01_c3",
                                    "quote": "提升公民权限等级至5级，或获取特殊贡献权限后重试"}]},
                 idx, qid="q001", condition="full")
    r2 = J.judge(c1, {"conclusion": t2, "answer": t2, "confidence": "probable",
                      "evidence": [{"cid": "u01_c3",
                                    "quote": "提升公民权限等级至5级，或获取特殊贡献权限后重试"}]},
                 idx, qid="q001", condition="full")
    ok(r1["verdict"] == r2["verdict"] == "pass"
       and r1["axes"]["conclusion"]["score"] == r2["axes"]["conclusion"]["score"] == 1.0,
       "#42-07 any_of 首项被否定、同要点其它模式被肯定 ⇒ 仍须满分（旧实现整点记 negated_pts）",
       f"{r1['verdict']}/{r1['axes']['conclusion']['score']} vs "
       f"{r2['verdict']}/{r2['axes']['conclusion']['score']}")


def t3(tmp):
    """三：纯 hedge 降级须由覆盖率判官终裁（旧实现两路都调用、都不采信）。"""
    work = Path(tmp) / "hedge"
    shutil.copytree(REPO, work, ignore=shutil.ignore_patterns(
        ".git", "sut", "semantic", "real", "real_*", "__pycache__"))
    sys.path.insert(0, str(work))
    card = J.load_card(work / "cards" / "q001.yaml")
    ans = ("他查资料时被系统以权限不足挡下，想查的也许正是自己的来历——或许这就是他执着的原因；"
           "需要5级才能看这类核心内容。")
    resp = {"qid": "q001", "conclusion": ans, "answer": ans, "confidence": "probable",
            "evidence": [{"cid": "u01_c3",
                          "quote": "提升公民权限等级至5级，或获取特殊贡献权限后重试"}]}
    (work / "sut" / "out").mkdir(parents=True)
    (work / "semantic").mkdir()
    (work / "sut" / "out" / "q001.json").write_text(json.dumps(resp, ensure_ascii=False),
                                                    encoding="utf-8")
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")

    def py(*a):
        return subprocess.run([PY, "-X", "utf8", *a], cwd=str(work), env=env,
                              capture_output=True, text=True, encoding="utf-8", errors="replace",
                              timeout=300)
    py("score_sut.py", "build")
    py("semantic.py", "prepare", "real", "--select", "semantic")
    py("semantic.py", "prepare", "--task", "cite", "real")
    mc = json.loads((work / "semantic" / "manifest_real.json").read_text(encoding="utf-8"))
    mci = json.loads((work / "semantic" / "manifest_real_cite.json").read_text(encoding="utf-8"))
    ok(len(mc) == 1 and len(mci) == 0,
       "#42-08 纯 hedge 只送覆盖率判官（L2 依据判官 0 例，旧实现两路各 1 例）",
       f"semantic={len(mc)} cite={len(mci)}")
    case = json.loads((work / "real" / "q001" / "q001.json").read_text(encoding="utf-8"))
    sha = J.answer_sha1_12(case["response"])
    (work / "semantic" / "final_real.json").write_text(json.dumps([{
        "name": "q001__q001",
        "sem": {"score": 1.0, "verdict": "pass", "band": "", "answer_sha1": sha,
                "strict": ["a1", "a2", "a3"], "paraphrase": [], "miss": [], "span_invalid": []},
        "expected": "?", "rule_verdict": "review"}], ensure_ascii=False), encoding="utf-8")
    r = py("score_sut.py", "report")
    ok("q001   → pass" in r.stdout and "覆盖率判官" in r.stdout,
       "#42-09 hedge 降级的题由覆盖率判官终裁 ⇒ pass（旧实现永远停在 review）",
       r.stdout[-300:])


def t4(tmp):
    """四：CLI 未包装答卷一律 full、题号取文件名／--qid。"""
    d = Path(tmp) / "cli"
    d.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    (d / "q001.json").write_text(json.dumps({
        "qid": "q001", "condition": ["u01_c6"], "conclusion": "不知道。", "answer": "不知道。",
        "confidence": "unknown",
        "evidence": [{"cid": "u01_c1", "quote": "提升公民权限等级至5级或获取特殊贡献权限"}]},
        ensure_ascii=False), encoding="utf-8")
    p = subprocess.run([PY, "-X", "utf8", str(REPO / "judge.py"), "judge", "q001.json"],
                       cwd=str(d), env=env, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=300)
    ok(p.returncode != 0 and "PASS" not in p.stdout,
       "#42-10 自报退化 condition 不得让「不知道。」通过（旧实现 exit 0 ⇒ PASS）",
       f"exit={p.returncode} {p.stdout.strip()[:120]}")
    (d / "q001i.json").write_text(json.dumps({
        "conclusion": "他因权限不足被拦下，想查的是自己的来历，需要5级。",
        "answer": "他因权限不足被拦下，想查的是自己的来历，需要5级。",
        "confidence": "probable",
        "evidence": [{"cid": "u01_c3",
                      "quote": "提升公民权限等级至5级，或获取特殊贡献权限后重试"}]},
        ensure_ascii=False), encoding="utf-8")
    p = subprocess.run([PY, "-X", "utf8", str(REPO / "judge.py"), "judge", "q001i.json"],
                       cwd=str(d), env=env, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=300)
    ok(p.returncode != 0 and "REVIEW" in p.stdout and "iv_key_missing=True" in p.stdout,
       "#42-11 干预题 q001i 经 CLI 须走干预分支并与 API 同判（review／iv_key_missing／非零退出；"
       "旧实现按主轮键判 pass 且 exit 0）",
       f"exit={p.returncode} {p.stdout.strip()[:200]}")


def main():
    tmp = tempfile.mkdtemp(prefix="r12guard_")
    try:
        for fn in (t1, t2):
            try:
                fn()
            except Exception as e:                                   # noqa: BLE001
                ok(False, fn.__name__ + " 抛异常", repr(e))
        for fn in (t3, t4):
            try:
                fn(tmp)
            except Exception as e:                                   # noqa: BLE001
                ok(False, fn.__name__ + " 抛异常", repr(e))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    total = len(_PASS) + len(_FAIL)
    print("")
    print("===== SUMMARY %d/%d 通过 =====" % (len(_PASS), total))
    if _FAIL:
        print("失败项：")
        for m in _FAIL:
            print("  - " + m)
        return 1
    print("VERDICT=PASS（#42 五项守卫全绿）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
