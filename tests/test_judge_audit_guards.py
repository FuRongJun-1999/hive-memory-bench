#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hive-memory-bench 判官协议守卫 · 第三批（judge_audit.py）。

覆盖 2 条外部审计 issue 的 CLI 级判据（standalone，只用标准库）：
  #13 汇总模式必须与明细模式同口径：登记一致率 30% 不得判「可报值」；未登记一致率至多「只报序」；
      越界读数（pos_hit > positives）与自报 panel_size 必须被拒（exit 2）
  #14 锚覆盖率须设门（漏答锚不得只算已答锚）；恰在 15pp 门槛的判官须合格（浮点容差）
  #33 第十轮审计（判官协议部分）：
      第二项 一致率必须在**非锚条目**上也算（锚上 100% ＋ 被测 100 条相反 ⇒ 不可测）；
             只在锚上算时报告模式至多「只报序」
      第三项 kappa 参与「只报序」下限（kappa ≤ 0 ⇒ 不可测）
      第四项 keep-qualified 剔除后须**重算**一致率；明细模式自报 panel_size 须被忽略

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


def t33(tmp):
    """#33 第二／三／四项：一致率的条目面、kappa 下限、剔除后重算。

    夹具用真实 qid 形状（pos01…／neg01…）：`_anchors` 产出的是 posXX/negXX，
    写成 p0/n0 会让「定点变异」全部落空（判官仍是 100% 合格）。
    """
    anc = [{"qid": f"pos{i:02d}", "expected": "correct"} for i in range(1, 21)] + \
          [{"qid": f"neg{i:02d}", "expected": "incorrect"} for i in range(1, 21)]

    def judge(wrong):
        return {a["qid"]: (("incorrect" if a["expected"] == "correct" else "correct")
                           if a["qid"] in wrong else a["expected"]) for a in anc}

    items = [f"x{i:03d}" for i in range(100)]

    # —— 第二项①：锚上 100%，被测 100 条完全相反 ⇒ 整批一致率被拽到机会水平 ——
    j1 = {a["qid"]: a["expected"] for a in anc}
    j2 = dict(j1)
    for q in items:
        j1[q], j2[q] = "correct", "incorrect"
    code, out, _rec = check(tmp, "t33_scope", {"round": "N", "stratum": "均衡",
                                               "anchors": anc, "judges": {"J1": j1, "J2": j2}})
    ok(code == 1 and "算在 140 条上：锚 40 ＋ 被测 100" in out and "不可测" in out,
       "#33-20 一致率须算在非锚条目上（锚 40 ＋ 被测 100）⇒ 不可测 exit 1（旧实现只看锚 ⇒ 可报值）",
       f"exit={code} {out[-260:]}")

    # —— 第二项②：只在锚上作答 ⇒ 至多「只报序」——
    pure = {a["qid"]: a["expected"] for a in anc}          # 只答锚、不答任何被测条目
    code, out, rec = check(tmp, "t33_anchorsonly", {"round": "O2", "stratum": "均衡",
                                                    "anchors": anc,
                                                    "judges": {"J1": dict(pure), "J2": dict(pure)}})
    ag = (rec or {}).get("agreement") or {}
    ok(code == 0 and rec and rec["report_mode"] == "只报序" and ag.get("scope") == "anchors-only",
       "#33-21 一致率只在锚上算 ⇒ 至多「只报序」（旧实现 ⇒ 可报值）",
       f"exit={code} {rec and rec.get('report_mode')} scope={ag.get('scope')}")

    # —— 第三项：kappa 参与「只报序」下限 ——
    code_p, _, rec_p = check(tmp, "t33_kpos", summary_job(
        agreement_recorded={"mean_identical": 0.60, "mean_kappa": 0.20}))
    code_z, out_z, _ = check(tmp, "t33_kzero", summary_job(
        agreement_recorded={"mean_identical": 0.60, "mean_kappa": 0.00}))
    code_n, _, _ = check(tmp, "t33_kneg", summary_job(
        agreement_recorded={"mean_identical": 0.60, "mean_kappa": -0.25}))
    ok(code_p == 0 and rec_p and rec_p["report_mode"] == "只报序" and code_z == 1 and code_n == 1,
       "#33-22 kappa 0.20 ⇒ 只报序；kappa 0.00／−0.25 ⇒ 不可测 exit 1（旧实现均只报序）",
       f"0.20→{rec_p and rec_p.get('report_mode')} exit={code_p}／0.00 exit={code_z}／−0.25 exit={code_n}")

    # —— 第四项①：keep-qualified 剔除后须重算一致率 ——
    #   A／B 各错 8 锚（80% ⇒ +30pp 合格）且互相不合；X 各错 15 锚（62.5% ⇒ +12.5pp < 15pp 不合格）。
    jA = judge({"pos17", "pos18", "pos19", "pos20", "neg17", "neg18", "neg19", "neg20"})
    jB = judge({"pos13", "pos14", "pos15", "pos16", "neg01", "neg02", "neg03", "neg04"})
    jX = judge({"pos17", "pos18", "pos19", "pos20", "neg17", "neg18", "neg19", "neg20",
                "pos05", "pos06", "pos07", "pos08", "neg05", "neg06", "neg07"})
    judges = {"A": jA, "B": jB}
    for i in range(10):
        judges[f"X{i}"] = dict(jX)
    d = Path(tmp) / "t33_keep"
    d.mkdir(parents=True, exist_ok=True)
    (d / "job.json").write_text(json.dumps({"round": "K2", "stratum": "均衡",
                                            "anchors": anc, "judges": judges},
                                           ensure_ascii=False), encoding="utf-8")
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    p = subprocess.run([PY, "-X", "utf8", str(REPO / "judge_audit.py"), "check", "job.json",
                        "--policy", "keep-qualified", "--out", "rec.json"],
                       cwd=str(d), env=env, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=300)
    rec2 = None
    if (d / "rec.json").exists():
        rec2 = json.loads((d / "rec.json").read_text(encoding="utf-8"))["rounds"]["K2"]
    pairs = ((rec2 or {}).get("agreement") or {}).get("pairs") or []
    ok(p.returncode == 0 and len(pairs) == 1 and pairs[0]["pair"] == ["A", "B"]
       and abs(pairs[0]["identical"] - 0.6) < 1e-9 and len(rec2.get("voided_judges") or []) == 10,
       "#33-23 keep-qualified 剔除 10 份不合格判官后须只在合格判官间重算（旧实现 pairs=66、含被剔判官）",
       f"exit={p.returncode} pairs={len(pairs)} 同分={pairs and pairs[0]['identical']} "
       f"剔除={rec2 and len(rec2.get('voided_judges') or [])}")

    # —— 第四项②：明细模式自报 panel_size 须被忽略（固定按 1 计）——
    code, out, _rec = check(tmp, "t33_panel1", {"round": "P1", "stratum": "均衡", "panel_size": 2,
                                                "anchors": anc, "judges": {"J1": dict(j1)}})
    ok(code == 1 and "1×1" in out,
       "#33-24 明细模式单判官自报 panel_size=2 不得凑够 2（旧实现 1×2 ≥ 2 即放行）",
       f"exit={code} {out[-200:]}")
    code, _out, rec = check(tmp, "t33_panel2", {"round": "P2", "stratum": "均衡", "panel_size": 2,
                                                "anchors": anc, "judges": {"J1": dict(j1), "J2": dict(j1)}})
    ok(code == 0 and rec and rec.get("panel_size") == 1 and rec.get("panel_size_ignored") == 2,
       "#33-24 明细模式 panel_size 固定为 1 并留痕（旧实现直接采信自报值）",
       f"exit={code} panel={rec and rec.get('panel_size')} ignored={rec and rec.get('panel_size_ignored')}")


def main():
    tmp = tempfile.mkdtemp(prefix="auditsut_")
    try:
        for fn in (t13, t14, t33):
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
