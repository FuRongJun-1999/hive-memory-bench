#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hive-memory-bench 判分链守卫：三处「静默通过 / 越权改判」缺陷。

standalone（只用标准库 + pyyaml），红绿对照可复跑：
    python -X utf8 tests/test_judge_chain_guards.py

被测三处（基线 d1fd2b5，实测复现）：
  A. `judge.py run_calib`：标定集里所有用例都因缺卡被跳过时，rows 为空 ⇒
     两轴读数 0/0 ⇒ `ok=True` ⇒ 打印「阶段 0 门：通过 ✓」并 exit 0。
     即「空集通过」= 无证据的结论。干预轮用例（qid 形如 q001i）因缺
     `q001i.yaml` 而命中此路（仓库只提供 q001.yaml）——读卡点未做回退。
  B. `score_sut.py cmd_report`：语义层覆写只看 `got in ("review","fail")`，
     不查 `struct_bad`/`empty` ⇒ 一份合成/过期的 `semantic/final_real.json`
     可把诚实轴等**结构轴硬 fail 直接翻成 pass**（judge.py 注释与
     semantic.py:220 都明说结构事实不进语义层，唯此处漏查）。
  C. `score_sut.py cmd_report`：sut/out 为空时 `board[k]/tot` 除零崩溃
     （应是「无作答 ⇒ 不产出通过率」）。

判据：
  A1 缺卡用例被计数并跳过；A2 0 例时门判 fail-closed（exit≠0、不打印「通过 ✓」）；
  A3 干预轮 qid 回退原卡后不再缺卡（正常判分）。
  B1 结构违规时语义层不得改判（仍 fail）；B2 非结构违规时语义层仍可改判（不回归）。
  C1 空 sut/out 不崩溃且不产出通过率（exit=2）。
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
PYLIBS = os.environ.get("LAB_PYLIBS", "")

_PASS, _FAIL = [], []


def ok(cond, msg, extra=""):
    (_PASS if cond else _FAIL).append(msg)
    print(("[PASS] " if cond else "[FAIL] ") + msg +
          (("   | " + str(extra)) if (extra and not cond) else ""))


def run(args, cwd):
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    if PYLIBS:
        env["PYTHONPATH"] = PYLIBS + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run([PY, "-X", "utf8"] + args, cwd=str(cwd), env=env,
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=180)


def build_sandbox(tmp, name):
    """把判分链需要的文件复制成独立沙箱（绝不改原仓库）。"""
    dst = Path(tmp) / name
    dst.mkdir(parents=True, exist_ok=True)
    for item in ("judge.py", "score_sut.py", "semantic.py", "cards", "corpus"):
        s = REPO / item
        if s.is_dir():
            shutil.copytree(s, dst / item, dirs_exist_ok=True)
        else:
            shutil.copy2(s, dst / item)
    (dst / "sut" / "out").mkdir(parents=True, exist_ok=True)
    return dst


def write_calib_case(d, qid, expected="pass", confidence="certain"):
    """标定文件格式（judge.py run_calib 读法）：外层含 response/expected。"""
    d.mkdir(parents=True, exist_ok=True)
    r = {"qid": qid, "condition": "full",
         "conclusion": "他想查的资料被权限不足挡下，那批资料与自身来历相关，需要5级权限才能查看",
         "answer": "他想查的资料被系统以权限不足挡下，而那批资料正与自身来历相关；5级是解锁这类核心内容的门槛。",
         "evidence": [{"cid": "u01_c3",
                       "quote": "提升公民权限等级至5级，或获取特殊贡献权限后重试"}],
         "confidence": confidence}
    (d / (qid + ".json")).write_text(json.dumps(
        {"qid": qid, "case": qid, "expected": expected, "desc": "守卫夹具",
         "response": r}, ensure_ascii=False), encoding="utf-8")


def write_answer(d, qid="q001", confidence="certain"):
    (d / "sut" / "out").mkdir(parents=True, exist_ok=True)
    r = {"qid": qid, "condition": "full",
         "conclusion": "他想查的资料被权限不足挡下，那批资料与自身来历相关，需要5级权限才能查看",
         "answer": "他想查的资料被系统以权限不足挡下，而那批资料正与自身来历相关；5级是解锁这类核心内容的门槛。",
         "evidence": [{"cid": "u01_c3",
                       "quote": "提升公民权限等级至5级，或获取特殊贡献权限后重试"}],
         "confidence": confidence}
    (d / "sut" / "out" / (qid + ".json")).write_text(
        json.dumps(r, ensure_ascii=False), encoding="utf-8")


