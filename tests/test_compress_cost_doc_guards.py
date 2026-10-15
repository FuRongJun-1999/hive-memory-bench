#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""压缩代价文档口径守卫（issue #33 第八项 / P1-26；issue #45-4 续修）。

覆盖：文档的「律」不得被同文表格推翻，且判据是机械的：
  #33-26a A 表（「保住那一块」严格／宽松两列）与 `systems/readings.json` 逐格一致；
          旧文把灵枢 v0.7.1 的 2/9 写成更新前的 5/9。
  #45-4   律二（「压缩越狠丢得越彻底」）**不是单调律，也不是「同一口径内成立」**：守卫按
          `逐字率`（切A／切B 的 L1_逐字率均值）给 A 表排序、机械复算「更狠却覆盖更高」的
          反例对，与 `readings.json` 的 `律二反例` 对账，再要求 doc 与 README 的律二段
          **逐条把反例写成一句可核对的对比**；并禁止「同一口径内成立」这类免责句。
          旧文正是靠这句免责把反例挡在门外（实测两种口径各自都有反例，共 4 条）。
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
    ok("压缩代价 律二／律三 口径守卫：0 处不符（律二反例 4 条）" in out,
       "#45-4 绿树基线：律二反例 4 条全部在 doc 与 README 里写出来")

    # —— a：A 表漂移（readings.json 改成旧数 5/9）必须报错 ——
    d = fresh()
    rp = d / "systems" / "readings.json"
    j = json.loads(rp.read_text(encoding="utf-8"))
    j["压缩代价"]["systems"]["lingshu"]["覆盖_严格"] = "5/9"
    rp.write_text(json.dumps(j, ensure_ascii=False, indent=1), encoding="utf-8")
    code, out = docs_check(d)
    ok(code != 0 and "灵枢" in out and "5/9" in out and "A 表" in out,
       "#33-26a A 表与 readings.json 不一致 ⇒ 报错", f"exit={code} {out[-200:]}")

    # —— b1：`逐字率` 声明漂移 ⇒ 报错 ——
    d = fresh()
    rp = d / "systems" / "readings.json"
    j = json.loads(rp.read_text(encoding="utf-8"))
    j["压缩代价"]["逐字率"]["memos"] = 50.0
    rp.write_text(json.dumps(j, ensure_ascii=False, indent=1), encoding="utf-8")
    code, out = docs_check(d)
    ok(code != 0 and "逐字率" in out and "不一致" in out,
       "#45-4 `逐字率` 声明与切A／切B 复算不一致 ⇒ 报错", f"exit={code} {out[-240:]}")

    # —— b2：`律二反例` 清单被删掉一条 ⇒ 与机械复算对不上 ⇒ 报错 ——
    d = fresh()
    rp = d / "systems" / "readings.json"
    j = json.loads(rp.read_text(encoding="utf-8"))
    j["压缩代价"]["律二反例"] = j["压缩代价"]["律二反例"][:3]
    rp.write_text(json.dumps(j, ensure_ascii=False, indent=1), encoding="utf-8")
    code, out = docs_check(d)
    ok(code != 0 and "律二反例" in out and "不一致" in out,
       "#45-4 `律二反例` 与机械复算不一致 ⇒ 报错", f"exit={code} {out[-240:]}")

    # —— b3：正文里把反例句删掉（只剩名字列表）⇒ 报错 ——
    d = fresh()
    dp = d / DOC
    t = dp.read_text(encoding="utf-8")
    i = t.find("**严格口径的反例**")
    j2 = t.find("可保留的较弱说法", i)
    assert i > 0 and j2 > i
    dp.write_text(t[:i] + "反例见 `systems/readings.json`。\n" + t[j2:], encoding="utf-8")
    code, out = docs_check(d)
    ok(code != 0 and "没写出反例" in out,
       "#45-4 正文删掉反例句 ⇒ 「没写出反例」报错", f"exit={code} {out[-240:]}")

    # —— b4：把免责句「同一口径内成立」塞回律二段 ⇒ 报错 ——
    d = fresh()
    dp = d / DOC
    t = dp.read_text(encoding="utf-8")
    t = t.replace("★ **律二：压缩越狠，丢得越彻底",
                  "★ **律二：压缩越狠，丢得越彻底（只在同一口径内成立）", 1)
    dp.write_text(t, encoding="utf-8")
    code, out = docs_check(d)
    ok(code != 0 and "同一口径内成立" in out,
       "#45-4 律二段塞回「同一口径内成立」⇒ 报错", f"exit={code} {out[-240:]}")

    # —— b5：README 律二段删掉反例句 ⇒ 报错 ——
    d = fresh()
    mp = d / "README.md"
    t = mp.read_text(encoding="utf-8")
    t = t.replace("反例 4 条：严格 Hindsight 1/9 ＞ Mem0／MemOS 0/9；宽松 Mem0 3/9 ＞ MemOS 2/9，且 ＞ 逐字率 100% 的灵枢 2/9；",
                  "反例见文档。")
    mp.write_text(t, encoding="utf-8")
    code, out = docs_check(d)
    ok(code != 0 and "README.md" in out and "没写出反例" in out,
       "#45-4 README 律二段删掉反例句 ⇒ 报错", f"exit={code} {out[-240:]}")

    # —— b6：免责句在律二段**之外**复活也要拦（全文面守） ——
    d = fresh()
    dp = d / DOC
    dp.write_text(dp.read_text(encoding="utf-8") +
                  "\n（补记：以上只是同一口径内成立的说法。）\n", encoding="utf-8")
    code, out = docs_check(d)
    ok(code != 0 and "同一口径内成立" in out and "免责句" in out,
       "#45-4 免责句在律二段之外复活 ⇒ 全文面守卫报错", f"exit={code} {out[-240:]}")

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
