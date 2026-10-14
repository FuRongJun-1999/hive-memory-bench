#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""压缩代价文档口径守卫（issue #33 第八项 / P1-26）。

覆盖：文档的「律」不得被同文表格推翻，且判据是机械的：
  #33-26a A 表（「保住那一块」严格／宽松两列）与 `systems/readings.json` 逐格一致；
          旧文把灵枢 v0.7.1 的 2/9 写成更新前的 5/9。
  #33-26b 写「单调」的行里列出的 x/9 链必须非降，且每个读数都必须在 A 表里出现过。
  #33-26c 「N 家 x/9」的家数必须 ≤ A 表里该读数的实际家数（旧文「原文检索两家 5/9」实为 1 家）。

用法：python -X utf8 tests/test_compress_cost_doc_guards.py
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
DOC = "docs/压缩的代价就是因果丢失_v1.0.md"
PY = sys.executable
_PASS, _FAIL = [], []


def ok(cond, msg, extra=""):
    (_PASS if cond else _FAIL).append(msg)
    print(("[PASS] " if cond else "[FAIL] ") + msg +
          (("   | " + str(extra)) if (extra and not cond) else ""))


def docs_check(root: Path):
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    p = subprocess.run([PY, "-X", "utf8", str(root / "check_all.py"), "docs"], cwd=str(root),
                       env=env, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=600)
    return p.returncode, p.stdout + p.stderr


def fresh() -> Path:
    d = Path(tempfile.mkdtemp()) / "r"
    shutil.copytree(REPO, d, ignore=shutil.ignore_patterns(
        ".git", "sut", "real", "real_*", "semantic", "__pycache__", "out", "e2e"))
    return d


def main() -> int:
    code, out = docs_check(REPO)
    ok(code == 0 and "结果：0 错误" in out,
       "#33-26 绿树基线：check_all.py docs 0 错误、exit 0", f"exit={code} {out[-200:]}")
    ok("压缩代价 A 表 ↔ readings.json：6/6 家逐格比对" in out,
       "#33-26a 绿树基线：A 表 6 家逐格比对通过")

    # —— a：A 表漂移（readings.json 改成旧数 5/9）必须报错 ——
    d = fresh()
    rp = d / "systems" / "readings.json"
    j = json.loads(rp.read_text(encoding="utf-8"))
    j["压缩代价"]["systems"]["lingshu"]["覆盖_严格"] = "5/9"
    rp.write_text(json.dumps(j, ensure_ascii=False, indent=1), encoding="utf-8")
    code, out = docs_check(d)
    ok(code != 0 and "灵枢" in out and "5/9" in out and "A 表" in out,
       "#33-26a A 表与 readings.json 不一致 ⇒ 报错", f"exit={code} {out[-200:]}")

    # —— b：写「单调」但链非降不成立 ⇒ 报错 ——
    d = fresh()
    dp = d / DOC
    dp.write_text(dp.read_text(encoding="utf-8") +
                  "\n★ 律二：无筛选的 BM25 9/9 ＜ Hindsight 1/9——单调。\n", encoding="utf-8")
    code, out = docs_check(d)
    ok(code != 0 and "非降不成立" in out,
       "#33-26b 「单调」行里 x/9 序列非降不成立 ⇒ 报错", f"exit={code} {out[-200:]}")

    # —— b'：引用 A 表里没有的读数 ⇒ 报错 ——
    d = fresh()
    dp = d / DOC
    dp.write_text(dp.read_text(encoding="utf-8") +
                  "\n★ 单调：BM25 9/9 ＜ 某家 7/9。\n", encoding="utf-8")
    code, out = docs_check(d)
    ok(code != 0 and "A 表里没有的读数 7/9" in out,
       "#33-26b 「单调」行引用 A 表里没有的读数 ⇒ 报错", f"exit={code} {out[-200:]}")

    # —— c：旧文原句（「原文检索两家 5/9」）必须被拦下 ——
    d = fresh()
    dp = d / DOC
    dp.write_text(dp.read_text(encoding="utf-8") +
                  "\n★ 律二：Hindsight 1/9 ＜ MemOS 2/9 ＜ Mem0 3/9（宽松）＜ 原文检索两家 5/9"
                  " ＜ 无筛选的 BM25 9/9——单调。\n", encoding="utf-8")
    code, out = docs_check(d)
    ok(code != 0 and "两家 5/9" in out and "只有 1 家" in out,
       "#33-26c 旧文「原文检索两家 5/9」⇒ 家数不符报错", f"exit={code} {out[-260:]}")

    total = len(_PASS) + len(_FAIL)
    print("")
    print("===== SUMMARY %d/%d 通过 =====" % (len(_PASS), total))
    if _FAIL:
        print("失败项：")
        for m in _FAIL:
            print("  - " + m)
        return 1
    print("VERDICT=PASS（压缩代价文档口径守卫全绿）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
