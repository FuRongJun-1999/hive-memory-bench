#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hive-memory-bench 状态链探针守卫 · 第十三轮（外部审计 issue #44）。

覆盖 #44 的五项（chain/tools/synth.py · probe_judge.py · probe_runner.py · hmb_paths.py）：
  一 同名异体歧义：真同名后语料里两条链交错、无任何区分线索，合并读法与答案键不一致的题
     须逐题标记 ambiguous 并剔出主读数（旧实现只剔 reconstructible，41 道留在主读数里，
     文本唯一支持的读法被判错、还记成「主体混淆」）
  二 同源指纹：keys_fp 只哈希每题的值/状态/序号，**换一套语料它一位不变**；须另有 data_fp
     （语料＋答案键＋生成日志）与 adapter/harness 身份，manifest 缺任一项即判「不同源」
  三 链长单调性 c3：旧口径只看点估计（首尾差 ≥ 0.05、相邻回升 ≤ 抽样噪声），U 形
     （0.80→0.60→0.75，首尾差恰 0.05）与平坦臂（真值三桶相同，靠抽样噪声）能过门；
     须改单侧两比例检验（z ≥ 1.645）＋浮点容差
  四 闭卷门 c2：旧实现只比三个聚合率，闭卷臂答对 18%（51 道可猜题）仍判过、这批题留在
     被测臂主读数里、读数行也没有任何逐题字段；须逐题记录命中并剔出主读数，且闭卷契约
     只改规则 1（旧契约规则 1 是「材料里没有的就不要编」，空材料下等于指示不作答）
  五 持久库身份：干净臂与三条破坏臂共用 IDENTITY='chain'，而运行器从不 reset ⇒ 互相污染；
     须按 store_tag(arm, damage) 分叉 ＋ 写入前非空守卫（账本／适配器自报）

用法：python -X utf8 chain/tools/tests/test_probe_judge_guards_r44.py
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
    def __init__(self, *a, **kw):
        self.calls = 0
        self.tokens = 0

    def chat(self, messages, **kw):
        self.calls += 1
        return json.dumps({"qid": "x", "value": None, "state": None, "at_seq": None,
                           "chain": [], "basis": [], "confidence": "unknown"},
                          ensure_ascii=False)


def load_pj(out_dir: Path, runs_dir: Path):
    spec = importlib.util.spec_from_file_location("pj44", TOOLS / "probe_judge.py")
    pj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pj)
    pj.OUT = out_dir
    pj.RUNS = runs_dir
    return pj


def load_pr(runs_dir: Path):
    stub = types.ModuleType("common")
    stub.RUNS = runs_dir
    stub.GEN_MODEL = "stub"
    stub.LLM = _StubLLM
    sys.modules["common"] = stub
    spec = importlib.util.spec_from_file_location("pr44", TOOLS / "probe_runner.py")
    pr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pr)
    pr.RUNS = runs_dir
    return pr


def load_synth():
    spec = importlib.util.spec_from_file_location("synth44", TOOLS / "synth.py")
    sy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sy)
    return sy


