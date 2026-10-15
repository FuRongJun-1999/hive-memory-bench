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

    # ================= issue #45-2：判分器会读、核验器不核的五类键字段 =================
    # 旧实现把 `reconstructible` 只在 ④ 打印分布、`interference` 只在 ⑤ 打印**日志**分布、
    # `type`／`sample_at_seq`／`question` 全文不核 ⇒ 下面五类篡改后 exit 0、硬不符 0。
    # 每类各用一份干净副本，避免类间互相影响（改 type／sample_at_seq 会反过来影响 ⑧ 的复算）。
    import importlib.util

    def load_synth(root: Path):
        sp = importlib.util.spec_from_file_location("_sy", str(root / "chain" / "tools" / "synth.py"))
        m = importlib.util.module_from_spec(sp)
        sp.loader.exec_module(m)
        return m

    def tamper_case(label: str, head: str, mutate):
        """在干净副本上打一类定点变异，返回（exit, 输出, 期望报出的 qid 列表）。"""
        dd = fresh()
        kp_ = dd / "chain" / "keys" / "keys.json"
        ks = json.loads(kp_.read_text(encoding="utf-8"))
        lg = json.loads((dd / "chain" / "keys" / "synth_log.json").read_text(encoding="utf-8"))
        ix = {(c["doc"], c["subject"], c["slot"]): c
              for c in lg["chains"] if not c.get("is_decoy")}
        qids = mutate(ks, ix, load_synth(dd))
        kp_.write_text(json.dumps(ks, ensure_ascii=False, indent=1), encoding="utf-8")
        code_, out_ = run(dd)
        seg = [l for l in out_.splitlines() if l.startswith(head)]
        reported = [x for x in qids if x in out_]
        ok(code_ != 0 and bool(seg) and "0 道不符" not in (seg[0] if seg else "0 道不符")
           and len(reported) == len(qids) and bool(qids),
           f"#45-2 {label}：篡改后非零退出且逐题报出（旧实现 exit 0、硬不符 0）",
           f"exit={code_}｜{(seg[0] if seg else '（无该行）')[:70]}｜未报出={[x for x in qids if x not in out_]}")
        return code_, out_

    # 类 1：非可推 → 可推（主读数分母 602→582，旧实现只在 ④ 打印分布）
    def m1(ks, ix, SY):
        c = [q for q in ks if not q["reconstructible"]][:8]
        for q in c:
            q["reconstructible"] = True
        return [q["qid"] for q in c]

    # 类 2：干扰档改成 none（判分器用它给主体混淆率分桶；旧实现只打印日志分布）
    def m2(ks, ix, SY):
        c = [q for q in ks if q.get("interference") not in (None, "none")][:8]
        for q in c:
            q["interference"] = "none"
        return [q["qid"] for q in c]

    # 类 3：题类 历史 → 现值（两者复算公式相同，② 照样通过；旧实现全文不核 type）
    def m3(ks, ix, SY):
        c = [q for q in ks if q["type"] == "历史"][:8]
        for q in c:
            q["type"] = "现值"
        return [q["qid"] for q in c]

    # 类 4：历史题取样点换成链上另一事件，答案按新时点一致复算、**题面不动**
    #       （旧实现只要求 sample_at_seq ∈ {事件 seq}，⑥ 只查时点题）
    def m4(ks, ix, SY):
        out_ = []
        for q in ks:
            if q["type"] != "历史":
                continue
            ch = ix.get((q["doc"], q["subject"], q["slot"]))
            if not ch:
                continue
            others = [e["seq"] for e in ch["events"] if e["seq"] != q["sample_at_seq"]]
            if not others:
                continue
            q["sample_at_seq"] = others[0]
            st = SY.state_at(ch["events"], others[0])
            q["answer"].update(value=st["value"], state=st["state"], at_seq=st["at_seq"])
            out_.append(q["qid"])
            if len(out_) >= 8:
                break
        return out_

    # 类 5：题面里的主体换成别的主体（答案键仍是原主体；旧实现全文不核 question）
    def m5(ks, ix, SY):
        out_ = []
        for q in ks:
            if q["type"] != "状态归属" or q.get("slot") not in ("信任对象", "配置值"):
                continue
            other = next((s for s in ("阿禾", "老陈", "小满", "周舟", "无人") if s != q["subject"]), None)
            if not other or q["subject"] not in (q.get("question") or ""):
                continue
            q["question"] = q["question"].replace(q["subject"], other, 1)
            out_.append(q["qid"])
            if len(out_) >= 8:
                break
        return out_

    outs45 = [tamper_case("⑧ reconstructible 逐题复算", "⑧ reconstructible", m1),
              tamper_case("⑨ 干扰档与日志一致", "⑨ 干扰档与日志一致", m2),
              tamper_case("⑩ 题类 ↔ qid 类型段一致", "⑩ 题类 ↔ qid 类型段一致", m3),
              tamper_case("⑪ 题面「第 N 次／章」↔ sample_at_seq", "⑪ 题面「第 N 次", m4),
              tamper_case("⑫ 题面含键里的主体与槽位", "⑫ 题面含键里的主体与槽位", m5)]
    ok(all("硬不符合计 0 处" not in o for _c, o in outs45),
       "#45-2 五类篡改后硬不符合计都不为 0")
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
