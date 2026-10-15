#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hive-memory-bench 状态链探针守卫 · 第十二轮（外部审计 issue #43）。

覆盖 #43 的五项（chain/tools/probe_runner.py ＋ probe_judge.py）：
  一 破坏臂管线三处失效：
     A calibrate 跑了三条破坏臂却不把它们交给判分（c_damage 恒 None）
     B 进程内臂（bm25/versionblind）ask 前用**完整**语料重建 ⇒ 乙 bad_write 是空操作
     C 丁 bad_present 的 verbatim 下降来自判分器读的材料件被剥了 cid（与答卷无关）
  二 门② 判据：基底须取该臂自己的 manifest.base_arm；须查「不是整机一起塌」；
     两两可分只在三条臂映射指标的并集上算
  三 时点指标：tp_early/tp_late 曾是同一个列表；timepoint 不计 at_seq
  四 变更链精度：同 seq 下枚举全部 (from,to) 不再算「多列」
  五 _json_ok 须表示「真的解析出了一个 JSON 对象」（旧实现只看正则有没有花括号）

用法：python -X utf8 chain/tools/tests/test_probe_judge_guards_r43.py
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import tempfile
import types
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent
CHAIN = TOOLS.parent
_PASS, _FAIL = [], []


def ok(cond, msg, extra=""):
    (_PASS if cond else _FAIL).append(msg)
    print(("[PASS] " if cond else "[FAIL] ") + msg +
          (("   | " + str(extra)) if (extra and not cond) else ""))


class _StubLLM:
    """确定性桩 LLM：只回一份合法 JSON，不联网。"""

    def __init__(self, *a, **kw):
        self.calls = 0
        self.tokens = 0

    def chat(self, messages, **kw):
        self.calls += 1
        return json.dumps({"qid": "x", "value": None, "state": None, "at_seq": None,
                           "chain": [], "basis": [], "confidence": "unknown"},
                          ensure_ascii=False)


def load_pj(out_dir: Path, runs_dir: Path):
    spec = importlib.util.spec_from_file_location("pj43", TOOLS / "probe_judge.py")
    pj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pj)
    pj.OUT = out_dir
    pj.RUNS = runs_dir
    return pj


def load_pr():
    """导入 probe_runner（它 import 仓外的 harness common；这里注入桩模块）。"""
    stub = types.ModuleType("common")
    stub.RUNS = Path(tempfile.gettempdir()) / "_hb_probe_runs_stub43"
    stub.GEN_MODEL = "stub"
    stub.LLM = _StubLLM
    sys.modules["common"] = stub
    spec = importlib.util.spec_from_file_location("pr43", TOOLS / "probe_runner.py")
    pr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pr)
    return pr


