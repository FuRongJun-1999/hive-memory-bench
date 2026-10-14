#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hive-memory-bench 状态链探针守卫（chain/tools/probe_judge.py + probe_runner.py）。

覆盖外部审计 issue 的 CLI 级判据（standalone，只用标准库）：
  #20 效度门 ③「链长单调退化」不得放行**逐桶缓升**的臂（每档 < 旧容差 0.05、方向相反）
  #21 四态正确率须分项报（常数 active 臂的 retired/unresolved/absent 须为 0）；
      时点定位须有自己的指标（旧实现里 63 道时点问答对答错都不计分）
  #24 变更链完整率须罚「多列别链的行」（整篇列出 ⇒ 判不过），且召回读数仍可见
  #25 效度门 ③ 须**逐臂**评（不得只评 SUT_ORDER 排第一的臂），逐臂结论入 c3_by_arm
  #23 主体混淆率：影子链索引须非空（旧 synth_log.json 缺 decoy_of ⇒ 该指标恒为 0），
      且「影子链在、索引空」须报错而非静默返回空表
  #31 「同名异体」档的影子主体须与主链**逐字同名**，语料里不得有点名式说明句/区分后缀
  #26 预注册的 ②「破坏方向」须是硬闸：没跑破坏臂 ⇒ passed=False / gate_stage=no-damage-arms；
      三条破坏臂齐备且方向正确 ⇒ ② 过；破坏臂不得被当成被测系统臂进 ③

用法：
    python -X utf8 chain/tools/tests/test_probe_judge_guards.py
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import tempfile
import types
from collections import Counter
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent
CHAIN = TOOLS.parent
_PASS, _FAIL = [], []


def ok(cond, msg, extra=""):
    (_PASS if cond else _FAIL).append(msg)
    print(("[PASS] " if cond else "[FAIL] ") + msg +
          (("   | " + str(extra)) if (extra and not cond) else ""))


def load_pj(out_dir: Path, runs_dir: Path):
    spec = importlib.util.spec_from_file_location("pj", TOOLS / "probe_judge.py")
    pj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pj)
    pj.OUT = out_dir          # ★ 模块级常量改指临时目录：测试绝不写仓库
    pj.RUNS = runs_dir
    return pj


def load_pr():
    """导入 probe_runner（它 import 仓外的 harness common；这里注入桩模块）。"""
    stub = types.ModuleType("common")
    stub.RUNS = Path(tempfile.gettempdir()) / "_hb_probe_runs_stub"
    stub.GEN_MODEL = "stub"
    stub.LLM = object
    sys.modules["common"] = stub
    spec = importlib.util.spec_from_file_location("pr", TOOLS / "probe_runner.py")
    pr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pr)
    return pr


class _SkipRunnerChecks(Exception):
    """旧树（未打补丁）没有破坏臂实现 ⇒ 跳过后续运行器侧检查，但仍留一条 FAIL 记录。"""


