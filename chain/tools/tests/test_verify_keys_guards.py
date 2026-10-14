#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""状态链答案键核验守卫（issue #33 第五项 / P1-23）。

覆盖：外部核验脚本必须核**判分器真正读的每一个字段**——旧实现只核
`answer.chain`，且现值分支的条件取自被核键自己的 `state=='active'`，
于是 `change_chain`／`accept`／历史/时点/缘由的 `value`、状态归属的 `state`
全无检查：在临时副本里篡改 8 道非可推题，脚本输出**逐字不变**。

用法：python -X utf8 chain/tools/tests/test_verify_keys_guards.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent.parent
CHAIN = REPO / "chain"
VK = CHAIN / "tools" / "verify_keys.py"
PY = sys.executable
_PASS, _FAIL = [], []


def ok(cond, msg, extra=""):
    (_PASS if cond else _FAIL).append(msg)
    print(("[PASS] " if cond else "[FAIL] ") + msg +
          (("   | " + str(extra)) if (extra and not cond) else ""))


def run(root: Path):
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    p = subprocess.run([PY, "-X", "utf8", str(root / "chain" / "tools" / "verify_keys.py")],
                       cwd=str(root), env=env, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=900)
    return p.returncode, p.stdout + p.stderr


def fresh() -> Path:
    d = Path(tempfile.mkdtemp()) / "r"
    shutil.copytree(REPO, d, ignore=shutil.ignore_patterns(
        ".git", "sut", "real", "real_*", "semantic", "__pycache__", "out"))
    return d


def main() -> int:
    code, out = run(REPO)
    ok(code == 0 and "硬不符合计 0 处" in out,
       "#33-23 干净数据基线：硬不符合计 0 处、exit 0", f"exit={code} {out[-160:]}")

    # 临时副本里篡改 8 道**非可推**题的被判分字段
    d = fresh()
    kp = d / "chain" / "keys" / "keys.json"
    keys = json.loads(kp.read_text(encoding="utf-8"))
    base_code, base_out = run(d)
    ok(base_code == 0, "#33-23 副本基线干净（篡改前 exit 0）", f"exit={base_code}")

    def pick(f):
        return next(q for q in keys if not q["reconstructible"] and f(q))

    def P(t, s=None):
        return lambda q: q["type"] == t and (s is None or q["answer"].get("state") == s)

    tampered = []
    hits = [
        ("现值·retired 题值改成 BOGUS", P("现值", "retired"), lambda a: a.update(value="BOGUS")),
        ("现值·active→unresolved 且值改 BOGUS", P("现值", "active"),
         lambda a: a.update(state="unresolved", value="BOGUS")),
        ("历史·值改 BOGUS", P("历史", "active"), lambda a: a.update(value="BOGUS")),
        ("缘由·值改 BOGUS", P("缘由", "active"), lambda a: a.update(value="BOGUS")),
        ("状态归属·active→absent", P("状态归属", "active"), lambda a: a.update(state="absent")),
        ("变更·change_chain 清空", P("变更", "active"), lambda a: a.update(change_chain=[])),
    ]
    for label, f, mut in hits:
        try:
            q = pick(f)
        except StopIteration:
            continue
        mut(q["answer"])
        tampered.append((q["qid"], label))
    # 时点·删 accept 且 state 改 active
    try:
        q = next(q for q in keys if not q["reconstructible"] and q["type"] == "时点"
                 and q["answer"].get("accept"))
        q["answer"].pop("accept")
        q["answer"]["state"] = "active"
        tampered.append((q["qid"], "时点·删 accept 且 state 改 active"))
    except StopIteration:
        pass
    # 现值·at_seq 改成 -1
    try:
        q = pick(P("现值", "active"))
        q["answer"]["at_seq"] = -1
        tampered.append((q["qid"], "现值·at_seq 改成 -1"))
    except StopIteration:
        pass
    kp.write_text(json.dumps(keys, ensure_ascii=False, indent=1), encoding="utf-8")

    code, out = run(d)
    missing = [qid for qid, _lab in tampered if qid not in out]
    ok(len(tampered) >= 8,
       "#33-23 夹具：至少篡改 8 道非可推题", f"{len(tampered)} 道")
    ok(code != 0 and not missing,
       "#33-23 每道被篡改的题都必须报出来（旧实现输出逐字不变）",
       f"exit={code} 未报出={missing}")
    ok("② 逐字段复算" in out and "0 道不符" not in out.split("② 逐字段复算")[1].split(chr(10))[0],
       "#33-23 ② 逐字段复算必须报出不符", out.split("② 逐字段复算")[1][:60] if "② 逐字段复算" in out else "")

    total = len(_PASS) + len(_FAIL)
    print("")
    print("===== SUMMARY %d/%d 通过 =====" % (len(_PASS), total))
    if _FAIL:
        print("失败项：")
        for m in _FAIL:
            print("  - " + m)
        return 1
    print("VERDICT=PASS（答案键核验守卫全绿）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
