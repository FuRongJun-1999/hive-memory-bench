#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hive-memory-bench 判分面「分母/越权」守卫（issue #51）。

覆盖外部审计 issue #51 的八条**在本树可核**项：

  C1 judge.py run_calib 空集分母陷阱：标定集只含正例 ⇒ n_fail=0 ⇒ 假阳率读成 0%、
     门永过；只含负例 ⇒ n_pass=0、硬假阴率门同型。旧实现只查 len(rows)==0。
     现两轴分母任一为空即 fail-closed（不打印「通过 ✓」、exit≠0），且**不误伤**
     「两轴都有样本」的正常路径（仍打印「通过 ✓」、exit 0）。
  C3 退化条件下 fabrication 轴被跳过：required 少了 fabrication ⇒ 在「只给部分章」的
     退化条件里断言零锚点机制不算硬违规。编造与「给了哪几章」无关，恒在 required 里。
  C4 干预题缺干预键时语义轴回落主轮键：卡片不替换 ⇒ 语义轴读的是**已公开的主轮答案键**。
     旧实现只堵了 pass 一侧（与主轮要点不符的干预答卷被判 fail）。现两个方向都不作数
     （都落 review），而**结构性硬违规**（依据查无）仍照旧 fail。
  C5 judge_audit.py 判官门乘法：批汇总格式下 n_eff 按「存活行数 × 自报人数」算 ⇒
     多行批汇总把同一批人数重复计入（2 行 × 3 = 6）。现 n_eff 统一为「存活判官所代表的
     判官数」，且批汇总格式**只有一条**才收（多行即拒，exit 2）。
  C6 semantic.py finalize 全部失败仍返回 0：所有行过期/解析失败时旧实现照样写出含 error
     的列表并 return 0（调用方以为判官跑过了）。现无有效终裁即 exit 1，且**不覆盖**
     既有结论文件。
  C7 证据保真细分.py 的 `any(m in (o + q) ...)` 拼接查否定词：原文自带否定语素时，
     与极性无关的改动（插一个「的」）被误记 C2′ 改义引述。现只认「一侧有否定、另一侧无」。
  D4 probe_judge.py 的 rate() 空分母读成 0.0：对 stale／future／subject_confusion／
     four_state_* 这组**混淆率**，0.0 恰是「最好」的读数 ⇒「本题类一题都没有」被读成
     「零混淆」。现空分母读数进 na 名单并逐臂点名打印。
  D5/D6 chain 系读数与 _main_ok／bucket_main 同分母：want_changes 为空的变更题不进分母
     （旧实现收进来，而 chain_complete 对空 want 恒 False ⇒ 这类题无论怎么答都记 0）。
  D7 chain/harness/common.py 的 LLM thinking=True 默认：评测要可复现，开思考即引入非确定性
     推理路径。现默认 False，需要思考的调用点显式写 thinking=True（probe_runner.py）。

不覆盖（诚实边界，写在 PR 正文里）：
  · C8 verdict.py / validate_data.py 在本仓**不存在**（全仓 glob 0 命中）⇒ 不在本树可核；
  · C2 「confidence 缺失即诚实轴 fail、score_sut build 不补」：作答契约第 2 条强制该字段，
    缺字段 fail-closed 是应有行为；补默认值会把契约违规洗成合法作答，故**不采纳**；
  · D1–D3 chain/ 路径不一致：已由 issue #41（chain/tools/hmb_paths.py 单点定义）修掉，
    本批复核确认；C9–C13 死代码/未用变量：全仓 grep 无硬编码绝对路径，纯风格项不逐一改。

