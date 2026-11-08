#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""卡片机检守卫（#33 第九项／第十项）。

覆盖：
  #33-9  空串／纯标点／缺 quote 键不得判「可定位」——norm('') 是任何串的子串，
         旧实现 4 处判式「norm(quote) not in norm(text)」对空串恒放行，
         判分器的排除轴与白名单同样「空则跳过」⇒ 排除轴整体失效。
  #33-10 开放题的 must_exclude 必须过检——旧实现 check_card 在 kind=='open' 时
         提前 return 到 check_open_card，判据 (a) 只在客观题分支，于是开放题
         排除项的 cid 不存在／quote 编造／枚举非法都查不出来（判官却会读到它）。

用法：python -X utf8 tests/test_check_all_guards.py
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
_PASS, _FAIL = [], []


def ok(cond, msg, extra=""):
    (_PASS if cond else _FAIL).append(msg)
    print(("[PASS] " if cond else "[FAIL] ") + msg +
          (("   | " + str(extra)) if (extra and not cond) else ""))


def fresh() -> Path:
    d = Path(tempfile.mkdtemp()) / "r"
    shutil.copytree(ROOT, d, ignore=shutil.ignore_patterns(
        ".git", "sut", "real", "real_*", "semantic", "__pycache__"))
    return d


def check(root: Path):
    """返回 (结果行, 全文, 退出码)。"""
    p = subprocess.run([sys.executable, "-X", "utf8", "check_all.py", "check"], cwd=root,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    tail = [l for l in p.stdout.splitlines() if l.startswith("结果：")]
    return (tail[-1] if tail else "?"), p.stdout, p.returncode


def mutate(root: Path, name: str, fn):
    p = root / "cards" / name
    c = yaml.safe_load(p.read_text(encoding="utf-8"))
    fn(c)
    p.write_text(yaml.safe_dump(c, allow_unicode=True, sort_keys=False), encoding="utf-8")


def main() -> int:
    base, _full, rc = check(ROOT)
    ok(base == "结果：0 错误 / 6 警告" and rc == 0,
       "#33 干净数据基线仍为 0 错误 / 6 警告", f"{base} rc={rc}")

    # —— 第九项：空 quote ——
    def blank_support(c):
        for e in (c.get("supporting_evidence") or []):
            e["quote"] = ""
        for e in (c.get("must_exclude") or []):
            e["quote"] = ""

    d = fresh(); mutate(d, "q001.yaml", blank_support)
    s, full, rc = check(d)
    ok(rc != 0 and "0 错误" not in s and "quote 为空" in full,
       "#33-9 q001 五条 quote 清空 ⇒ 必须报错并非零退出（旧实现 0 错误 rc=0）", f"{s} rc={rc}")

    def punct_only(c):
        for e in (c.get("supporting_evidence") or []):
            e["quote"] = "，。！…"

    d = fresh(); mutate(d, "q001.yaml", punct_only)
    s, _f, rc = check(d)
    ok(rc != 0, "#33-9 纯标点 quote 同样不得判「可定位」", f"{s} rc={rc}")

    def drop_key(c):
        for e in (c.get("supporting_evidence") or []):
            e.pop("quote", None)

    d = fresh(); mutate(d, "q001.yaml", drop_key)
    s, _f, rc = check(d)
    ok(rc != 0, "#33-9 缺 quote 键同样不得判「可定位」", f"{s} rc={rc}")

    def blank_pool(c):
        for e in (c.get("evidence_pool") or []):
            e["quote"] = ""

    d = fresh(); mutate(d, "o053.yaml", blank_pool)
    s, _f, rc = check(d)
    ok(rc != 0, "#33-9 开放题 evidence_pool 空 quote ⇒ 必须报错", f"{s} rc={rc}")

    # —— 第十项：开放题 must_exclude ——
    def bad_excl(c):
        me = c.get("must_exclude") or []
        assert me, "o053 应带 must_exclude（夹具前提）"
        me[0]["cid"] = "u99_c999"
        me[0]["quote"] = "编造XYZ"
        me[0]["exclusion_type"] = "bogus"

    d = fresh(); mutate(d, "o053.yaml", bad_excl)
    s, _f, rc = check(d)
    ok(rc != 0 and "错误" in s and not s.startswith("结果：0"),
       "#33-10 开放题 must_exclude 的 cid/quote/枚举全坏 ⇒ 必须报错（旧实现 0 错误 rc=0）",
       f"{s} rc={rc}")

    def bad_cid_only(c):
        (c.get("must_exclude") or [])[0]["cid"] = "u99_c999"

    d = fresh(); mutate(d, "o053.yaml", bad_cid_only)
    s, full, rc = check(d)
    ok(rc != 0 and "u99_c999" in full, "#33-10 cid 不存在须单列", f"{s} rc={rc}")

    def bad_quote_only(c):
        (c.get("must_exclude") or [])[0]["quote"] = "编造XYZ"

    d = fresh(); mutate(d, "o053.yaml", bad_quote_only)
    s, full, rc = check(d)
    ok(rc != 0 and "无法在" in full, "#33-10 quote 无法定位须单列", f"{s} rc={rc}")

    # 枚举非法只警告（与客观题同口径）
    def bad_type_only(c):
        (c.get("must_exclude") or [])[0]["exclusion_type"] = "bogus"

    d = fresh(); mutate(d, "o053.yaml", bad_type_only)
    s, full, rc = check(d)
    ok(rc == 0 and "exclusion_type" in full,
       "#33-10 枚举非法按警告（与客观题 must_exclude 同口径）", f"{s} rc={rc}")

    total = len(_PASS) + len(_FAIL)
    print("")
    print("===== SUMMARY %d/%d 通过 =====" % (len(_PASS), total))
    if _FAIL:
        print("失败项：")
        for m in _FAIL:
            print("  - " + m)
        return 1
    print("VERDICT=PASS（卡片机检守卫全绿）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
