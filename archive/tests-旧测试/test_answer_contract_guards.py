#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""作答契约形状守卫（issue #54）。

病灶：`sut/out/` 里只要有一份作答的**字段类型**不符合 `questions/作答契约.md`，
旧实现就让**整批** build 以 AttributeError 退出——同批里正常的题也拿不到分；官方导入脚本的
`--check` 体检同样挡不住（字符串 evidence ⇒ 体检自己崩；数字 confidence ⇒ 放行，
然后 build 崩）。

三条主张各有一组守卫：
  A. 判据单点 —— 形状校验只在 `judge.contract_errors` 一处定义，score_sut 与导入脚本都调它；
  B. 消费点护栏 —— `axis_evidence` / `axis_honesty` / 导入脚本的体检循环即使被
     绕过校验，也只把该条记无效，不再抛异常（「判据上收后守卫须锚在消费点」）；
  C. 整批不连坐 —— 三种畸形输入下 build/report 都以 0 退出、同批正常作答照常出分、
     畸形题计 fail 并单列题号，report 照旧写出 `real/board.json`。

用法：python -X utf8 tests/test_answer_contract_guards.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PY = sys.executable
_PASS, _FAIL = [], []


def ok(cond, msg, extra=""):
    (_PASS if cond else _FAIL).append(msg)
    print(("[PASS] " if cond else "[FAIL] ") + msg +
          (("   | " + str(extra)) if (extra and not cond) else ""))


