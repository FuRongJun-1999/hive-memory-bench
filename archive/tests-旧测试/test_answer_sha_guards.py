#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hive-memory-bench 判分链守卫 · 答卷指纹（judge.py + score_sut.py，第十一轮 P0）。

覆盖 1 条外部审计 issue 的最小可判据（standalone，只用标准库 + pyyaml）：
  #40 答卷指纹 `answer_sha1_12` 只哈希 `answer or conclusion`，**不含 evidence**，
      而 L2 依据契合判官（cite-v0.4）判的恰恰是引文——结论一字不改、只把引文换成与结论
      无关的句子，指纹不变、`_stale_qids()` 不判过期、旧 `fit` 判词静默生效，q001 照样 pass。
      现改为哈希**判官读到的全部字段**（conclusion/answer/每条 evidence 的 cid+quote/
      condition/confidence，外加口径版本号），并给 cite 判词加 prompt 版本核对。

用法：
    python -X utf8 tests/test_answer_sha_guards.py
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
sys.path.insert(0, str(REPO))
import judge as J  # noqa: E402

_PASS, _FAIL = [], []

ANS = "他查资料时被系统以权限不足挡下，想查的正是自己的来历，而需要5级才能看这类核心内容。"
Q_OK = "权限不足。其他相关信息已被加密"          # 相关、但不在白名单 ⇒ 规则层 cite 降级
Q_OFF = "陈默开启舱门，看向巨子塔方向，躺好，起飞"   # 与结论无关（同章）


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


def A(quote, conclusion=ANS):
    return {"qid": "q001", "conclusion": conclusion, "answer": conclusion,
            "confidence": "probable", "evidence": [{"cid": "u01_c3", "quote": quote}]}


def put(d, obj):
    (d / "sut" / "out" / "q001.json").write_text(
        json.dumps(obj, ensure_ascii=False), encoding="utf-8")


def built_sha(d):
    """判官侧算指纹用的对象：`real/<qid>/<qid>.json` 里的 `response`（score_sut.py build 写出）。

    注意它与 `sut/out/<qid>.json` 的原文差两个字段——`load_sut()` 会把 `qid` 改成文件名、
    把 `condition` 归一成 `"full"`（issue #8／#15：自报值不采信）。指纹口径要覆盖判官读到的
    字段，故断言必须拿**管线里的那个对象**算，不能拿手写的原始 dict 算。
    """
    return J.answer_sha1_12(json.loads(
        (d / "real" / "q001" / "q001.json").read_text(encoding="utf-8"))["response"])


def cite_file(d, version=None, sha=None):
    """按官方 finalize 的格式写 `semantic/final_real_cite.json`（L2 判官对当前答卷判 fit）。"""
    (d / "semantic").mkdir(parents=True, exist_ok=True)
    (d / "semantic" / "final_real_cite.json").write_text(json.dumps(
        [{"name": "q001__q001", "cite": "fit", "why": "引文支撑结论",
          "prompt_version": version or J.CITE_PROMPT_VERSION,
          "answer_sha1": sha if sha is not None else built_sha(d)}],
        ensure_ascii=False), encoding="utf-8")


def row(d):
    b = json.loads((d / "real" / "board.json").read_text(encoding="utf-8"))
    return [e for e in b["detail"] if e["qid"] == "q001"][0]


def t40a():
    """#40：指纹必须覆盖判官读到的全部字段。"""
    v1, v2 = A(Q_OK), A(Q_OFF)
    ok(J.answer_sha1_12(v1) != J.answer_sha1_12(v2),
       "#40a 只换引文（结论一字不改）⇒ 指纹必须变")
    ok(J.answer_sha1_12(v1) == J.answer_sha1_12(A(Q_OK)),
       "#40b 同一份答卷 ⇒ 指纹必须稳定（幂等）")
    ok(J.answer_sha1_12(v1) != J.answer_sha1_12(
        {**v1, "condition": "degraded"}), "#40c condition 进指纹")
    ok(J.answer_sha1_12(v1) != J.answer_sha1_12({**v1, "confidence": "certain"}),
       "#40d confidence 进指纹")
    ok(J.answer_sha1_12(v1) != J.answer_sha1_12(
        {**v1, "evidence": [{"cid": "u01_c9", "quote": Q_OK}]}),
       "#40e evidence 的 cid 进指纹")


def t40b(tmp):
    """#40：换引文后旧 fit 判词不得生效（端到端，官方 build+report）。"""
    d = fresh(tmp, "t40b")
    put(d, A(Q_OK))
    r = run(["score_sut.py", "build"], d)
    ok(r.returncode == 0, "#40f build 退出码", r.stderr[-300:])
    cite_file(d)
    run(["score_sut.py", "report"], d)
    ok(row(d)["verdict"] == "pass",
       "#40g 前置（不回归）：引文没换时 L2 fit 仍撤销依据轴降级", row(d))
    # 只换引文：结论一字不改
    put(d, A(Q_OFF))
    run(["score_sut.py", "build"], d)
    p = run(["score_sut.py", "report"], d)
    ok("过期" in p.stdout, "#40h report 须打出「判官结论过期」WARN", p.stdout[-300:])
    ok(row(d)["verdict"] != "pass",
       "#40i 只换引文 ⇒ q001 不得 pass（判官从没看过这份答卷）", row(d))


def t40c(tmp):
    """#40：判官 prompt 升版后旧判词不得生效。"""
    d = fresh(tmp, "t40c")
    put(d, A(Q_OK))
    run(["score_sut.py", "build"], d)
    cite_file(d, version="cite-v0.3")
    run(["score_sut.py", "report"], d)
    ok(row(d)["verdict"] != "pass",
       "#40j 判词来自上一版 prompt ⇒ 不得采信", row(d))


def t40d(tmp):
    """#40：旧版终裁文件（没写 prompt_version）不得采信。"""
    d = fresh(tmp, "t40d")
    put(d, A(Q_OK))
    run(["score_sut.py", "build"], d)
    (d / "semantic").mkdir(parents=True, exist_ok=True)
    (d / "semantic" / "final_real_cite.json").write_text(json.dumps(
        [{"name": "q001__q001", "cite": "fit", "why": "x",
          "answer_sha1": built_sha(d)}], ensure_ascii=False), encoding="utf-8")
    run(["score_sut.py", "report"], d)
    ok(row(d)["verdict"] != "pass",
       "#40k 没写 prompt_version 的旧判词 ⇒ 无从核对版本，不采信", row(d))


def main():
    tmp = tempfile.mkdtemp(prefix="shaguard_")
    try:
        t40a()
        for fn in (t40b, t40c, t40d):
            try:
                fn(tmp)
            except Exception as e:
                ok(False, fn.__name__ + " 抛异常", repr(e))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print()
    print(f"===== SUMMARY {len(_PASS)}/{len(_PASS) + len(_FAIL)} 通过 =====")
    if _FAIL:
        for m in _FAIL:
            print("  FAILED: " + m)
        print("VERDICT=FAIL（答卷指纹守卫未全绿）")
        sys.exit(1)
    print("VERDICT=PASS（答卷指纹守卫全绿）")


if __name__ == '__main__':
    main()