def main():
    tmp = Path(tempfile.mkdtemp(prefix="probe43_"))
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

        def write_arm(name, fn, manifest=None):
            d = runs / f"chain_{name}"
            (d / "sut" / "out").mkdir(parents=True, exist_ok=True)
            (d / "retrieval").mkdir(parents=True, exist_ok=True)
            for k in keys:
                (d / "sut" / "out" / f'{k["qid"]}.json').write_text(
                    json.dumps(fn(k), ensure_ascii=False), encoding="utf-8")
                mat = [{"cid": f'{k["doc"]}#{c["seq"]}', "text": c["text"], "score": 1.0}
                       for c in corpus if c["doc"] == k["doc"]]
                (d / "retrieval" / f'{k["qid"]}.json').write_text(
                    json.dumps({"qid": k["qid"], "material": mat}, ensure_ascii=False),
                    encoding="utf-8")
            m = {"arm": name, "phase": "ask", "keys_fp": fp,
                 # ★ issue #44-二：manifest 须带数据指纹，否则整臂被判「不同源」剔除。
                 "data_fp": pj.hmb_paths.data_fp(),
                 "n_questions": len(keys),
                 "limit": 0, "calib_sample": 0}
            m.update(manifest or {})
            (d / "manifest.json").write_text(json.dumps(m, ensure_ascii=False),
                                            encoding="utf-8")

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

        # ---- #43-三：时点方向/定位三臂 ----
        def tp_early(k):
            a = oracle(k)
            if k["type"] == "时点" and isinstance(k["answer"].get("at_seq"), int):
                a["at_seq"] = k["answer"]["at_seq"] - 1
            return a

        def tp_late(k):
            a = oracle(k)
            if k["type"] == "时点" and isinstance(k["answer"].get("at_seq"), int):
                a["at_seq"] = k["answer"]["at_seq"] + 3
            return a

        def tp_noseq(k):
            a = oracle(k)
            if k["type"] == "时点":
                a["at_seq"] = None
            return a

        # ---- #43-四：同一 seq 下枚举全部 (from, to) 组合 ----
        def enum_sut(k):
            if k["type"] != "变更":
                return empty(k)
            rows_ = []
            for r in (k["answer"].get("chain") or []):
                for f in (None, r.get("from"), r.get("to"), "x"):
                    for t in (None, r.get("from"), r.get("to"), "y"):
                        rows_.append({"seq": r["seq"], "from": f, "to": t})
            return dict(value=None, state=None, at_seq=None, chain=rows_, basis=[])

        write_arm("oracle", oracle)
        write_arm("vb", vb)
        write_arm("empty", empty)
        write_arm("good", good)
        write_arm("tp_early", tp_early)
        write_arm("tp_late", tp_late)
        write_arm("tp_noseq", tp_noseq)
        write_arm("enum", enum_sut)

        names = ["oracle", "vb", "empty", "good", "tp_early", "tp_late", "tp_noseq",
                 "enum"]
        rows = {r["arm"]: r for r in pj.judge_arms(names, write=False)}
        ctl = ("vb", "empty")

        # ---- #43-三 ----
        te, tl, tn, oo = (rows["tp_early"], rows["tp_late"], rows["tp_noseq"],
                          rows["oracle"])
        ok(te["timepoint_early"] == 1.0 and te["timepoint_late"] == 0.0
           and tl["timepoint_early"] == 0.0 and tl["timepoint_late"] == 1.0,
           "#43-三 全答早的臂 early=1.0/late=0.0，全答晚的相反（旧实现 tp_early=tp_late 恒等）",
           f"早臂 {te['timepoint_early']}/{te['timepoint_late']}，"
           f"晚臂 {tl['timepoint_early']}/{tl['timepoint_late']}")
        ok(oo["timepoint"] == 1.0 and oo["counts"]["timepoint"] > 0
           and oo["timepoint_early"] == 0.0 and oo["timepoint_late"] == 0.0,
           "#43-三 oracle 的 timepoint=1.0 且早晚方向分母为 0（全对）",
           f"timepoint={oo['timepoint']}, n={oo['counts']['timepoint']}")
        ok(tn["timepoint"] == 0.0 and tn["counts"]["timepoint"] > 0,
           "#43-三 值/状态全对但 at_seq 全错 ⇒ timepoint=0.0（旧实现给满分）",
           f"timepoint={tn['timepoint']}, n={tn['counts']['timepoint']}")

        # ---- #43-四 ----
        en = rows["enum"]
        ok(en["chain"] == 0.0 and en["chain_precision"] < 0.6
           and oo["chain"] == 1.0 and oo["chain_precision"] == 1.0,
           "#43-四 同 seq 下枚举全部 (from,to) ⇒ chain 判不过、精度低（旧口径一行都不算多列）",
           f"enum chain={en['chain']}, precision={en['chain_precision']}")

        # ---- #43-二①：基底取自各臂自己的 manifest.base_arm ----
        abs_q = [k["qid"] for k in keys
                 if k.get("type") == "状态归属" and k["answer"].get("state") == "absent"]

        def tweak_absent(fn, frac):
            hit = set(abs_q[:round(len(abs_q) * frac)])

            def g(k):
                a = fn(k)
                if k["qid"] in abs_q:
                    a = dict(a, state="absent" if k["qid"] in hit else "retired")
                return a
            return g

        write_arm("damage_bad_write", tweak_absent(good, 1.0), {"base_arm": "good"})
        write_arm("damage_bad_retrieval", tweak_absent(good, 0.5), {"base_arm": "good"})
        write_arm("damage_bad_present", good, {"base_arm": "good"})
        dnames = ["oracle", "vb", "empty", "good", "damage_bad_write",
                  "damage_bad_retrieval", "damage_bad_present"]
        r2 = {r["arm"]: r for r in pj.judge_arms(dnames, write=False)}
        c_zero = pj.calibration([r2["vb"], r2["empty"], r2["oracle"],
                                 r2["damage_bad_write"], r2["damage_bad_retrieval"],
                                 r2["damage_bad_present"]], sut_arm="oracle",
                                control_arms=ctl)
        ok(c_zero["criteria"].get("c_damage") is False and c_zero["passed"] is False
           and all(d.get("base") == "good"
                   for d in c_zero["damage_by_arm"].values()),
           "#43-二① 零破坏副本（基底写在各自 manifest 里）⇒ ② 不过（旧实现拿 SUT_ORDER 首臂当基底）",
           {a: d.get("base") for a, d in c_zero["damage_by_arm"].items()})

        # ---- #43-二②③：三条全空答卷 ----
        write_arm("damage_bad_write", tweak_absent(empty, 1.0), {"base_arm": "good"})
        write_arm("damage_bad_retrieval", tweak_absent(empty, 0.0), {"base_arm": "good"})
        write_arm("damage_bad_present", tweak_absent(empty, 0.5), {"base_arm": "good"})
        r3 = {r["arm"]: r for r in pj.judge_arms(dnames, write=False)}
        c_emp = pj.calibration([r3["vb"], r3["empty"], r3["good"],
                                r3["damage_bad_write"], r3["damage_bad_retrieval"],
                                r3["damage_bad_present"]], sut_arm="good",
                               control_arms=ctl)
        ok(c_emp["criteria"].get("c_damage") is False and c_emp["passed"] is False,
           "#43-二②③ 三条全空答卷（只在 absent 小题上「可分」）⇒ ② 不过",
           {a: d.get("unmapped_kept") for a, d in c_emp["damage_by_arm"].items()})

        # ---- #43-二：正对照——三条破坏臂相对各自的基底方向正确 ⇒ ② 过 ----
        write_arm("damage_bad_write", dmg_write, {"base_arm": "good"})
        write_arm("damage_bad_retrieval", dmg_retrieval, {"base_arm": "good"})
        write_arm("damage_bad_present", dmg_present, {"base_arm": "good"})
        r4 = {r["arm"]: r for r in pj.judge_arms(dnames, write=False)}
        c_ok = pj.calibration([r4["vb"], r4["empty"], r4["good"],
                               r4["damage_bad_write"], r4["damage_bad_retrieval"],
                               r4["damage_bad_present"]], sut_arm="good",
                              control_arms=ctl)
        ok(c_ok["criteria"].get("c_damage") is True and c_ok["passed"] is True,
           "#43-二 对照：三条破坏臂相对 manifest.base_arm 方向正确且可分 ⇒ ② 过",
           f"c_damage={c_ok['criteria'].get('c_damage')}")

        # ---- #43-一C：判分器须从 material_full 取 cid/seq（答卷不变 ⇒ verbatim 不变） ----
        k0 = next(k for k in keys if not k["reconstructible"] and k["type"] == "现值")
        seg = by_seq.get((k0["doc"], k0["sample_at_seq"]), "")[:40]
        ans = dict(value=k0["answer"]["value"], state=k0["answer"]["state"],
                   at_seq=k0["answer"]["at_seq"], chain=[],
                   basis=[{"file": f'{k0["doc"]}#{k0["sample_at_seq"]}',
                           "line": k0["sample_at_seq"], "quote": seg or "x" * 8}])
        d5 = runs / "chain_cidstrip"
        (d5 / "sut" / "out").mkdir(parents=True)
        (d5 / "retrieval").mkdir(parents=True)
        full = [{"cid": f'{k0["doc"]}#{c["seq"]}', "text": c["text"], "score": 1.0}
                for c in corpus if c["doc"] == k0["doc"]]
        (d5 / "retrieval" / f'{k0["qid"]}.json').write_text(
            json.dumps({"qid": k0["qid"],
                        "material": [{"text": m["text"]} for m in full],
                        "material_full": full}, ensure_ascii=False), encoding="utf-8")
        m5 = pj._material_of("cidstrip", k0["qid"])
        ok(m5 is not None and bool(m5[1]) and pj.verbatim_ok(ans, m5) is True,
           "#43-一C 材料件被剥 cid 时判分器仍能回源（读 material_full）⇒ verbatim 不变",
           f"cids={len(m5[1]) if m5 else None}, seqs={len(m5[2]) if m5 else None}")
        (d5 / "retrieval" / f'{k0["qid"]}.json').write_text(
            json.dumps({"qid": k0["qid"], "material": [{"text": m["text"]} for m in full]},
                       ensure_ascii=False), encoding="utf-8")
        m5b = pj._material_of("cidstrip", k0["qid"])
        ok(m5b is not None and not m5b[1] and pj.verbatim_ok(ans, m5b) is False,
           "#43-一C 对照：旧格式（只有被剥过的 material）⇒ cid 缺失、依据轴判不过")

        # ---- #43-五：_json_ok 须表示真的解析出 JSON ----
        pr = load_pr()
        a1 = pr.parse_chain_answer('{"value": "600", "state": "active",}', "q1")
        a2 = pr.parse_chain_answer("{value: 600, state: active}", "q1")
        a3 = pr.parse_chain_answer('{"value": "600"}', "q1")
        a4 = pr.parse_chain_answer("（无 JSON）", "q1")
        ok(a1["_json_ok"] is False and a2["_json_ok"] is False
           and a3["_json_ok"] is True and a4["_json_ok"] is False,
           "#43-五 尾逗号/未加引号键 ⇒ _json_ok=False；合法 JSON ⇒ True（旧实现只看正则）",
           f"尾逗号={a1['_json_ok']}, 无引号键={a2['_json_ok']}, 合法={a3['_json_ok']}")

        def badjson(k):
            a = oracle(k)
            if k["qid"] in badset:
                a = dict(a, value=None, state=None, at_seq=None, chain=[], basis=[],
                         _json_ok=False)
            return a

        import random as _rnd
        badset = set(_rnd.Random(0).sample([k["qid"] for k in keys], int(len(keys) * 0.4)))
        write_arm("badjson", badjson)
        kept = [r["arm"] for r in pj.judge_arms(["oracle", "badjson"], write=True)]
        excl = {e["arm"]: e.get("exclude_reason", "") for e in
                json.loads((out / "readings_excluded.json").read_text(encoding="utf-8"))}
        ok(kept == ["oracle"] and "badjson" in excl and "占位卷" in excl.get("badjson", ""),
           "#43-五 40% 题解析失败的臂须进 excluded（旧实现 n_error=0、complete=True）",
           f"kept={kept}, reason={excl.get('badjson')}")

        # ---- #43-一A：calibrate 把三条破坏臂一并交给判分 ----
        calls = {}
        stubj = types.ModuleType("probe_judge")

        def _ja(names, write=True):
            calls["arms"] = list(names)
            return []

        stubj.judge_arms = _ja
        stubj.calibration = lambda readings, limit=0: {"passed": False, "criteria": {},
                                                       "sut_arm": None}
        sys.modules["probe_judge"] = stubj
        _orig = (pr.run_dir, pr.do_ingest, pr.do_ask, pr.OUT)
        try:
            pr.run_dir = lambda arm: tmp / ("rd_" + arm)
            pr.do_ingest = lambda *a, **kw: {}
            pr.do_ask = lambda *a, **kw: {}
            pr.OUT = tmp / "out2"
            pr.OUT.mkdir(parents=True, exist_ok=True)
            pr.do_calibrate(["bm25"], 0)
        finally:
            sys.modules.pop("probe_judge", None)
            (pr.run_dir, pr.do_ingest, pr.do_ask, pr.OUT) = _orig
        want = {"bm25", "damage_bad_write", "damage_bad_retrieval", "damage_bad_present"}
        ok(set(calls.get("arms") or []) == want,
           "#43-一A calibrate 跑完三条破坏臂后须把它们一并交给 judge_arms",
           calls.get("arms"))

        # ---- #43-一B/C：do_ask 对进程内臂按 damage 重建语料、检索件双份存储 ----
        chapters = [{"cid": f"D#{i}", "doc": "D", "seq": i, "text": f"第{i}块正文"}
                    for i in range(1, 11)]
        fkeys = [{"qid": f"q{i:03d}", "type": "现值", "question": f"第{i}题？",
                  "answer": {"value": "v", "state": "active", "at_seq": i},
                  "reconstructible": False, "doc": "D", "seq": i} for i in range(1, 4)]
        seen = {}

        class FakeAd:
            def ingest(self, chs):
                seen["n"] = len(chs)
                return {"n_chapters": len(chs)}

        pr.load_corpus = lambda: list(chapters)
        pr.load_keys = lambda: list(fkeys)
        # ★ issue #44-五：make_adapter 多了 store 形参（库身份随破坏档分叉）。
        pr.make_adapter = lambda arm, store=None: (FakeAd(), None, "stub")
        pr.retrieve_for = lambda arm, ad, q, k: [
            {"cid": f"D#{i}", "text": f"第{i}块正文", "score": 1.0} for i in (1, 2)]
        pr.C.LLM = _StubLLM
        d6 = tmp / "ask_write"
        pr.do_ingest("bm25", d6, 0, damage="bad_write")
        n_ing = seen.get("n")
        pr.do_ask("bm25", d6, 0, damage="bad_write")
        n_ask = seen.get("n")
        n_dmg = len(pr.damage_chapters(chapters, "bad_write"))
        ok(n_ask == n_dmg and n_ask < len(chapters) and n_ask == n_ing,
           "#43-一B do_ask 对进程内臂按同一 damage 重建语料（乙丢约 30%，旧实现用完整语料）",
           f"ingest={n_ing}, ask={n_ask}, damage_chapters={n_dmg}, 全量={len(chapters)}")
        m6 = json.loads((d6 / "manifest.json").read_text(encoding="utf-8"))
        ok(m6.get("n_chapters") == n_ask,
           "#43-一B ask 阶段的 manifest 不得丢掉 ingest 的 n_chapters",
           f"n_chapters={m6.get('n_chapters')} vs {n_ask}")
        d7 = tmp / "ask_present"
        pr.do_ask("bm25", d7, 0, damage="bad_present")
        rj = json.loads((d7 / "retrieval" / "q001.json").read_text(encoding="utf-8"))
        ok(all("cid" not in m for m in rj["material"])
           and all(m.get("cid") for m in rj.get("material_full") or []),
           "#43-一C 丁剥 cid 只影响给被测系统看的那份，material_full 保留 cid",
           f"material={rj['material'][:1]}, full={ (rj.get('material_full') or [])[:1] }")
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
    print("VERDICT=PASS（状态链探针 #43 守卫全绿）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
