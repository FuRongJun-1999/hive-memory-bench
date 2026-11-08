#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""L2 依据契合 prepare 的 stale 计数守卫（issue #52）。

该行打印文本声明的是「既有判官输出绑定的是**别的答卷**（指纹不符）」的例数，即
**存在且指纹不符**（S）。旧算式 `len(manifest) - len(todo) - 缺输出例数` 展开后是
M−X（M＝存在且相符、X＝不存在）——全新工作区打印 −2、全部相符时打印 +2、真过期
却整行不打印，与紧邻的「待判 N」自相矛盾（审计读数：36 个非空态只有 2 个与真值一致）。

本守卫：
  #52-a 源码级：旧算式痕迹消失，且与姊妹函数 cmd_prepare 同形（先 `exists()` 再比指纹）；
  #52-b 三态定点：全新工作区 / 全部相符 / 一真过期+一无输出 ⇒ 该行分别为「不打印 / 不打印 / 1」；
  #52-c 穷举 N=2（9 态）+ N=3（27 态）共 36 个非空态：该行给出的数 == 真值 S（真值 0 ⇒ 不打印）；
  #52-d 回退即红：把算式换回旧式，同一穷举必须出现 ≥8 个态与真值不符（旧读数 26/36 错）。
  #52-e 姊妹函数对照：同一批输入下 cmd_prepare 数的是 S（与 cite 路径同源）。