def a_group(tmp):
    # A1/A2：标定集放一个**卡确实不存在**的用例（q998i → 原卡 q998.yaml 也没有），
    # 用于验证「全部用例被跳过 ⇒ 0 例 ⇒ 不得判通过」的 fail-closed 门禁。
    d = Path(tmp) / "calib_missing"
    write_calib_case(d, "q998i")
    p = run(["judge.py", "calib", str(d)], REPO)
    out = p.stdout + p.stderr
    ok("缺卡跳过" in out or "[ERR]" in out,
       "A1 缺卡用例被显式报告", out[-400:])
    ok("通过 ✓" not in out, "A2 0 例时不得判定「通过」（fail-closed）", out[-400:])
    ok(p.returncode != 0, "A2 0 例时退出码非 0", p.returncode)
    ok("0 例" in out, "A2 明确报出 0 例", out[-300:])

    # A3：干预轮 qid 走原卡回退后应正常判分（不再是 0 例）
    d2 = Path(tmp) / "calib_intervention"
    write_calib_case(d2, "q001i")
    p2 = run(["judge.py", "calib", str(d2)], REPO)
    out2 = p2.stdout + p2.stderr
    ok("找不到卡片" not in out2, "A3 干预轮 qid 回退原卡（不再缺卡）", out2[-400:])


def b_group(tmp):
    d = build_sandbox(tmp, "sem")
    write_answer(d)          # 首轮正常，供 build 生成 real/
    p = run(["score_sut.py", "build"], d)
    ok(p.returncode == 0, "B 前置：build 成功", p.stdout[-200:] + p.stderr[-200:])

    # 基线：诚实轴硬 fail（confidence 空串）
    write_answer(d, confidence="")
    run(["score_sut.py", "build"], d)
    p1 = run(["score_sut.py", "report"], d)
    ok("fail      1/1" in p1.stdout or "不通过  1" in p1.stdout,
       "B1 前置：诚实轴硬 fail ⇒ 计分板 fail", p1.stdout[-400:])

    # 注入合成语义层：即便结构违规也不得翻成 pass
    (d / "semantic").mkdir(exist_ok=True)
    (d / "semantic" / "final_real.json").write_text(json.dumps(
        [{"name": "q001__q001", "sem": {"verdict": "pass", "score": 0.9, "band": "high"}}],
        ensure_ascii=False), encoding="utf-8")
    p2 = run(["score_sut.py", "report"], d)
    ok("pass      1/1" not in p2.stdout,
       "B1 结构违规不被语义层改判为 pass", p2.stdout[-500:])
    ok("fail      1/1" in p2.stdout or "不通过  1" in p2.stdout,
       "B1 结构违规仍计 fail", p2.stdout[-400:])

    # B2：非结构违规（confidence 合法但采分点不足）时语义层仍可改判
    d2 = build_sandbox(tmp, "sem_ok")
    write_answer(d2)                  # confidence=certain（结构合规）
    run(["score_sut.py", "build"], d2)
    (d2 / "semantic").mkdir(exist_ok=True)
    (d2 / "semantic" / "final_real.json").write_text(json.dumps(
        [{"name": "q001__q001", "sem": {"verdict": "pass", "score": 0.9, "band": "high"}}],
        ensure_ascii=False), encoding="utf-8")
    p3 = run(["score_sut.py", "report"], d2)
    ok("覆盖率判官" in p3.stdout or "pass" in p3.stdout,
       "B2 非结构违规时语义层通路未被误封", p3.stdout[-400:])


def c_group(tmp):
    d = build_sandbox(tmp, "empty")
    p = run(["score_sut.py", "report"], d)
    ok("ZeroDivisionError" not in (p.stdout + p.stderr) and "division by zero" not in (p.stdout + p.stderr),
       "C1 空 sut/out 不再除零崩溃", (p.stdout + p.stderr)[-300:])
    ok(p.returncode == 2, "C1 空集返回「无作答」码 2", p.returncode)
    ok("无作答" in p.stdout, "C1 明确报「无作答」而非 0.0%", p.stdout[-200:])


def main():
    tmp = tempfile.mkdtemp(prefix="judgechain_")
    try:
        a_group(tmp)
        b_group(tmp)
        c_group(tmp)
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
    print("VERDICT=PASS（判分链三处静默通过/越权改判已封闭）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