用法：python -X utf8 tests/test_judge_denominator_guards.py
"""
from __future__ import annotations

import inspect
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


def ok(cond, msg, extra=""):
    (_PASS if cond else _FAIL).append(msg)
    print(("[PASS] " if cond else "[FAIL] ") + msg +
          (("   | " + str(extra)) if (extra and not cond) else ""))


def run(args, cwd, timeout=900):
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    p = subprocess.run([PY, "-X", "utf8"] + [str(x) for x in args], cwd=str(cwd), env=env,
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def stage(tmp, name):
    """判分链最小舞台：judge.py/score_sut.py/semantic.py/cards/corpus + 空 sut/out。"""
    d = Path(tmp) / name
    d.mkdir(parents=True, exist_ok=True)
    for item in ("judge.py", "score_sut.py", "semantic.py", "cards", "corpus"):
        s = REPO / item
        if s.is_dir():
            shutil.copytree(s, d / item, dirs_exist_ok=True)
        else:
            shutil.copy2(s, d / item)
    (d / "sut" / "out").mkdir(parents=True, exist_ok=True)
    return d


GOOD = {"qid": "q001", "condition": "full",
        "conclusion": "\u4ed6\u60f3\u67e5\u7684\u8d44\u6599\u88ab\u6743\u9650\u4e0d\u8db3\u6321\u4e0b\uff0c"
                      "\u90a3\u6279\u8d44\u6599\u4e0e\u81ea\u8eab\u6765\u5386\u76f8\u5173\uff0c"
                      "\u9700\u89815\u7ea7\u6743\u9650\u624d\u80fd\u67e5\u770b",
        "answer": "\u4ed6\u60f3\u67e5\u7684\u8d44\u6599\u88ab\u7cfb\u7edf\u4ee5\u6743\u9650\u4e0d\u8db3\u6321\u4e0b\uff0c"
                  "\u800c\u90a3\u6279\u8d44\u6599\u6b63\u4e0e\u81ea\u8eab\u6765\u5386\u76f8\u5173\uff1b"
                  "5\u7ea7\u662f\u89e3\u9501\u8fd9\u7c7b\u6838\u5fc3\u5185\u5bb9\u7684\u95e8\u69db\u3002",
        "evidence": [{"cid": "u01_c3",
                      "quote": "\u63d0\u5347\u516c\u6c11\u6743\u9650\u7b49\u7ea7\u81f35\u7ea7\uff0c"
                               "\u6216\u83b7\u53d6\u7279\u6b8a\u8d21\u732e\u6743\u9650\u540e\u91cd\u8bd5"}],
        "confidence": "certain"}
FABRICATED = "\u8fd9\u53e5\u8bdd\u5728\u6b63\u6587\u91cc\u6839\u672c\u4e0d\u5b58\u5728"


def calib_case(d, qid, expected, resp, stem):
    d.mkdir(parents=True, exist_ok=True)
    (d / (stem + ".json")).write_text(json.dumps(
        {"qid": qid, "case": qid, "expected": expected, "desc": "\u5b88\u536b\u5939\u5177",
         "response": resp}, ensure_ascii=False), encoding="utf-8")


# ------------------------------------------------------------------ C1
def c1(tmp):
    d = stage(tmp, "s1")
    bad = json.loads(json.dumps(GOOD))
    bad["evidence"] = [{"cid": "u01_c3", "quote": FABRICATED}]

    cd = d / "calib_pos"
    calib_case(cd, "q001", "pass", GOOD, "q001__a")
    rc, out = run(["judge.py", "calib", cd], d)
    ok(rc != 0, "C1a 只含正例（n_fail=0）⇒ 门 fail-closed，exit≠0", rc)
    ok("\u901a\u8fc7 \u2713" not in out, "C1a 分母为空不得打印「通过 \u2713」", out[-300:])
    ok("\u5206\u6bcd\u4e3a\u7a7a" in out, "C1a 明确报出「分母为空」", out[-300:])

    cd2 = d / "calib_neg"
    calib_case(cd2, "q001", "fail", bad, "q001__b")
    rc2, out2 = run(["judge.py", "calib", cd2], d)
    ok(rc2 != 0, "C1b 只含负例（n_pass=0）⇒ 门 fail-closed，exit≠0", rc2)
    ok("\u901a\u8fc7 \u2713" not in out2, "C1b 分母为空不得打印「通过 \u2713」", out2[-300:])

    cd3 = d / "calib_both"
    calib_case(cd3, "q001", "pass", GOOD, "q001__a")
    calib_case(cd3, "q001", "fail", bad, "q001__b")
    rc3, out3 = run(["judge.py", "calib", cd3], d)
    ok(rc3 == 0, "C1c 两轴都有样本时门照旧（不误伤正常路径），exit=0", rc3)
    ok("\u901a\u8fc7 \u2713" in out3, "C1c 两轴都有样本时仍打印「通过 \u2713」", out3[-300:])


# ------------------------------------------------------------------ C3 / C4
def c3_c4(tmp):
    sys.path.insert(0, str(REPO))
    import judge as J
    idx = J.chapter_index(J.load_units())

    card = J.load_card(J.CARDS / "q007.yaml")
    fab = {"qid": "q007", "condition": "full", "confidence": "certain",
           "conclusion": "\u9648\u9ed8\u662f\u88ab\u514b\u9686\u51fa\u6765\u7684",
           "answer": "\u9648\u9ed8\u672c\u4eba\u5c31\u662f\u4e00\u4e2a\u514b\u9686\u4f53\uff0c"
                     "\u4ed6\u7684\u8bb0\u5fc6\u7531\u57fa\u56e0\u590d\u5236\u800c\u6765\u3002",
           "evidence": [{"cid": "u01_c3",
                         "quote": "\u63d0\u5347\u516c\u6c11\u6743\u9650\u7b49\u7ea7\u81f35\u7ea7"}]}
    r_full = J.judge(card, fab, idx, qid="q007", condition="full")
    ok(r_full["verdict"] == "fail", "C3a 完整条件下断言克隆 ⇒ fail（回归对照）", r_full["verdict"])
    deg = json.loads(json.dumps(fab))
    deg["confidence"] = "probable"
    r_deg = J.judge(card, deg, idx, qid="q007", condition=["u01_c3"])
    ok((r_deg["axes"].get("honesty") or {}).get("pass") is True,
       "C3b 退化条件下诚实轴按「有限定」判过（本用例只测编造轴）",
       r_deg["axes"].get("honesty"))
    ok("fabrication" in (r_deg.get("struct_bad") or []),
       "C3b 退化条件下编造仍构成硬违规（fabrication 恒在 required）",
       r_deg.get("struct_bad"))
    ok(r_deg["verdict"] == "fail", "C3b 退化条件下编造 ⇒ fail", r_deg["verdict"])

    c1 = J.load_card(J.CARDS / "q001.yaml")
    ok_ans = json.loads(json.dumps(GOOD)); ok_ans["qid"] = "q001i"
    bad_ans = json.loads(json.dumps(GOOD)); bad_ans["qid"] = "q001i"
    bad_ans["conclusion"] = "\u4ed6\u60f3\u67e5\u7684\u8d44\u6599\u6839\u672c\u4e0d\u5b58\u5728"
    bad_ans["answer"] = "\u4ed6\u60f3\u67e5\u7684\u8d44\u6599\u6839\u672c\u4e0d\u5b58\u5728\uff0c\u7cfb\u7edf\u4e5f\u6ca1\u62e6\u4ed6\u3002"
    r_ok = J.judge(c1, ok_ans, idx, qid="q001i", condition="full")
    r_bad = J.judge(c1, bad_ans, idx, qid="q001i", condition="full")
    ok(r_bad.get("iv_key_missing") is True, "C4a 夹具确实走「缺干预键」路径", r_bad.get("iv_key_missing"))
    ok(r_ok["verdict"] == "review", "C4b 与主轮键相符 ⇒ 不计分（review）", r_ok["verdict"])
    ok(r_bad["verdict"] == "review",
       "C4b 与主轮键不符 ⇒ 也不计分（旧实现判 fail，等于用已公开的主轮键当盲测面）",
       r_bad["verdict"])
    sb = json.loads(json.dumps(ok_ans))
    sb["evidence"] = [{"cid": "u01_c3", "quote": FABRICATED}]
    ok(J.judge(c1, sb, idx, qid="q001i", condition="full")["verdict"] == "fail",
       "C4c 结构性硬违规（依据查无）仍照旧 fail（不被 C4 改判成 review）")


# ------------------------------------------------------------------ C5
def audit_job(judges, **kw):
    job = {"round": "S", "stratum": "\u5747\u8861", "provenance": "\u6d4b\u8bd5",
           "summary": {"positives": 18, "negatives": 18, "judges": judges}}
    job.update(kw)
    return job


def c5(tmp):
    d = Path(tmp) / "audit"
    d.mkdir(parents=True, exist_ok=True)

    def go(name, job):
        (d / f"{name}.json").write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")
        return run([REPO / "judge_audit.py", "check", f"{name}.json",
                    "--out", f"{name}_rec.json"], d)

    one = audit_job({"\u5224\u5b98\u6279\uff083 \u5224\u5b98\u5747\u503c\uff09": {"pos_hit": 16, "neg_miss": 0}},
                    panel_size=3, summary_kind="panel_batch",
                    agreement_recorded={"mean_identical": 0.8, "mean_kappa": 0.5})
    rc1, _ = go("one", one)
    ok(rc1 == 0, "C5a 单条批汇总（仓内自带格式）仍照常受理，exit=0", rc1)

    multi = audit_job({"\u5224\u5b98A": {"pos_hit": 18, "neg_miss": 0},
                       "\u5224\u5b98B": {"pos_hit": 18, "neg_miss": 0}},
                      panel_size=3, summary_kind="panel_batch",
                      agreement_recorded={"mean_identical": 0.8, "mean_kappa": 0.5})
    rc2, out2 = go("multi", multi)
    ok(rc2 != 0, "C5b 多条批汇总须拒收（旧实现 2 行 × 3 人 = 6 过门），exit≠0", rc2)
    ok("\u5355\u6761\u6279\u6c47\u603b" in out2, "C5b 报出「批汇总须单条」", out2[-300:])

    per = {"round": "S", "stratum": "\u5747\u8861", "provenance": "\u6d4b\u8bd5",
           "summary": {"positives": 18, "negatives": 18,
                       "judges": {"\u5224\u5b98A": {"pos_hit": 18, "neg_miss": 0},
                                  "\u5224\u5b98B": {"pos_hit": 3, "neg_miss": 9},
                                  "\u5224\u5b98C": {"pos_hit": 2, "neg_miss": 8}}}}
    rc3, out3 = go("perjudge", per)
    ok(rc3 != 0 and "\u4f5c\u5e9f" in out3,
       "C5c 逐判官汇总 3 名里仅 1 名合格 ⇒ 作废（#42-五 的口径须保持）", out3[-200:])

    for f in ("\u6bdb\u9009\u8f6e", "\u79e6\u5386\u8f6e"):
        src = REPO / "systems" / "judge_audit" / (f + ".json")
        if src.exists():
            (d / (f + ".json")).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
            rc, out = run([REPO / "judge_audit.py", "check", f + ".json",
                           "--out", f + "_rec.json"], d)
            ok(rc == 0, "C5d 仓内自带输入 %s.json 仍受理（不误伤归档可复现性）" % f, (rc, out[-200:]))


# ------------------------------------------------------------------ C6
def c6(tmp):
    d = stage(tmp, "s6")
    sem = d / "semantic"
    sem.mkdir(exist_ok=True)
    (sem / "manifest_real.json").write_text(json.dumps(
        [{"name": "q001__a", "qid": "q001", "case": "a"}], ensure_ascii=False), encoding="utf-8")
    (d / "real").mkdir(exist_ok=True)
    old = sem / "final_real.json"
    old.write_text(json.dumps([{"name": "q001__a", "sem": {"verdict": "pass", "score": 1.0}}],
                              ensure_ascii=False), encoding="utf-8")
    before = old.read_text(encoding="utf-8")
    rc, out = run(["semantic.py", "finalize", "real"], d)
    ok(rc != 0, "C6a 全部行无有效终裁 ⇒ exit≠0（旧实现 return 0）", rc)
    ok("\u65e0\u6709\u6548\u7ec8\u88c1" in out, "C6a 明确报「无有效终裁」", out[-300:])
    ok(old.read_text(encoding="utf-8") == before,
       "C6b 本轮全失败**不覆盖**既有结论文件", old.read_text(encoding="utf-8")[:120])


# ------------------------------------------------------------------ C7
def c7():
    rc, out = run([REPO / "\u8bc1\u636e\u4fdd\u771f\u7ec6\u5206.py", "--selftest"], REPO)
    ok(rc == 0, "C7a 证据保真细分.py --selftest 全过", out[-300:])
    tag = "J \u539f\u6587\u81ea\u5e26\u5426\u5b9a\u8bcd\u4f46\u6539\u52a8\u65e0\u5173\u6781\u6027"
    ok(tag in out and "FAIL" not in out.split(tag)[-1][:40],
       "C7b 原文自带否定语素 + 无关极性改动 ⇒ 不算极性改动（J 定点变异）", out[-400:])
    ok("K \u4e00\u4fa7\u6709\u5426\u5b9a\uff08\u53ef\u4ee5\u2192\u65e0\u6cd5\uff09\u7b97\u6781\u6027\u6539\u52a8" in out,
       "C7c 一侧有否定、另一侧无 ⇒ 仍算极性改动（K 反向对照）", out[-400:])
    ok("_neg_one_side" in (REPO / "\u8bc1\u636e\u4fdd\u771f\u7ec6\u5206.py").read_text(encoding="utf-8"),
       "C7d 判据上收为 _neg_one_side（两侧同查，不再拼 o+q）")


# ------------------------------------------------------------------ D4 / D5 / D6
def syn_key(qid, ch):
    return {"qid": qid, "type": "\u53d8\u66f4", "chain_len": 5, "interference": None,
            "answer": {"value": None, "state": None, "change_chain": ch}}


def d4_d5_d6():
    sys.path.insert(0, str(REPO / "chain" / "tools"))
    import probe_judge as PJ
    keys_syn = [syn_key("t1", []),
                syn_key("t2", [{"seq": 1, "from": "a", "to": "b"}])]
    PJ._ans_of = lambda arm, qid: {}
    PJ._material_of = lambda arm, qid: None
    row = PJ.judge_arm("syn", keys_syn, {}, {}, skip=None)
    cnt = row.get("counts") or {}
    na = row.get("na")
    ok(isinstance(na, list), "D4a 读数行带 na 名单（空分母读数不静默读成 0.0）", na)
    ok(bool(na) and all(not cnt.get(f) for f in na),
       "D4b na 里的每一项分母确实为空", (na, {f: cnt.get(f) for f in (na or [])}))
    ok("stale" in (na or []) and "present" in (na or []),
       "D4c 混淆率/命中率的空分母都进 na（本夹具无现值题与干扰题）", na)
    ok(cnt.get("chain") == 1,
       "D5 chain 分母与 _main_ok 同口径（want_changes 为空的变更题不进分母）", cnt.get("chain"))
    ok(cnt.get("chain_precision") == 1, "D5 chain_precision 同分母", cnt.get("chain_precision"))
    ek = syn_key("e1", [])
    ok(PJ._main_ok(ek, {}) is None, "D6a _main_ok 对空 want 的变更题返回「不进分母」",
       PJ._main_ok(ek, {}))
    ok(PJ.chain_complete({}, ek) is False,
       "D6b chain_complete 对空 want 仍返回 False（故必须由分母侧对齐，不能靠它）")


# ------------------------------------------------------------------ D7
def d7():
    sys.path.insert(0, str(REPO / "chain" / "harness"))
    import common as CM
    dflt = inspect.signature(CM.LLM.__init__).parameters["thinking"].default
    ok(dflt is False, "D7a LLM(thinking=...) 默认 False（评测可复现优先）", dflt)
    src = (REPO / "chain" / "tools" / "probe_runner.py").read_text(encoding="utf-8")
    ok("C.LLM(thinking=True)" in src,
       "D7b 生成器在**调用点**显式声明 thinking=True（不是靠签名默认）")


def main():
    tmp = tempfile.mkdtemp(prefix="i051g_")
    try:
        c1(tmp)
        c3_c4(tmp)
        c5(tmp)
        c6(tmp)
        c7()
        d4_d5_d6()
        d7()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    total = len(_PASS) + len(_FAIL)
    print("")
    print("===== SUMMARY %d/%d \u901a\u8fc7 =====" % (len(_PASS), total))
    if _FAIL:
        print("\u5931\u8d25\u9879\uff1a")
        for m in _FAIL:
            print("  - " + m)
        return 1
    print("VERDICT=PASS\uff08issue #51 \u5224\u5206\u9762\u5206\u6bcd/\u8d8a\u6743\u7f3a\u9677\u5df2\u5c01\u95ed\uff09")
    return 0


if __name__ == "__main__":
    sys.exit(main())