def main():
    tmp = Path(tempfile.mkdtemp(prefix="probesut_"))
    try:
        out, runs = tmp / "out", tmp / "runs"
        out.mkdir(parents=True)
        runs.mkdir(parents=True)
        shutil.copy(CHAIN / "keys" / "keys.json", out / "keys.json")
        shutil.copy(CHAIN / "corpus" / "corpus.json", out / "corpus.json")
        shutil.copy(CHAIN / "keys" / "synth_log.json", out / "synth_log.json")
        pj = load_pj(out, runs)
        keys, doc_norms, decoys = pj._corpus_index()
        fp = pj.keys_fp(keys)
        corpus = json.loads((out / "corpus.json").read_text(encoding="utf-8"))
        by_seq = {(c["doc"], c["seq"]): c["text"] for c in corpus}

        def oracle(k):
            seg = by_seq.get((k["doc"], k["sample_at_seq"]), "")
            return dict(value=k["answer"]["value"], state=k["answer"]["state"],
                        at_seq=k["answer"]["at_seq"], chain=k["answer"]["chain"],
                        basis=[{"file": f'{k["doc"]}#{k["sample_at_seq"]}',
                                "line": k["sample_at_seq"], "quote": seg[:40] or "x" * 8}])

        def empty(k):
            return dict(value=None, state=None, at_seq=None, chain=[], basis=[])

        def vb(k):
            return oracle(k) if k["type"] == "现值" else empty(k)

        def good(k):
            return oracle(k) if pj._bucket(k["chain_len"]) == "short" else empty(k)

        def write_arm(name, fn):
            d = runs / f"chain_{name}"
            (d / "sut" / "out").mkdir(parents=True)
            (d / "retrieval").mkdir(parents=True)
            for k in keys:
                (d / "sut" / "out" / f'{k["qid"]}.json').write_text(
                    json.dumps(fn(k), ensure_ascii=False), encoding="utf-8")
                mat = [{"cid": f'{k["doc"]}#{c["seq"]}', "text": c["text"], "score": 1.0}
                       for c in corpus if c["doc"] == k["doc"]]
                (d / "retrieval" / f'{k["qid"]}.json').write_text(
                    json.dumps({"qid": k["qid"], "material": mat}, ensure_ascii=False),
                    encoding="utf-8")
            (d / "manifest.json").write_text(json.dumps(
                {"arm": name, "phase": "ask", "keys_fp": fp, "n_questions": len(keys),
                 "limit": 0, "calib_sample": 0}, ensure_ascii=False), encoding="utf-8")

        # 逐桶缓升的臂（#20）：短/中/长每档上升 < 0.05（与「随链长退化」方向相反）
        mainq = {}
        for k in keys:
            if not k["reconstructible"] and pj._main_ok(k, oracle(k)) is not None:
                mainq.setdefault(pj._bucket(k["chain_len"]), []).append(k["qid"])
        want = {"short": 0.86, "mid": 0.90, "long": 0.94}
        right = {q for b, qs in mainq.items() for q in qs[:round(want[b] * len(qs))]}

        # 整篇列出（#24）：本文档**所有链**的「值→值」行全列上，不答值、不答状态
        lg = json.loads((out / "synth_log.json").read_text(encoding="utf-8"))
        alltr = {}
        for c in lg["chains"]:
            alltr.setdefault(c["doc"], []).extend(
                {"seq": e["seq"], "from": e["frm"], "to": e["to"]} for e in c["events"]
                if e.get("frm") is not None and e.get("to") is not None)

        def dump(k):
            if k["type"] != "变更":
                return empty(k)
            return dict(value=None, state=None, at_seq=None,
                        chain=list(alltr.get(k["doc"], [])), basis=[])

        # 破坏臂（#26）：以 good 为基底按映射表破坏
        def dmg_write(k):
            return empty(k) if k["type"] in ("历史", "变更") else good(k)

        def dmg_retrieval(k):
            if k["type"] == "现值":
                return empty(k)
            a = dict(good(k))
            a["basis"] = []
            return a

        def dmg_present(k):
            a = dict(good(k))
            a["basis"] = []
            return a

        from collections import Counter as _C
        mode = _C(str(k["answer"]["value"]) for k in keys
                  if k["answer"]["value"] is not None).most_common(1)[0][0]

        # #27 占位卷臂：40% 题逐字照抄 do_ask 异常分支写盘的内容
        import random as _rnd
        _fail = set(_rnd.Random(0).sample([k["qid"] for k in keys], int(len(keys) * 0.4)))

        def flaky(k):
            if k["qid"] in _fail:
                return {"qid": k["qid"], "value": None, "state": None, "at_seq": None,
                        "chain": [], "basis": [], "confidence": "unknown",
                        "_error": "APIConnectionError: Connection error."}
            return oracle(k)

        # #28 退役后照报旧值的臂：答案为 null 的题改报链上最后一个旧值 + state=active
        def noretire(k):
            if k["answer"].get("value") is not None:
                return oracle(k)
            olds = [e["to"] for e in (k["answer"].get("chain") or []) if e.get("to")]
            a = oracle(k)
            a["value"] = olds[-1] if olds else "旧值"
            a["state"] = "active"
            return a

        write_arm("oracle", oracle)
        write_arm("flaky", flaky)
        write_arm("noretire", noretire)
        write_arm("vb", vb)
        write_arm("empty", empty)
        write_arm("good", good)
        write_arm("rising", lambda k: oracle(k) if k["qid"] in right else empty(k))
        write_arm("dump", dump)
        write_arm("const", lambda k: dict(value=mode, state="active", at_seq=None,
                                          chain=[], basis=[]))
        write_arm("damage_bad_write", dmg_write)
        write_arm("damage_bad_retrieval", dmg_retrieval)
        write_arm("damage_bad_present", dmg_present)

        names = ["oracle", "vb", "empty", "good", "rising", "dump", "const",
                 "damage_bad_write", "damage_bad_retrieval", "damage_bad_present"]
        rows = {r["arm"]: r for r in pj.judge_arms(names, write=False)}
        ctl = ("vb", "empty")

        # ---- #27：占位卷不得进整臂读数 ----
        mf = runs / "chain_flaky" / "manifest.json"
        mm = json.loads(mf.read_text(encoding="utf-8"))
        mm.update(ok=len(keys) - len(_fail), errors=len(_fail))
        mf.write_text(json.dumps(mm, ensure_ascii=False), encoding="utf-8")
        kept_arms = [r["arm"] for r in pj.judge_arms(["oracle", "flaky"], write=True)]
        excl = {e["arm"]: e.get("exclude_reason", "") for e in
                json.loads((out / "readings_excluded.json").read_text(encoding="utf-8"))}
        ok(kept_arms == ["oracle"] and "flaky" in excl
           and ("占位卷" in excl.get("flaky", "") or "失败" in excl.get("flaky", "")),
           "#27 带 _error 的占位卷（40% 题）不得进整臂读数（进 excluded 并写明原因）",
           f"kept={kept_arms}, flaky_reason={excl.get('flaky')}")

        # ---- #28：退役题须进分母 ----
        nr = {r["arm"]: r for r in pj.judge_arms(["oracle", "noretire"], write=False)}
        n_present = sum(1 for k in keys if not k["reconstructible"] and k["type"] == "现值")
        n_null = sum(1 for k in keys if not k["reconstructible"] and k["type"] == "现值"
                     and k["answer"].get("value") is None)
        ok(nr["oracle"]["counts"]["present"] == n_present and n_null > 0,
           "#28 现值分母含答案为 null 的退役题（旧实现剔除它们）",
           f"denom={nr['oracle']['counts']['present']}, 现值题={n_present}, 其中 null={n_null}")
        ok(nr["noretire"]["present"] < nr["oracle"]["present"]
           and nr["noretire"]["stale"] > nr["oracle"]["stale"],
           "#28 退役后照报旧值的臂：现值须掉、滞后混淆须涨（旧实现两者逐位相同）",
           f"present {nr['noretire']['present']} vs {nr['oracle']['present']}；"
           f"stale {nr['noretire']['stale']} vs {nr['oracle']['stale']}")

        # ---- #20 ----
        rs = rows["rising"]
        seq = [rs["bucket_main"].get(b) for b in ("short", "mid", "long")]
        cal = pj.calibration([rows["vb"], rows["empty"], rs], sut_arm="rising",
                             control_arms=ctl)
        ok(cal["chain_length_monotonic"] is False,
           "#20 逐桶缓升（每档 <0.05、方向相反）不得过 ③", f"buckets={seq}")
        good_cal = pj.calibration([rows["vb"], rows["empty"], rows["good"]],
                                  sut_arm="good", control_arms=ctl)
        ok(good_cal["chain_length_monotonic"] is True,
           "#20 对照：短链对/中长链错的真退化臂仍须过 ③")

        # ---- #21 ----
        cs = rows["const"]
        ok(cs.get("four_state_active") == 1.0 and cs.get("four_state_retired") == 0.0
           and cs.get("four_state_unresolved") == 0.0 and cs.get("four_state_absent") == 0.0,
           "#21 四态须分项报（常数 active 臂的 retired/unresolved/absent 全 0）",
           {s: cs.get(f"four_state_{s}") for s in ("active", "retired", "unresolved", "absent")})
        ok(isinstance(cs.get("four_state_majority"), float),
           "#21 合并数须附多数类基线（合并数被它主导）")
        ok((rows["good"].get("counts") or {}).get("timepoint", 0) > 0
           and rows["good"].get("timepoint") is not None,
           "#21 时点定位须有自己的指标（旧实现里时点问答对答错都不计分）")

        # ---- #23 / #31：影子链与主体混淆率 ----
        lgj = json.loads((out / "synth_log.json").read_text(encoding="utf-8"))
        prim = [c for c in lgj["chains"] if not c["is_decoy"]]
        dec = [c for c in lgj["chains"] if c["is_decoy"]]
        di = pj.decoy_index()
        ok(dec and len(di) == len(dec),
           "#23 影子链索引须非空（旧 synth_log.json 缺 decoy_of ⇒ 主体混淆率恒为 0）",
           f"影子链={len(dec)}, decoy_index={len(di)}")
        good_lg = (out / "synth_log.json").read_text(encoding="utf-8")
        stripped = json.loads(good_lg)
        for c in stripped["chains"]:
            if c.get("is_decoy"):
                c.pop("decoy_of", None)
        (out / "synth_log.json").write_text(json.dumps(stripped, ensure_ascii=False),
                                            encoding="utf-8")
        try:
            pj.decoy_index()
            raised = False
        except RuntimeError:
            raised = True
        (out / "synth_log.json").write_text(good_lg, encoding="utf-8")
        ok(raised, "#23 影子链存在却一条都没索引到 ⇒ 必须报错，不得静默返回空表（恒 0 指标）")

        def wrongsubj(k):
            vals = di.get((k["doc"], k["subject"], k["slot"])) or set()
            v = next((x for x in sorted(vals)
                      if x and x != pj.norm(k["answer"].get("value"))), None)
            if not v:
                return oracle(k)
            return dict(value=v, state="active", at_seq=None, chain=[], basis=[])

        write_arm("wrongsubj", wrongsubj)
        ws = {r["arm"]: r for r in pj.judge_arms(["oracle", "wrongsubj"], write=False)}
        ok(ws["oracle"]["subject_confusion"] == 0.0
           and ws["wrongsubj"]["subject_confusion"] > 0.0
           and (ws["wrongsubj"]["counts"] or {}).get("subject_confusion", 0) > 0,
           "#23 答影子主体值的臂：主体混淆率须 > 0（旧实现任何答卷恒为 0.000）",
           f"oracle={ws['oracle']['subject_confusion']}, "
           f"wrongsubj={ws['wrongsubj']['subject_confusion']}")

        n_hom = sum(1 for d in dec if d.get("decoy_tag") == "同名异体")
        same = [d for d in dec if d.get("decoy_tag") == "同名异体" and any(
            p["doc"] == d["doc"] and p["slot"] == d["slot"] and p["subject"] == d["subject"]
            for p in prim)]
        blob = "".join(c["text"] for c in corpus)
        ok(n_hom > 0 and len(same) == n_hom
           and "同名但并非同一主体" not in blob
           and "·同名者" not in blob and "·下属" not in blob,
           "#31 同名异体档影子主体须与主链逐字同名；语料不得有点名式说明句/区分后缀",
           f"同名异体={n_hom}, 真同名={len(same)}, 说明句={blob.count('同名但并非同一主体')}, "
           f"后缀={blob.count('·同名者') + blob.count('·下属')}")

        # ---- #24 ----
        dp, oo = rows["dump"], rows["oracle"]
        ok(dp.get("chain", 1.0) < 0.2 and dp.get("chain_row_recall") == 1.0,
           "#24 整篇列出别链的行 ⇒ 变更链判不过（而召回读数仍是 1.0）",
           f"chain={dp.get('chain')}, row_recall={dp.get('chain_row_recall')}")
        ok((dp.get("chain_precision") or 1.0) < 0.6
           and oo.get("chain_precision") == 1.0 and oo.get("chain") == 1.0,
           "#24 补精度读数：dump 低、正常臂为 1.0",
           f"dump={dp.get('chain_precision')}, oracle={oo.get('chain_precision')}")

        # ---- #25 ----
        multi = pj.calibration([rows["vb"], rows["empty"], rows["good"], rs],
                               control_arms=ctl)
        m_by = multi.get("c3_by_arm") or {}
        ok(multi["criteria"].get("c3") is False
           and set(m_by) == {"good", "rising"}
           and (m_by.get("good") or {}).get("satisfied") is True
           and (m_by.get("rising") or {}).get("satisfied") is False,
           "#25 ③ 逐臂评：一条单调 + 一条缓升 ⇒ c3 不过，逐臂结论入 c3_by_arm",
           {a: v.get("satisfied") for a, v in m_by.items()})
        one = pj.calibration([rows["vb"], rows["empty"], rows["good"], rs],
                             sut_arm="good", control_arms=ctl)
        ok(one["criteria"].get("c3") is True
           and set(one.get("c3_by_arm") or {}) == {"good"},
           "#25 显式指定单臂 ⇒ 只评该臂（诊断用）")

        # ---- #26 ----
        ok(good_cal["criteria"].get("c_damage", "缺失") is None
           and good_cal["passed"] is False
           and good_cal.get("gate_stage") == "no-damage-arms",
           "#26 没跑破坏臂 ⇒ ② 未评、passed=False、gate_stage=no-damage-arms",
           f"stage={good_cal.get('gate_stage')}, passed={good_cal['passed']}, "
           f"c_damage={good_cal['criteria'].get('c_damage', '缺失')}")
        dmg = [rows["damage_bad_write"], rows["damage_bad_retrieval"],
               rows["damage_bad_present"]]
        dmg_cal = pj.calibration([rows["vb"], rows["empty"], rows["good"]] + dmg,
                                 sut_arm="good", control_arms=ctl)
        ok(dmg_cal["criteria"].get("c_damage") is True and dmg_cal["passed"] is True
           and dmg_cal.get("gate_stage") == "full",
           "#26 三条破坏臂齐备且方向正确 ⇒ ② 过、passed=True",
           f"c_damage={dmg_cal['criteria'].get('c_damage', '缺失')}, "
           f"stage={dmg_cal.get('gate_stage')}")
        ok(set(dmg_cal.get("c3_by_arm") or {}) == {"good"},
           "#26 破坏臂不得被当成被测系统臂进 ③（否则破坏臂自身会拖垮单调性判据）",
           set(dmg_cal.get("c3_by_arm") or {}))
        part = pj.calibration([rows["vb"], rows["empty"], rows["good"],
                               rows["damage_bad_present"]], sut_arm="good", control_arms=ctl)
        ok(part["criteria"].get("c_damage") is False and part["passed"] is False,
           "#26 破坏臂不齐（缺乙/丙）⇒ ② 不过，不得按「跑了一条就算过」放行")

        # ---- #26 运行器侧：破坏臂的扰动是纯函数（无 LLM 也可单测）----
        pr = load_pr()
        if not hasattr(pr, "damage_chapters"):
            ok(False, "#26 运行器未实现破坏臂（probe_runner 里没有 damage_chapters/"
                      "damage_material）——预注册第 2 条无从评")
            raise _SkipRunnerChecks()
        chapters = [{"cid": f"c{i}", "doc": "d", "text": "x" * 10} for i in range(100)]
        kept = pr.damage_chapters(chapters, "bad_write")
        kept2 = pr.damage_chapters(chapters, "bad_write")
        ok(0.60 <= len(kept) / 100 <= 0.80 and kept == kept2
           and pr.damage_chapters(chapters, "") == chapters,
           "#26 乙 bad_write：固定种子丢约 30% 语料块且可复现",
           f"kept={len(kept)}/100")
        mat = [{"cid": f"c{i}", "text": "t", "score": 1.0} for i in range(10)]
        r1 = pr.damage_material(mat, "bad_retrieval")
        ok(len(r1) == 6 and r1 == pr.damage_material(mat, "bad_retrieval")
           and {m["cid"] for m in r1} != {m["cid"] for m in mat[:6]},
           "#26 丙 bad_retrieval：打乱并只留 60%（可复现）", f"n={len(r1)}")
        p1 = pr.damage_material(mat, "bad_present")
        ok(all(set(m) == {"text"} for m in p1) and len(p1) == len(mat),
           "#26 丁 bad_present：剥掉 cid/score（来源字段）", p1[0] if p1 else None)
        # ---- #30：闭卷提示词不得内嵌答案模板 ----
        cp = pr.build_closed_prompt("q001", "某主体当前的值是什么？")
        blob = json.dumps(cp, ensure_ascii=False)
        ok(cp[0]["content"] == pr.CHAIN_SYS and '"absent"' not in blob
           and '"value":null' not in blob.replace(" ", "")
           and "（无材料）" in cp[1]["content"],
           "#30 闭卷臂与正常臂同一份契约、只给空材料（不再把答案模板写进提示词）",
           blob[:200])
        ok(pr.damage_arm_name("bad_write") == "damage_bad_write"
           and {pr.damage_arm_name(k) for k in pr.DAMAGE_KINDS} == set(pj.DAMAGE_MAP),
           "#26 运行器与判分器的破坏臂名/映射表一一对应")
    except _SkipRunnerChecks:
        pass
    except Exception as e:
        ok(False, "守卫套件抛异常", repr(e))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    total = len(_PASS) + len(_FAIL)
    print("")
    print("===== SUMMARY %d/%d 通过 =====" % (len(_PASS), total))
    if _FAIL:
        print("失败项：")
        for m in _FAIL:
            print("  - " + m)
        return 1
    print("VERDICT=PASS（状态链探针守卫全绿）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
