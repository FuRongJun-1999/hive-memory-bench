#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hive-memory-bench 判分链守卫 · 第一批（score_sut.py 端到端路由）。

覆盖 3 条外部审计 issue 的 CLI 级判据（standalone，只用标准库 + pyyaml）：
  #15 被测系统自报 condition 不得让结论轴退出判决（「不知道。」经 build 后须 fail）
  #8  被测系统自报 qid 不得改路由（写 q001i 的 q001 答卷须告警且按主轮键判）
  #7  覆盖率判官不得把结构轴降级（站外文献）改回 pass

用法：
    python -X utf8 tests/test_score_sut_routing_guards.py
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


def run(args, cwd):
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    return subprocess.run([PY, "-X", "utf8"] + args, cwd=str(cwd), env=env,
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=300)


def sandbox(tmp, name):
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


Q = "提升公民权限等级至5级，或获取特殊贡献权限后重试"
HONEST = "他查资料时被系统以权限不足挡下，想查的正是自己的来历，而需要5级才能看这类核心内容。"


def put(d, qid, obj):
    (d / "sut" / "out" / f"{qid}.json").write_text(
        json.dumps(obj, ensure_ascii=False), encoding="utf-8")


def build_line(d, qid):
    p = run(["score_sut.py", "build"], d)
    for line in p.stdout.splitlines():
        s = line.strip()
        if s.startswith(qid + " ") or s.startswith(qid + "\t"):
            return s, p
    return "", p


def t15(tmp):
    d = sandbox(tmp, "t15")
    put(d, "q001", {"qid": "q001", "condition": "u01_c6", "conclusion": "不知道。",
                    "answer": "不知道。", "confidence": "unknown",
                    "evidence": [{"cid": "u01_c3", "quote": Q}]})
    line, p = build_line(d, "q001")
    ok(" fail " in line or line.endswith("fail"),
       "#15 自报退化条件不得让「不知道。」通过（build 判 fail）", line or p.stdout[-300:])


def t8(tmp):
    d = sandbox(tmp, "t8")
    put(d, "q001", {"qid": "q001i", "conclusion": HONEST, "answer": HONEST,
                    "confidence": "probable",
                    "evidence": [{"cid": "u01_c3", "quote": Q}]})
    line, p = build_line(d, "q001")
    ok("[WARN]" in p.stdout, "#8 自报 qid 与文件名不符须告警", p.stdout[:300])
    ok(line and "pass" in line, "#8 仍按文件名 q001 判（诚实答案 pass）", line)


def t7(tmp):
    d = sandbox(tmp, "t7")
    put(d, "q001", {"qid": "q001", "conclusion": HONEST,
                    "answer": HONEST + " 另见 https://arxiv.org/abs/2401.00001 的研究。",
                    "confidence": "probable",
                    "evidence": [{"cid": "u01_c3", "quote": Q}]})
    line, p0 = build_line(d, "q001")
    ok("review" in line, "#7 前置：站外文献须触发降级（verdict=review）", line or p0.stdout[-300:])
    (d / "semantic").mkdir(exist_ok=True)
    (d / "semantic" / "final_real.json").write_text(json.dumps(
        [{"name": "q001__q001", "sem": {"verdict": "pass", "score": 0.9, "band": "high"}}],
        ensure_ascii=False), encoding="utf-8")
    p1 = run(["score_sut.py", "report"], d)
    board = json.loads((d / "real" / "board.json").read_text(encoding="utf-8"))
    det = board["detail"][0]
    ok(det["verdict"] != "pass",
       "#7 覆盖率判官不得把站外文献降级改回 pass", det)
    ok("覆盖率判官" not in det["by"],
       "#7 by 不得记为「覆盖率判官」", det["by"])
    ok("pass      1/1" not in p1.stdout, "#7 计分板不得出现 pass 1/1", p1.stdout[-300:])


def main():
    tmp = tempfile.mkdtemp(prefix="sutsut_")
    try:
        for fn in (t15, t8, t7):
            try:
                fn(tmp)
            except Exception as e:
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
    print("VERDICT=PASS（判分链路由/降级守卫全绿）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