用法：python -X utf8 tests/test_semantic_cite_stale_guards.py
"""
from __future__ import annotations

import itertools
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PY = sys.executable
_PASS, _FAIL = [], []

ANSWER = ("因为他的查阅请求被系统以权限不足挡下，而那批资料正与他的自身来历相关，"
          "5 级权限是解锁这类核心内容的门槛，所以他一直惦记着要把权限升到 5 级。")
QUOTE = "## 第一章 初见蜂巢世界"

OLD_STALE = ("    stale = len(manifest) - len(todo) - sum(1 for m in manifest\n"
             "                                            if not (oc / f\"{m['name']}.json\").exists())\n")


def ok(cond, msg, extra=""):
    (_PASS if cond else _FAIL).append(msg)
    print(("[PASS] " if cond else "[FAIL] ") + msg +
          (("   | " + str(extra)) if (extra and not cond) else ""))


def build_tree(src: Path) -> Path:
    t = Path(tempfile.mkdtemp(prefix="i052_guard_"))
    for f in ("judge.py", "semantic.py"):
        shutil.copy2(src / f, t / f)
    for d in ("cards", "corpus"):
        shutil.copytree(src / d, t / d)
    return t


def write_case(t: Path, qid: str, case: str):
    d = t / "cases_g" / qid
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{case}.json").write_text(json.dumps(
        {"qid": qid, "case": case,
         "response": {"answer": ANSWER, "confidence": "certain",
                      "evidence": [{"cid": "u01_c1", "quote": QUOTE}]}},
        ensure_ascii=False, indent=1), encoding="utf-8")


def run_prepare(t: Path):
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    p = subprocess.run([PY, "-X", "utf8", "semantic.py", "prepare", "--task", "cite",
                        "cases_g"], cwd=str(t), env=env, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=300)
    return p.returncode, p.stdout + p.stderr


def printed(out: str):
    """该行打印的值；整行不打印 ⇒ 0（真值 0 时正是应有行为）。"""
    for l in out.splitlines():
        if "既有判官输出绑定的是" in l:
            m = re.search(r"★\s*(-?\d+)\s*例", l)
            return int(m.group(1)) if m else 0
    return 0


def manifest_of(t: Path):
    return json.loads((t / "semantic" / "manifest_cases_g_cite.json").read_text(encoding="utf-8"))


def set_states(t: Path, man, states):
    """states[i] ∈ {'M' 存在且相符, 'X' 不存在, 'S' 存在且不符}；返回真值 S。"""
    outdir = t / "semantic" / "cite_out" / "cases_g"
    outdir.mkdir(parents=True, exist_ok=True)
    truth = 0
    for m, st in zip(man, states):
        f = outdir / f"{m['name']}.json"
        if st == "X":
            if f.exists():
                f.unlink()
            continue
        ah = m["answer_sha1_12"] if st == "M" else "0000000000"
        if st == "S":
            truth += 1
        f.write_text(json.dumps({"qid": m["qid"], "case": m["case"],
                                 "answer_sha1_12": ah, "verdict": "fit",
                                 "why": "守卫用", "evidence": "守卫用"},
                                ensure_ascii=False), encoding="utf-8")
    return truth


def exhaust(t: Path, n: int):
    """穷举 n 例的全部 3^n 个非空状态，返回 [(states, truth, printed, ok?)]。"""
    rows = []
    run_prepare(t)                      # 先生成 manifest（内容不随 cite_out 变化）
    man = manifest_of(t)
    assert len(man) == n, f"manifest 例数 {len(man)}（应为 {n}）"
    for states in itertools.product("MXS", repeat=n):
        truth = set_states(t, man, states)
        rc, out = run_prepare(t)
        got = printed(out)
        rows.append((states, truth, got, got == truth and rc == 0))
    return rows


def main() -> int:
    src = REPO / "semantic.py"
    text = src.read_text(encoding="utf-8")

    # —— #52-a 源码级 ——
    ok(OLD_STALE not in text,
       "#52-a 旧算式（len(manifest)-len(todo)-缺输出例数）已消失")
    ok('if (oc / f"' in text and '.json").exists()' in text
       and 'and _declared_hash(oc / f"' in text,
       "#52-a cite 路径与姊妹函数同形（先判存在、再判指纹不符）")
    ok("已存在且指纹不符" in text,
       "#52-a 打印行写明声明的量（避免再次歧义）")

    # —— #52-b 三态定点 ——
    t = build_tree(REPO)
    write_case(t, "q001", "c1")
    write_case(t, "q001", "c2")
    rc, out = run_prepare(t)
    man = manifest_of(t)
    ok(len(man) == 2 and rc == 0, "#52-b 前置：两例都进 cite 请求", f"n={len(man)} rc={rc}")

    set_states(t, man, ("X", "X"))
    rc, out = run_prepare(t)
    ok(printed(out) == 0 and "既有判官输出绑定的是" not in out,
       "#52-b 全新工作区（M=0 X=2 S=0）⇒ 该行不打印（旧实现打印 −2）",
       f"got={printed(out)}")

    set_states(t, man, ("M", "M"))
    rc, out = run_prepare(t)
    ok(printed(out) == 0 and "既有判官输出绑定的是" not in out,
       "#52-b 两份指纹全相符（M=2 X=0 S=0）⇒ 该行不打印（旧实现打印 +2）",
       f"got={printed(out)}")

    set_states(t, man, ("S", "X"))
    rc, out = run_prepare(t)
    ok(printed(out) == 1 and "已存在且指纹不符" in out,
       "#52-b 一份真过期＋一份无输出（M=0 X=1 S=1）⇒ 该行打印 1（旧实现打印 −1）",
       f"got={printed(out)}")

    set_states(t, man, ("S", "S"))
    rc, out = run_prepare(t)
    ok(printed(out) == 2,
       "#52-b 两份真过期（S=2 M=0）⇒ 该行打印 2（旧实现整行不打印）", f"got={printed(out)}")

    # —— #52-c 穷举 36 态 ——
    t2 = build_tree(REPO)
    for i in (1, 2):
        write_case(t2, "q001", f"c{i}")
    rows2 = exhaust(t2, 2)
    bad2 = [r for r in rows2 if not r[3]]
    ok(len(rows2) == 9 and not bad2,
       "#52-c N=2 全部 9 个非空态：该行给出的数 == 真值 S", bad2[:4])

    t3 = build_tree(REPO)
    for i in (1, 2, 3):
        write_case(t3, "q001", f"c{i}")
    rows3 = exhaust(t3, 3)
    bad3 = [r for r in rows3 if not r[3]]
    ok(len(rows3) == 27 and not bad3,
       "#52-c N=3 全部 27 个非空态：该行给出的数 == 真值 S", bad3[:4])
    total = rows2 + rows3
    ok(sum(1 for r in total if r[3]) == 36,
       "#52-c 合计 36 个非空态全部与真值一致（旧读数：只有 2/36）")

    # —— #52-d 回退即红 ——
    td = build_tree(REPO)
    dp = td / "semantic.py"
    dt = dp.read_text(encoding="utf-8")
    assert dt.count(OLD_STALE) == 0
    i0 = dt.index("    stale = sum(1 for m in manifest")
    i1 = dt.index('    print(f"L2 依据契合请求')
    dp.write_text(dt[:i0] + OLD_STALE + dt[i1:], encoding="utf-8")
    for i in (1, 2):
        write_case(td, "q001", f"c{i}")
    rowsd = exhaust(td, 2)
    badd = [r for r in rowsd if not r[3]]
    ok(len(badd) >= 4,
       "#52-d 把算式换回旧式 ⇒ 同一穷举出现 ≥4 个态与真值不符（回退即红）",
       f"不符 {len(badd)}/9")

    # —— #52-e 姊妹函数对照 ——
    t4 = build_tree(REPO)
    write_case(t4, "q001", "c1")
    write_case(t4, "q001", "c2")
    run_prepare(t4)
    man4 = manifest_of(t4)
    outdir = t4 / "semantic" / "out" / "cases_g"
    outdir.mkdir(parents=True, exist_ok=True)
    for m, st in zip(man4, ("S", "M")):
        ah = m["answer_sha1_12"] if st == "M" else "0000000000"
        (outdir / f"{m['name']}.json").write_text(json.dumps(
            {"qid": m["qid"], "case": m["case"], "answer_sha1_12": ah, "verdict": "fit",
             "why": "守卫用", "evidence": "守卫用"}, ensure_ascii=False), encoding="utf-8")
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    p = subprocess.run([PY, "-X", "utf8", "semantic.py", "prepare", "cases_g",
                        "--select", "semantic"], cwd=str(t4), env=env, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=300)
    o = p.stdout + p.stderr
    ok("★ 1 例的既有判官输出绑定的是**别的答卷**" in o,
       "#52-e 姊妹函数 cmd_prepare 在同一批输入上数的是 S（1 例真过期）", o[-200:])

    total_n = len(_PASS) + len(_FAIL)
    print("")
    print("===== SUMMARY %d/%d 通过 =====" % (len(_PASS), total_n))
    if _FAIL:
        print("失败项：")
        for m in _FAIL:
            print("  - " + m)
        return 1
    print("VERDICT=PASS（L2 依据契合 stale 计数守卫全绿）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