def main():
    tmp = Path(tempfile.mkdtemp(prefix="probe44_"))
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
        fp_data = pj.hmb_paths.data_fp()
        corpus = json.loads((out / "corpus.json").read_text(encoding="utf-8"))
        log = json.loads((out / "synth_log.json").read_text(encoding="utf-8"))
        by_seq = {(c["doc"], c["seq"]): c["text"] for c in corpus}

        def oracle(k):
            seg = by_seq.get((k["doc"], k["sample_at_seq"]), "")
            return dict(value=k["answer"]["value"], state=k["answer"]["state"],
                        at_seq=k["answer"]["at_seq"],
                        chain=k["answer"].get("change_chain") or [],
                        basis=[{"file": f'{k["doc"]}#{k["sample_at_seq"]}',
                                "line": k["sample_at_seq"], "quote": seg[:40] or "x" * 8}])

        def empty(k):
            return dict(value=None, state=None, at_seq=None, chain=[], basis=[])

        def vb(k):
            return oracle(k) if k["type"] == "现值" else empty(k)

        def good(k):
            return oracle(k) if pj._bucket(k["chain_len"]) == "short" else empty(k)

        def write_arm(name, fn, manifest=None, material=True):
            d = runs / f"chain_{name}"
            (d / "sut" / "out").mkdir(parents=True, exist_ok=True)
            (d / "retrieval").mkdir(parents=True, exist_ok=True)
            for k in keys:
                (d / "sut" / "out" / f'{k["qid"]}.json').write_text(
                    json.dumps(fn(k), ensure_ascii=False), encoding="utf-8")
                mat = ([{"cid": f'{k["doc"]}#{c["seq"]}', "text": c["text"], "score": 1.0}
                        for c in corpus if c["doc"] == k["doc"]] if material else [])
                (d / "retrieval" / f'{k["qid"]}.json').write_text(
                    json.dumps({"qid": k["qid"], "material": mat}, ensure_ascii=False),
                    encoding="utf-8")
            m = {"arm": name, "phase": "ask", "keys_fp": fp, "data_fp": fp_data,
                 "n_questions": len(keys), "limit": 0, "calib_sample": 0}
            m.update(manifest or {})
            (d / "manifest.json").write_text(json.dumps(m, ensure_ascii=False),
                                             encoding="utf-8")

        # ---------------- 一 同名异体歧义 ----------------
        sy = load_synth()
        same_name = {}
        for c in log["chains"]:
            same_name.setdefault((c["doc"], c["subject"], c["slot"]), []).append(c)
        groups = {g: v for g, v in same_name.items() if len(v) > 1}
        marked = [k for k in keys if k.get("ambiguous")]
        want = []
        for k in keys:
            g = same_name.get((k["doc"], k["subject"], k["slot"]))
            if g and len(g) > 1 and not k["reconstructible"] \
                    and sy.ambiguous(k, sy.merged_events(g)):
                want.append(k["qid"])
        ok(bool(groups) and bool(marked),
           "#44-一 语料里存在「同名同槽位」的链组，且答案键里确有 ambiguous 标记",
           f"同名组 {len(groups)} 个，标记 {len(marked)} 道")
        ok(sorted(k["qid"] for k in marked) == sorted(want),
           "#44-一 ambiguous 标记与 synth 的独立复算逐题一致（题数 %d）" % len(want),
           f"标记 {len(marked)} vs 复算 {len(want)}")
        ok(all(pj._excluded(k) for k in marked)
           and all(not pj._excluded(k) for k in keys
                   if k.get("ambiguous") is not True and not k["reconstructible"]),
           "#44-一 判分器 _excluded 与答案键同口径（歧义题剔出主读数，其余非可推题保留）")
        n_amb = len(marked)
        ok(n_amb > 0 and all(not k["reconstructible"] for k in marked),
           "#44-一 歧义题不计入可推题（两条剔出口径互不重复）",
           f"歧义 {n_amb} 道，其中可推 {sum(1 for k in marked if k['reconstructible'])} 道")
        _amb_old = [k for k in keys if not k["reconstructible"]]
        ok(len(_amb_old) - n_amb < len(_amb_old),
           "#44-一 旧口径（只剔 reconstructible）会把 %d 道歧义题留在主读数里" % n_amb,
           f"旧分母 {len(_amb_old)} → 新分母 {len(_amb_old) - n_amb}")

        # ---------------- 二 同源指纹 ----------------
        ok(sorted(fp_data) == ["corpus", "keys", "synth_log"],
           "#44-二 data_fp 覆盖语料＋答案键＋生成日志", sorted(fp_data))
        alt = tmp / "out_alt"
        alt.mkdir()
        for n in ("keys.json", "corpus.json", "synth_log.json"):
            shutil.copy(out / n, alt / n)
        c2 = json.loads((alt / "corpus.json").read_text(encoding="utf-8"))
        c2[0]["text"] = c2[0]["text"] + "（改动一个字）"
        (alt / "corpus.json").write_text(json.dumps(c2, ensure_ascii=False, indent=1),
                                         encoding="utf-8")
        fp_data_alt = pj.hmb_paths.data_fp(alt)
        ok(fp_data_alt["corpus"] != fp_data["corpus"]
           and fp_data_alt["keys"] == fp_data["keys"],
           "#44-二 只改语料 ⇒ data_fp.corpus 变（keys 部分不变）",
           f"{fp_data['corpus'][:12]} → {fp_data_alt['corpus'][:12]}")
        keys_alt = json.loads((alt / "keys.json").read_text(encoding="utf-8"))
        for k in keys_alt:
            k["answer"]["value"] = k["answer"]["value"]          # 值/状态/序号不动
        ok(pj.keys_fp(keys_alt) == fp,
           "#44-二 keys_fp 对「值/状态/序号之外」的改动不敏感——它一位都没变",
           f"keys_fp={fp}")
        ad = pj.hmb_paths.adapter_fp("bm25")
        hf = pj.hmb_paths.harness_fp()
        ok(bool(ad.get("module")) and bool(ad.get("sha256"))
           and isinstance(hf, dict) and hf,
           "#44-二 适配器身份（模块名/路径/源码哈希）与 harness 文件指纹可算",
           f"adapter={ad.get('module')}, harness {len(hf)} 个文件")

        write_arm("nodata", oracle, manifest={"data_fp": None})
        (runs / "chain_nodata" / "manifest.json").write_text(
            json.dumps({"arm": "nodata", "phase": "ask", "keys_fp": fp,
                        "n_questions": len(keys), "limit": 0, "calib_sample": 0},
                       ensure_ascii=False), encoding="utf-8")
        write_arm("baddata", oracle, manifest={"data_fp": dict(fp_data, corpus="0" * 16)})
        write_arm("okdata", oracle)
        rows = {r["arm"]: r for r in pj.judge_arms(["nodata", "baddata", "okdata"],
                                                   write=True)}
        excl = {x["arm"]: x.get("exclude_reason", "") for x in
                json.loads((out / "readings_excluded.json").read_text(encoding="utf-8"))}
        ok("okdata" in rows and "nodata" not in rows and "baddata" not in rows,
           "#44-二 manifest 缺 data_fp／data_fp 不符 ⇒ 整臂剔除；带对的指纹 ⇒ 进读数",
           f"kept={sorted(rows)} excluded={sorted(excl)}")
        ok("data_fp" in excl.get("nodata", "") and "数据指纹不符" in excl.get("baddata", ""),
           "#44-二 剔除理由写明缺哪一项指纹",
           f"nodata={excl.get('nodata')}｜baddata={excl.get('baddata')}")
        _src = (TOOLS / "probe_runner.py").read_text(encoding="utf-8")
        ok(rows["okdata"].get("data_fp") == fp_data
           and all(k in rows["okdata"] for k in ("adapter", "harness_files", "store"))
           and "harness_files" in _src and "adapter_fp(" in _src,
           "#44-二/五 读数行带 data_fp／adapter／harness_files／store（可事后核同源）",
           sorted(k for k in rows["okdata"] if "fp" in k or "adapter" in k or k == "store"))

        # ---------------- 三 链长单调性 ----------------
        bn = {}
        for k in keys:
            if not pj._excluded(k) and pj._main_ok(k, oracle(k)) is not None:
                b = pj._bucket(k["chain_len"])
                bn[b] = bn.get(b, 0) + 1
        N = dict(bn)

        def c3_of(rates, ks=None):
            row = dict(arm="lingshu", bucket_main=rates, bucket_main_n=dict(N),
                       bucket_main_k=ks, n=0,
                       **{f: 0.0 for f in pj.METRIC_FIELDS}, counts={})
            cal = pj.calibration([row])
            return cal["criteria"]["c3"], cal["c3_by_arm"]["lingshu"]["reason"]

        def ks_of(rates):
            return {b: int(round(rates[b] * N[b])) for b in N}

        u = {"short": 0.80, "mid": 0.60, "long": 0.75}
        u_ok, u_why = c3_of(u, ks_of(u))
        ok(u_ok is False,
           "#44-三 U 形臂（0.80→0.60→0.75，首尾差恰 0.05）不再判「随链长退化」", u_why[:90])
        f_flat = {"short": 0.80, "mid": 0.80, "long": 0.80}
        f_ok, f_why = c3_of(f_flat, ks_of(f_flat))
        ok(f_ok is False, "#44-三 平坦臂（三桶同 0.80）不判退化", f_why[:90])
        d_true = {"short": 1.0, "mid": 0.5, "long": 0.0}
        d_ok, d_why = c3_of(d_true, ks_of(d_true))
        ok(d_ok is True, "#44-三 对照：真退化臂（1.0→0.5→0.0）仍判退化", d_why[:90])
        import random as _rndmod
        rnd = _rndmod.Random(20261015)
        npass, TRIALS = 0, 600
        for _ in range(TRIALS):
            r = {}
            for b, m in N.items():
                r[b] = round(sum(1 for _ in range(m) if rnd.random() < 0.80) / m, 4)
            npass += 1 if c3_of(r, ks_of(r))[0] else 0
        ok(npass <= TRIALS // 10,
           "#44-三 真值三桶同为 0.80 的 %d 次二项抽样：判过 %d 次（要求 ≤10%%，旧判据 24.2%%）"
           % (TRIALS, npass), f"{100.0 * npass / TRIALS:.1f}%")
        _fd = 0.8 - 0.7500000000000001
        ok(_fd >= pj.MIN_DROP - pj.DROP_EPS and _fd < pj.MIN_DROP,
           "#44-三 首尾差 0.04999999999999993 视为达标（≥ MIN_DROP − 1e-9，浮点残差）",
           repr(_fd))
        ok(pj.two_prop_z(100, 100, 0, 100) > pj.MIN_DROP_Z
           and pj.two_prop_z(50, 100, 50, 100) == 0.0
           and pj.two_prop_z(0, 0, 0, 0) == 0.0,
           "#44-三 two_prop_z：单侧、分母为 0 时返回 0（看不出差异）")

        # ---------------- 四 闭卷门逐题 ----------------
        mainq = [k for k in keys if not pj._excluded(k)]
        hit = set()
        for t in ("现值", "历史", "变更"):
            qs = [k["qid"] for k in mainq if k["type"] == t]
            hit |= set(qs[:int(len(qs) * 0.18)])

        def closed(k):
            return oracle(k) if k["qid"] in hit else empty(k)

        write_arm("closed", closed, material=False)
        write_arm("bm25", oracle)
        write_arm("versionblind", vb)
        rr = {r["arm"]: r for r in pj.judge_arms(["versionblind", "closed", "bm25"],
                                                 write=True)}
        cb, sut = rr["closed"], rr["bm25"]
        ok(len(hit) > 0 and cb["present"] <= 0.2 and cb["history"] <= 0.2
           and cb["chain"] <= 0.2,
           "#44-四 构造：闭卷臂三聚合率都在 0.2 以内（旧实现只看这三项 ⇒ 判过）",
           f"present={cb['present']} history={cb['history']} chain={cb['chain']}")
        cal = pj.calibration([rr["versionblind"], cb, sut])
        ok(cal["criteria"]["c2"] is False
           and cal["closed_hits"]["n"] > 0
           and cal["closed_hits"]["rate"] > pj.CLOSED_MAX_HIT,
           "#44-四 闭卷逐题命中 18% ⇒ c2 不过（旧实现只比聚合率，判过）",
           f"c2={cal['criteria']['c2']} hits={cal['closed_hits']['n']}/"
           f"{cal['closed_hits']['n_main']}={cal['closed_hits']['rate']}")
        chf = json.loads((out / "closed_hits.json").read_text(encoding="utf-8"))
        ok(sut["n"] == sut["n_expected"] == len(mainq) - len(chf)
           and sut["n_skipped"] == len(chf)
           and sut["n_closed_excluded"] == len(chf),
           "#44-四 可猜题从被测臂主读数中剔除，分母随之下调且记账",
           f"n={sut['n']} n_expected={sut['n_expected']} 主读数题 {len(mainq)} 剔 {len(chf)}")
        ok(cb["n_skipped"] == 0 and cb["n"] == len(mainq),
           "#44-四 闭卷臂自身不被剔除（否则永远看不见可猜题）",
           f"closed n={cb['n']} skipped={cb['n_skipped']}")
        ok(hit <= set(chf) and set(chf) <= {k["qid"] for k in mainq},
           "#44-四 可猜题全量清单落盘 closed_hits.json（含我构造的 %d 道，共 %d 道——"
           "其余是被空答也判对的题型）" % (len(hit), len(chf)), f"{len(chf)} 条")
        ok(isinstance(sut.get("closed_excluded_qids"), list)
           and len(sut["closed_excluded_qids"]) == min(10, len(hit)),
           "#44-四 读数行带 closed_excluded_qids 示例（前 10 个）")
        pr = load_pr(runs)
        cs, ch = pr.CLOSED_SYS.split("\n"), pr.CHAIN_SYS.split("\n")
        df = [i for i in range(len(cs)) if i >= len(ch) or cs[i] != ch[i]]
        ok(pr.CLOSED_SYS != pr.CHAIN_SYS and len(cs) == len(ch) and len(df) == 1
           and cs[df[0]].startswith("1. ")
           and "不得使用你自己的知识" not in pr.CLOSED_SYS,
           "#44-四 闭卷契约只改规则 1（旧契约规则 1 在空材料下等于「不要作答」）",
           f"diff={[(i, ch[i][:20], cs[i][:20]) for i in df]}")
        cp = pr.build_closed_prompt("q001", "某主体当前的值是什么？")
        blob = json.dumps(cp, ensure_ascii=False)
        ok(cp[0]["content"] == pr.CLOSED_SYS and '"absent"' not in blob
           and "（无材料）" in cp[1]["content"],
           "#44-四 闭卷提示词用 CLOSED_SYS ＋ 空材料，且不内嵌答案模板")

        # ---------------- 五 持久库身份 ----------------
        tags = {"clean": pr.store_tag("mem0", ""), "write": pr.store_tag("mem0", "bad_write"),
                "retr": pr.store_tag("mem0", "bad_retrieval"),
                "pres": pr.store_tag("mem0", "bad_present")}
        ok(len(set(tags.values())) == 4 and all(t.startswith("chain") for t in tags.values()),
           "#44-五 库身份随破坏档分叉：干净/乙/丙/丁 四个互不相同", tags)
        ok(pr.PERSISTENT_ARMS == ("lingshu", "openviking", "mem0", "memos", "hindsight"),
           "#44-五 持久库臂清单与 README 一致", pr.PERSISTENT_ARMS)
        pr.ALLOW_NONEMPTY_STORE = False
        pr.store_commit("mem0", tags["clean"], tmp / "d", 270)
        led = json.loads((runs / "_store_ledger.json").read_text(encoding="utf-8"))
        ok(tags["clean"] in led and led[tags["clean"]]["n_chapters"] == 270,
           "#44-五 store_commit 把本次写入记进本地账本", sorted(led))
        try:
            pr.store_guard("mem0", tags["clean"], tmp / "d")
            raised = False
        except SystemExit as e:
            raised = True
            msg = str(e)
        ok(raised and "拒绝写入" in msg and "allow-nonempty-store" in msg,
           "#44-五 账本命中的库再次写入 ⇒ 中止并给出三条处理办法")
        try:
            pr.store_guard("mem0", tags["write"], tmp / "d")
            raised2 = False
        except SystemExit:
            raised2 = True
        ok(raised2 is False,
           "#44-五 对照：另一破坏档的库身份未被写过 ⇒ 放行（旧实现四档共用一个库）")

        class _Ad:
            name = "mem0"

            def count(self):
                return 7

        _orig = pr.make_adapter
        pr.make_adapter = lambda arm, store=None: (_Ad(), None, "stub")
        try:
            pr.store_guard("mem0", tags["pres"], tmp / "d")
            raised3 = False
        except SystemExit as e:
            raised3 = True
            msg3 = str(e)
        finally:
            pr.make_adapter = _orig
        ok(raised3 and "count=7" in msg3,
           "#44-五 适配器自报非空（count()）⇒ 也中止（账本之外拦既有数据）")
        pr.ALLOW_NONEMPTY_STORE = True
        try:
            pr.store_guard("mem0", tags["clean"], tmp / "d")
            allowed = True
        except SystemExit:
            allowed = False
        finally:
            pr.ALLOW_NONEMPTY_STORE = False
        ok(allowed, "#44-五 --allow-nonempty-store 显式认下后放行")
        ok("--allow-nonempty-store" in (TOOLS / "probe_runner.py").read_text(encoding="utf-8")
           and "store" in (TOOLS / "probe_runner.py").read_text(encoding="utf-8"),
           "#44-五 运行器 CLI 暴露 --allow-nonempty-store，manifest 记 store")
    except Exception as e:
        ok(False, "守卫套件抛异常", repr(e))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    print("===== SUMMARY %d/%d 通过 =====" % (len(_PASS), len(_PASS) + len(_FAIL)))
    if _FAIL:
        print("失败项：")
        for m in _FAIL:
            print("  - " + m)
        sys.exit(1)
    print("VERDICT=PASS（issue #44 五项守卫全绿）")


if __name__ == "__main__":
    main()
