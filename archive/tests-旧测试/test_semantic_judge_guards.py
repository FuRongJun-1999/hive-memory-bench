#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hive-memory-bench 判分链守卫 · 第二批（语义层 / 覆盖率判官）。

覆盖 3 条外部审计 issue 的 CLI 级判据（standalone，只用标准库 + pyyaml）：
  #11 判官 span 机械校验对纯标点/单字不得恒真（「……」「。」「的」须作废该要点）
  #12 全部要点 paraphrase 的卡须达标（浮点误差不得判 fail）
  #17 判官结论须绑定答卷：换答卷后旧判词不得生效（0 分答卷不得 → pass）

用法：
    python -X utf8 tests/test_semantic_judge_guards.py
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

HONEST = "他查资料时被系统以权限不足挡下，想查的正是自己的来历，而需要5级才能看这类核心内容。"
Q = "提升公民权限等级至5级，或获取特殊贡献权限后重试"
ZERO = "他喜欢研究技术的东西。"


def ok(cond, msg, extra=""):
    (_PASS if cond else _FAIL).append(msg)
    print(("[PASS] " if cond else "[FAIL] ") + msg +
          (("   | " + str(extra)) if (extra and not cond) else ""))


def run(args, cwd):
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    return subprocess.run([PY, "-X", "utf8"] + args, cwd=str(cwd), env=env,
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=300)


def fresh(tmp, name):
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


def put(d, qid, obj):
    (d / "sut" / "out" / f"{qid}.json").write_text(
        json.dumps(obj, ensure_ascii=False), encoding="utf-8")


def A(text, ev=None, qid="q001"):
    return {"qid": qid, "conclusion": text, "answer": text,
            "evidence": ev if ev is not None else [{"cid": "u01_c3", "quote": Q}],
            "confidence": "probable"}


def board_row(d, qid):
    d2 = json.loads((d / "real" / "board.json").read_text(encoding="utf-8"))
    return [e for e in d2["detail"] if e["qid"] == qid][0]


def judge_points(d, spans, verdict="strict"):
    """按协议格式写判官输出（span 由调用方给）。"""
    man = json.loads((d / "semantic" / "manifest_real.json").read_text(encoding="utf-8"))[0]
    ah = man["answer_sha1_12"]
    o = d / "semantic" / "out" / "real"
    o.mkdir(parents=True, exist_ok=True)
    (o / f"{man['name']}.json").write_text(json.dumps({
        "qid": man["qid"], "case": man["case"], "answer_sha1_12": ah,
        "points": [{"id": p, "verdict": verdict, "why": "x", "span": s}
                   for p, s in zip(man["required"], spans)]},
        ensure_ascii=False), encoding="utf-8")
    return man


def t11(tmp):
    """#11：纯标点/单字 span 不得放行。"""
    for span in ("……", "。", "的"):
        d = fresh(tmp, "t11_" + str(abs(hash(span)) % 100000))
        put(d, "q001", A(ZERO))
        run(["score_sut.py", "build"], d)
        run(["semantic.py", "prepare", "real", "--select", "semantic"], d)
        judge_points(d, [span, span, span])
        run(["semantic.py", "finalize", "real"], d)
        sem = json.loads((d / "semantic" / "final_real.json").read_text(encoding="utf-8"))[0]["sem"]
        ok(sem["verdict"] == "fail" and sem["span_invalid"],
           f"#11 span={span!r} 须作废该要点并判 fail", sem)


def t12(tmp):
    """#12：全部要点 paraphrase 须达标。"""
    d = fresh(tmp, "t12")
    ans = "系统说他级别不够看不了；他想弄明白自己到底从哪来；得升到最高那档权限才看得到。"
    put(d, "q001", A(ans))
    run(["score_sut.py", "build"], d)
    run(["semantic.py", "prepare", "real", "--select", "semantic"], d)
    spans = {"a1": "级别不够看不了", "a2": "自己到底从哪来", "a3": "升到最高那档权限才看得到"}
    man = json.loads((d / "semantic" / "manifest_real.json").read_text(encoding="utf-8"))[0]
    o = d / "semantic" / "out" / "real"
    o.mkdir(parents=True, exist_ok=True)
    (o / f"{man['name']}.json").write_text(json.dumps({
        "qid": man["qid"], "case": man["case"], "answer_sha1_12": man["answer_sha1_12"],
        "points": [{"id": p, "verdict": "paraphrase", "why": "大意命中", "span": spans[p]}
                   for p in man["required"]]}, ensure_ascii=False), encoding="utf-8")
    run(["semantic.py", "finalize", "real"], d)
    run(["score_sut.py", "report"], d)
    sem = json.loads((d / "semantic" / "final_real.json").read_text(encoding="utf-8"))[0]["sem"]
    ok(sem["verdict"] == "pass", "#12 三点全 paraphrase 须判 pass（score 先取整再比较）", sem)
    ok(board_row(d, "q001")["verdict"] == "pass", "#12 计分板须 pass", board_row(d, "q001"))


def t17(tmp):
    """#17：换答卷后旧判词不得生效。"""
    d = fresh(tmp, "t17")
    sa = "他想看自己是怎么来的，可是级别不够被拦住了，要到五级才行。"
    put(d, "q001", A(sa))
    run(["score_sut.py", "build"], d)
    run(["semantic.py", "prepare", "real", "--select", "semantic"], d)
    judge_points(d, ["级别不够被拦住", "自己是怎么来的", "要到五级才行"])
    run(["semantic.py", "finalize", "real"], d)
    run(["score_sut.py", "report"], d)
    ok(board_row(d, "q001")["verdict"] == "pass", "#17 前置：系统 A 判 pass", board_row(d, "q001"))
    # 换成 0 分答卷
    put(d, "q001", A(ZERO))
    # C1 路径 a：只 build + report（README 之外的常见走法）——旧判词不得生效
    run(["score_sut.py", "build"], d)
    run(["score_sut.py", "report"], d)
    row_a = board_row(d, "q001")
    ok(row_a["verdict"] != "pass",
       "#17 路径a：0 分答卷直接 report 不得为 pass（判官从没看过它）", row_a)
    # C1 路径 b：按 README 全流程重跑（build → prepare → …）
    p = run(["semantic.py", "prepare", "real", "--select", "semantic"], d)
    ok("待判：1" in p.stdout or "待判：1 例" in p.stdout,
       "#17 prepare 须把换过答卷的题列为待判（缓存键含答卷指纹）", p.stdout[-400:])
    run(["semantic.py", "finalize", "real"], d)
    run(["score_sut.py", "report"], d)
    row = board_row(d, "q001")
    ok(row["verdict"] != "pass", "#17 换答卷后不得仍为 pass", row)
    ok("过期" in row["by"] or "规则层" in row["by"], "#17 by 须标过期或停在规则层", row["by"])
    # 路径 a：直接 report（判词过期）
    p2 = run(["score_sut.py", "report"], d)
    ok("过期" in p2.stdout or board_row(d, "q001")["verdict"] != "pass",
       "#17 直接 report 亦不得采信过期判词", p2.stdout[-300:])


def main():
    tmp = tempfile.mkdtemp(prefix="semguard_")
    try:
        for fn in (t11, t12, t17):
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
    print("VERDICT=PASS（语义层/覆盖率判官守卫全绿）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
