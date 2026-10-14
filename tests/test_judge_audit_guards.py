#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hive-memory-bench 判官协议守卫 · 第三批（judge_audit.py）。

覆盖 2 条外部审计 issue 的 CLI 级判据（standalone，只用标准库）：
  #13 汇总模式必须与明细模式同口径：登记一致率 30% 不得判「可报值」；未登记一致率至多「只报序」；
      越界读数（pos_hit > positives）与自报 panel_size 必须被拒（exit 2）
  #14 锚覆盖率须设门（漏答锚不得只算已答锚）；恰在 15pp 门槛的判官须合格（浮点容差）

用法：
    python -X utf8 tests/test_judge_audit_guards.py
"""
from __future__ import annotations

import json
import os
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


def check(tmp, name, job):
    """跑 judge_audit.py check，返回 (exit, stdout, 记录 dict|None)。"""
    d = Path(tmp) / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "job.json").write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    p = subprocess.run([PY, "-X", "utf8", str(REPO / "judge_audit.py"), "check", "job.json",
                        "--out", "rec.json"], cwd=str(d), env=env, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=300)
    rec = None
    if (d / "rec.json").exists():
        rec = json.loads((d / "rec.json").read_text(encoding="utf-8"))["rounds"].get(job["round"])
    return p.returncode, p.stdout + p.stderr, rec


def anchors(np_, nn):
    return ([{"qid": f"p{i}", "expected": "correct"} for i in range(np_)]
            + [{"qid": f"n{i}", "expected": "incorrect"} for i in range(nn)])


def summary_job(**kw):
    job = {"round": "S", "stratum": "均衡", "provenance": "测试",
           "summary": {"positives": 9, "negatives": 9,
                       "judges": {"甲批": {"pos_hit": 9, "neg_miss": 0},
                                  "乙批": {"pos_hit": 8, "neg_miss": 0}}}}
    job.update(kw)
    return job


def t13(tmp):
    """#13：汇总模式不审一致率 / 不校验输入。"""
    _, out, rec = check(tmp, "s30", summary_job(
        agreement_recorded={"mean_identical": 0.30, "mean_kappa": 0.05}))
    ok(rec is None or rec["report_mode"] != "可报值",
       "#13a 登记一致率 30% 不得判「可报值」", rec and rec["report_mode"])
    _, _, rec2 = check(tmp, "s60", summary_job(
        agreement_recorded={"mean_identical": 0.60, "mean_kappa": 0.20}))
    ok(rec2 is None or rec2["report_mode"] == "只报序",
       "#13b 与明细模式同口径：同分 60% ⇒ 只报序", rec2 and rec2["report_mode"])
    _, _, rec3 = check(tmp, "snone", summary_job())
    ok(rec3 is None or rec3["report_mode"] != "可报值",
       "#13c 未登记一致率不得默认「可报值」", rec3 and rec3["report_mode"])
    code, out4, _ = check(tmp, "oob", summary_job(
        summary={"positives": 9, "negatives": 9,
                 "judges": {"甲批": {"pos_hit": 30, "neg_miss": 0},
                            "乙批": {"pos_hit": 9, "neg_miss": 0}}}))
    ok(code != 0, "#13d pos_hit=30 > positives=9 须拒绝（非零退出）", code)
    code5, _, _ = check(tmp, "panel", summary_job(panel_size=3))
    ok(code5 != 0, "#13e 自报 panel_size 不得替代逐判官汇总（须拒绝）", code5)


def t14(tmp):
    """#14：覆盖率门 + 门槛容差。"""
    anc = anchors(20, 20)
    few = {"p0": "correct", "n0": "incorrect"}
    code, out, rec = check(tmp, "cov", {"round": "C", "stratum": "均衡", "anchors": anc,
                                        "judges": {"J1": few, "J2": dict(few)}})
    ok(code == 1 and (rec is None or rec["status"] == "void"),
       "#14a 覆盖 5% 的判官须不合格（整批作废、exit 1）", f"exit={code} {out[-200:]}")
    anc2 = anchors(16, 4)
    jj = {}
    for tag, wrong in (("J1", {"p0"}), ("J2", {"p1"})):
        jj[tag] = {a["qid"]: ("incorrect" if a["expected"] == "correct" else "correct")
                   if a["qid"] in wrong else a["expected"] for a in anc2}
    code2, out2, rec2 = check(tmp, "eq", {"round": "E", "stratum": "偏正", "anchors": anc2,
                                          "judges": jj})
    ok(code2 == 0, "#14b 恰在 +15pp 门槛的判官须合格（exit 0）", f"exit={code2} {out2[-200:]}")


def main():
    tmp = tempfile.mkdtemp(prefix="auditsut_")
    try:
        for fn in (t13, t14):
            try:
                fn(tmp)
            except Exception as e:
                ok(False, fn.__name__ + " 抛异常", repr(e))
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
    total = len(_PASS) + len(_FAIL)
    print("")
    print("===== SUMMARY %d/%d 通过 =====" % (len(_PASS), total))
    if _FAIL:
        print("失败项：")
        for m in _FAIL:
            print("  - " + m)
        return 1
    print("VERDICT=PASS（判官协议守卫全绿）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