def run(args, cwd, timeout=900):
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    p = subprocess.run([PY, "-X", "utf8"] + [str(x) for x in args], cwd=str(cwd), env=env,
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def stage(tmp, name):
    d = Path(tmp) / name
    d.mkdir(parents=True, exist_ok=True)
    for item in ("judge.py", "score_sut.py", "semantic.py", "导入回收作答.py", "cards", "corpus"):
        s = REPO / item
        if s.is_dir():
            shutil.copytree(s, d / item, dirs_exist_ok=True)
        else:
            shutil.copy2(s, d / item)
    (d / "sut" / "out").mkdir(parents=True, exist_ok=True)
    return d


NORMAL = {"qid": "q002", "condition": "full",
          "conclusion": "\u4ed6\u60f3\u67e5\u7684\u8d44\u6599\u88ab\u6743\u9650\u4e0d\u8db3\u6321\u4e0b",
          "answer": "\u4ed6\u60f3\u67e5\u7684\u8d44\u6599\u88ab\u7cfb\u7edf\u4ee5\u6743\u9650\u4e0d\u8db3\u6321\u4e0b\uff0c"
                    "\u800c\u90a3\u6279\u8d44\u6599\u6b63\u4e0e\u81ea\u8eab\u6765\u5386\u76f8\u5173\uff1b"
                    "5\u7ea7\u662f\u89e3\u9501\u8fd9\u7c7b\u6838\u5fc3\u5185\u5bb9\u7684\u95e8\u69db\u3002",
          "evidence": [{"cid": "u01_c3",
                        "quote": "\u63d0\u5347\u516c\u6c11\u6743\u9650\u7b49\u7ea7\u81f35\u7ea7\uff0c"
                                 "\u6216\u83b7\u53d6\u7279\u6b8a\u8d21\u732e\u6743\u9650\u540e\u91cd\u8bd5"}],
          "confidence": "certain"}
MAL = {
    "evstr": dict(NORMAL, qid="q001", evidence=["\u4e00\u6bb5\u5b57\u7b26\u4e32"]),
    "confint": dict(NORMAL, qid="q001", confidence=1),
    "toplist": [{"qid": "q001", "answer": "x"}],
    "evdict": dict(NORMAL, qid="q001", evidence={"cid": "u01_c3", "quote": "x"}),
    "quoteint": dict(NORMAL, qid="q001", evidence=[{"cid": "u01_c3", "quote": 7}]),
    "ansint": dict(NORMAL, qid="q001", answer=7),
}


# ------------------------------------------------------------ A. 判据单点
def a_single_point():
    sys.path.insert(0, str(REPO))
    import judge as J
    ok(callable(getattr(J, "contract_errors", None)),
       "A1 judge.contract_errors 存在（形状判据有唯一定义处）")
    if not callable(getattr(J, "contract_errors", None)):
        # 红树（5f9c0c0）上判据单点尚未存在——余下各项记 FAIL 而不是抛异常，
        # 这样「红树失败 / 绿树全过」是同一份守卫跑出来的对照，不是崩溃。
        for m in ("A2 合规作答判为形状合规（不误伤）",
                  "A2 只给 qid 的最小作答也合规（缺字段不算形状不符）",
                  "A3 evstr ⇒ 报出「evidence[1] 不是对象」",
                  "A3 confint ⇒ 报出「confidence 不是字符串」",
                  "A3 toplist ⇒ 报出「顶层不是 JSON 对象」",
                  "A3 evdict ⇒ 报出「evidence 不是列表」",
                  "A3 quoteint ⇒ 报出「evidence[1].quote 不是字符串」",
                  "A3 ansint ⇒ 报出「answer 不是字符串」"):
            ok(False, m, "judge.contract_errors 不存在（判据单点未落地）")
        return
    ok(J.contract_errors(NORMAL) == [],
       "A2 合规作答判为形状合规（不误伤）", J.contract_errors(NORMAL))
    ok(J.contract_errors({"qid": "q001"}) == [],
       "A2 只给 qid 的最小作答也合规（缺字段不算形状不符）")
    for tag, msg in (("evstr", "evidence[1] 不是对象"), ("confint", "confidence 不是字符串"),
                     ("toplist", "顶层不是 JSON 对象"), ("evdict", "evidence 不是列表"),
                     ("quoteint", "evidence[1].quote 不是字符串"), ("ansint", "answer 不是字符串")):
        errs = J.contract_errors(MAL[tag])
        ok(bool(errs) and any(msg in e for e in errs),
           "A3 %s ⇒ 报出「%s」" % (tag, msg), errs)
    ss = (REPO / "score_sut.py").read_text(encoding="utf-8")
    im = (REPO / "\u5bfc\u5165\u56de\u6536\u4f5c\u7b54.py").read_text(encoding="utf-8")
    ok("J.contract_errors(" in ss, "A4 score_sut.py 调判据单点（不另写一份类型检查）")
    ok("J.contract_errors(" in im, "A4 导入回收作答.py 调同一个判据单点")
    ok(ss.count("isinstance(obj, dict)") == 0 and "type(obj).__name__" not in ss.split("J.contract_errors")[0],
       "A4 两处不再各写各的顶层类型判断")


# ------------------------------------------------------------ B. 消费点护栏
def b_consumption_points():
    sys.path.insert(0, str(REPO))
    import judge as J
    idx = J.chapter_index(J.load_units())
    card = J.load_card(J.CARDS / "q001.yaml")

    try:
        ev = J.axis_evidence(card, {"evidence": ["\u4e00\u6bb5\u5b57\u7b26\u4e32"]}, idx)
        ok(ev["pass"] is False and any("\u4e0d\u662f\u5bf9\u8c61" in x for x in ev["invalid"]),
           "B1 axis_evidence 直接吃字符串 evidence ⇒ 记无效引用，不抛异常", ev)
    except Exception as e:
        ok(False, "B1 axis_evidence 直接吃字符串 evidence ⇒ 记无效引用，不抛异常", repr(e))

    try:
        ev2 = J.axis_evidence(card, {"evidence": {"cid": "u01_c3", "quote": "x"}}, idx)
        ok(ev2["pass"] is False, "B1 axis_evidence 吃 dict 型 evidence ⇒ 计无效，不抛异常", ev2)
    except Exception as e:
        ok(False, "B1 axis_evidence 吃 dict 型 evidence ⇒ 计无效，不抛异常", repr(e))

    try:
        h = J.axis_honesty(card, {"confidence": 1})
        ok(h["pass"] is False and "\u987b\u4e3a\u5b57\u7b26\u4e32" in h["detail"],
           "B2 axis_honesty 直接吃数字 confidence ⇒ 记诚实轴违规并说明类型，不抛异常", h)
    except Exception as e:
        ok(False, "B2 axis_honesty 直接吃数字 confidence ⇒ 记诚实轴违规，不抛异常", repr(e))

    ok(J.axis_honesty(card, {"confidence": "certain"})["pass"] is True,
       "B2 confidence 为合法字符串时诚实轴照旧判过（不误伤）")
    ok(J.axis_honesty(card, {"confidence": "maybe"})["detail"].startswith("confidence \u975e\u6cd5"),
       "B2 confidence 取值非法仍走原路径（与类型不符分得开）")

    # judge() 自身
    for tag in ("evstr", "confint", "toplist", "evdict", "quoteint", "ansint"):
        try:
            r = J.judge(card, MAL[tag], idx, qid="q001", condition="full")
            good = (r["verdict"] == "fail" and "contract" in (r.get("struct_bad") or [])
                    and bool(r.get("contract_bad")))
            ok(good, "B3 judge() 吃 %s ⇒ 一次明确的 fail（struct_bad=contract），不抛异常" % tag, r)
        except Exception as e:
            ok(False, "B3 judge() 吃 %s ⇒ 一次明确的 fail，不抛异常" % tag, repr(e))

    r_ok = J.judge(card, dict(NORMAL, qid="q001"), idx, qid="q001", condition="full")
    ok("contract" not in (r_ok.get("struct_bad") or []),
       "B3 合规作答的 struct_bad 不含 contract（不误伤）", r_ok.get("struct_bad"))
    ok("contract_bad" not in r_ok or not r_ok.get("contract_bad"),
       "B3 合规作答不带 contract_bad", r_ok.get("contract_bad"))


# ------------------------------------------------------------ C. 整批不连坐
def c_batch(tmp):
    for tag in ("evstr", "confint", "toplist"):
        d = stage(tmp, "c_" + tag)
        (d / "sut" / "out" / "q001.json").write_text(
            json.dumps(MAL[tag], ensure_ascii=False), encoding="utf-8")
        (d / "sut" / "out" / "q002.json").write_text(
            json.dumps(NORMAL, ensure_ascii=False), encoding="utf-8")
        rc, out = run(["score_sut.py", "build"], d)
        ok(rc == 0 and "AttributeError" not in out and "Traceback" not in out,
           "C1 build 遇 %s：以 0 退出、无异常栈（旧实现 exit 1 + AttributeError）" % tag,
           (rc, out[-260:]))
        ok((d / "real" / "q002" / "q002.json").exists(),
           "C2 build 遇 %s：同批正常的 q002 照常出分（旧实现整批不出分）" % tag)
        ok((d / "real" / "q001" / "q001.json").exists(),
           "C2 build 遇 %s：畸形题也落盘（单列，不再无声跳过）" % tag)
        ok("\u5951\u7ea6\u4e0d\u7b26" in out and "q001" in out,
           "C3 build 遇 %s：汇总点名「契约不符 … q001」" % tag, out[-400:])
        rc2, out2 = run(["score_sut.py", "report"], d)
        ok(rc2 == 0 and "AttributeError" not in out2,
           "C4 report 遇 %s：以 0 退出、无异常栈" % tag, (rc2, out2[-260:]))
        ok((d / "real" / "board.json").exists(),
           "C4 report 遇 %s：board.json 照旧写出（旧实现写不出来）" % tag)
        if (d / "real" / "board.json").exists():
            b = json.loads((d / "real" / "board.json").read_text(encoding="utf-8"))
            det = {r["qid"]: r["verdict"] for r in b["detail"]}
            ok(det.get("q001") == "fail",
               "C5 report 遇 %s：畸形题计 fail（不是静默丢题）" % tag, det)
            ok(det.get("q002") in ("pass", "review", "fail"),
               "C5 report 遇 %s：正常题进了计分板" % tag, det)


# ------------------------------------------------------------ D. 导入脚本
def d_import(tmp):
    for tag in ("evstr", "confint"):
        d = stage(tmp, "d_" + tag)
        exp = d / "_exp.json"
        exp.write_text(json.dumps({"answers": [NORMAL, MAL[tag]]}, ensure_ascii=False),
                       encoding="utf-8")
        rc, out = run(["\u5bfc\u5165\u56de\u6536\u4f5c\u7b54.py", exp, "--check"], d)
        ok("AttributeError" not in out and "Traceback" not in out,
           "D1 %s：--check 不抛异常（旧实现字符串 evidence 直接崩）" % tag, out[-260:])
        ok(rc == 1 and "\u5951\u7ea6\u4e0d\u7b26" in out,
           "D2 %s：--check 把「类型不符」列为体检项并以非零退出" % tag, (rc, out[-260:]))
        ok(not list((d / "sut" / "out").glob("*.json")),
           "D2 %s：--check 不落盘" % tag)
        rc2, out2 = run(["\u5bfc\u5165\u56de\u6536\u4f5c\u7b54.py", exp], d)
        ok("AttributeError" not in out2 and rc2 == 0,
           "D3 %s：落盘不抛异常、以 0 退出" % tag, (rc2, out2[-260:]))
        files = sorted(x.name for x in (d / "sut" / "out").glob("*.json"))
        ok(files == ["q001.json", "q002.json"],
           "D3 %s：两份作答都落盘（畸形题不丢，交给 build 计 fail）" % tag, files)
        ok("\u5951\u7ea6\u4e0d\u7b26" in out2,
           "D3 %s：落盘汇总报出「契约不符」题数" % tag, out2[-300:])
        rc3, out3 = run(["score_sut.py", "build"], d)
        ok(rc3 == 0 and "AttributeError" not in out3,
           "D4 %s：导入后 build 以 0 退出（旧实现数字 confidence 一路放行到 build 才崩）" % tag,
           (rc3, out3[-260:]))

    # 合规导出不得被新门挡住
    d = stage(tmp, "d_ok")
    exp = d / "_ok.json"
    exp.write_text(json.dumps({"answers": [NORMAL]}, ensure_ascii=False), encoding="utf-8")
    rc, out = run(["\u5bfc\u5165\u56de\u6536\u4f5c\u7b54.py", exp, "--check"], d)
    ok(rc == 0 and "\u5951\u7ea6\u4e0d\u7b26" not in out,
       "D5 合规导出的 --check 仍以 0 退出（新门不误伤正常路径）", (rc, out[-260:]))


def main():
    tmp = tempfile.mkdtemp(prefix="i054g_")
    try:
        a_single_point()
        b_consumption_points()
        c_batch(tmp)
        d_import(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    total = len(_PASS) + len(_FAIL)
    print("")
    print("===== SUMMARY %d/%d \u901a\u8fc7 =====" % (len(_PASS), total))
    if _FAIL:
        print("\u5931\u8d25\u9879\uff1a")
        for m in _FAIL:
            print("  - " + m)
        return 1
    print("VERDICT=PASS\uff08issue #54 \u4f5c\u7b54\u5951\u7ea6\u5f62\u72b6\u5df2\u5c01\u95ed\uff1a\u4e00\u4efd\u7578\u5f62\u4f5c\u7b54\u4e0d\u518d\u62d6\u57ae\u6574\u6279\uff09")
    return 0


if __name__ == "__main__":
    sys.exit(main())
