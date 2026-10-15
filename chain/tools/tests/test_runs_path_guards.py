#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hive-memory-bench 状态链探针守卫 · 答卷目录同源（第十一轮 P0，issue #41）。

  #41 发布版 harness 写答卷的目录（`chain/harness/common.py` 的 `RUNS`）与判分器读答卷的
      目录（`probe_judge.py:32` 写死的仓外 `membench/dist/记忆系统对比_v1.0/runs`）不是同一个：
      第三方照 `chain/README.md` §8 跑完 bm25 全链，642 份答卷落进 `chain/tools/out/runs`，
      判分器输出 `[]`、rc=0；`calibrate` 两条对照臂 n=0；而在「判分目录里已有旧卷」的机器上，
      判分器发布的还是**另一次运行**的答卷，`keys_fp` 校验照样通过、读数行不带任何来源。

本守卫的判据（全部 CLI／模块级，只用标准库）：
  #41a `hmb_paths.runs_dir()` / `probe_judge.RUNS` / `probe_runner.RUNS` 三者逐字相同，
       且随 `HMB_RUNS` 走；
  #41b 运行器写答卷用的目录就是 `hmb_paths.runs_dir()`（不再读 harness 自己的 `C.RUNS`）；
  #41c 读不到任何答卷时**非零退出**（旧实现空表 + rc=0）；
  #41d `manifest.dir` 与实际读取目录不符 ⇒ 该臂被剔出整臂读数并写明原因；
  #41e 某臂答卷数 n=0 ⇒ ④ 记「未评」（None）而非「过」，`passed` 不得为 True。

用法：
    python -X utf8 chain/tools/tests/test_runs_path_guards.py
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent
CHAIN = TOOLS.parent
REPO = CHAIN.parent
PY = sys.executable
_PASS, _FAIL = [], []


def ok(cond, msg, extra=""):
    (_PASS if cond else _FAIL).append(msg)
    print(("[PASS] " if cond else "[FAIL] ") + msg +
          (("   | " + str(extra)) if (extra and not cond) else ""))


def env_for(runs=None):
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8",
               HMB_HARNESS="repo", DEEPSEEK_API_KEY="dummy")
    env.pop("HMB_RUNS", None)
    if runs is not None:
        env["HMB_RUNS"] = str(runs)
    return env


PATHS_CODE = """
import importlib.util, json, sys
from pathlib import Path
tools = Path(sys.argv[1])
sys.path.insert(0, str(tools))
import hmb_paths
def load(name):
    spec = importlib.util.spec_from_file_location(name, tools / (name + ".py"))
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m
pj = load("probe_judge")
pr = load("probe_runner")
print(json.dumps({"hmb": str(hmb_paths.runs_dir()), "judge": str(pj.RUNS),
                  "runner": str(pr.RUNS), "run_dir": str(pr.run_dir("smoke"))}))
"""


def run_py(args, env, cwd=None):
    return subprocess.run([PY, "-X", "utf8"] + args, cwd=str(cwd or REPO), env=env,
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=300)


def load_pj(out_dir, runs_dir):
    spec = importlib.util.spec_from_file_location("pj41", TOOLS / "probe_judge.py")
    pj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pj)
    pj.OUT = out_dir
    pj.RUNS = runs_dir
    return pj


def t41a(tmp):
    """#41：三方共用同一份目录解析，且随 HMB_RUNS 走。"""
    custom = Path(tmp) / "custom_runs"
    custom.mkdir(parents=True, exist_ok=True)
    p = run_py(["-c", PATHS_CODE, str(TOOLS)], env_for(custom))
    ok(p.returncode == 0, "#41a0 导入 probe_judge / probe_runner 成功", p.stderr[-400:])
    try:
        d = json.loads(p.stdout.strip().splitlines()[-1])
    except Exception:
        ok(False, "#41a0b 路径探针输出可解析", p.stdout[-400:])
        return
    ok(d["hmb"] == d["judge"] == d["runner"],
       "#41a1 判分器与运行器读写的答卷根目录须逐字相同", d)
    ok(Path(d["judge"]).resolve() == custom.resolve(),
       "#41a2 三者都随 HMB_RUNS 走（不再写死仓外路径）", d)
    ok(Path(d["run_dir"]).resolve() == (custom / "chain_smoke").resolve(),
       "#41a3 运行器 run_dir() 落在同一根目录下", d)
    p2 = run_py(["-c", PATHS_CODE, str(TOOLS)], env_for(None))
    try:
        d2 = json.loads(p2.stdout.strip().splitlines()[-1])
    except Exception:
        ok(False, "#41a4 无 HMB_RUNS 时的路径探针输出可解析", p2.stdout[-400:])
        return
    ok(d2["hmb"] == d2["judge"] == d2["runner"] == str(TOOLS / "out" / "runs"),
       "#41a4 无 HMB_RUNS ⇒ 默认落到 chain/tools/out/runs（判分器读得到）", d2)


def t41b(tmp):
    """#41：读不到任何答卷 ⇒ 非零退出（旧实现空表 + rc=0）。"""
    empty = Path(tmp) / "empty_runs"
    empty.mkdir(parents=True, exist_ok=True)
    p = run_py([str(TOOLS / "probe_judge.py")], env_for(empty))
    ok(p.returncode != 0, "#41b1 无答卷时须非零退出", f"rc={p.returncode}")
    ok("没有找到任何答卷" in p.stdout, "#41b2 须写明原因（不是静默空表）", p.stdout[-300:])


def t41c(tmp):
    """#41：manifest.dir 与实际读取目录不符 ⇒ 剔除并写明原因。"""
    out, runs = Path(tmp) / "out41", Path(tmp) / "runs41"
    out.mkdir(parents=True, exist_ok=True)
    runs.mkdir(parents=True, exist_ok=True)
    shutil.copy(CHAIN / "keys" / "keys.json", out / "keys.json")
    shutil.copy(CHAIN / "corpus" / "corpus.json", out / "corpus.json")
    shutil.copy(CHAIN / "keys" / "synth_log.json", out / "synth_log.json")
    pj = load_pj(out, runs)
    fp = pj.keys_fp(pj._corpus_index()[0])
    elsewhere = Path(tmp) / "other_harness" / "runs"
    for arm, mdir in (("bad_dir", elsewhere), ("good_dir", runs / "chain_good_dir")):
        d = runs / f"chain_{arm}"
        (d / "sut" / "out").mkdir(parents=True, exist_ok=True)
        (d / "manifest.json").write_text(json.dumps(
            {"arm": arm, "phase": "ask", "keys_fp": fp, "limit": 0, "dir": str(mdir)},
            ensure_ascii=False), encoding="utf-8")
    pj.judge_arms(["bad_dir", "good_dir"], write=True)
    exc = {r["arm"]: r for r in json.loads(
        (out / "readings_excluded.json").read_text(encoding="utf-8"))}
    ok("bad_dir" in exc and "manifest.dir" in (exc["bad_dir"].get("exclude_reason") or ""),
       "#41c1 manifest.dir 不符的臂须被剔出整臂读数", exc.get("bad_dir"))
    ok("manifest.dir" not in ((exc.get("good_dir") or {}).get("exclude_reason") or ""),
       "#41c2 目录一致的臂不得因目录被判剔除（缺题等原因除外）", exc.get("good_dir"))


def t41d(tmp):
    """#41：某臂 n=0 ⇒ ④ 记「未评」，passed 不得为 True。"""
    out, runs = Path(tmp) / "out41d", Path(tmp) / "runs41d"
    out.mkdir(parents=True, exist_ok=True)
    runs.mkdir(parents=True, exist_ok=True)
    shutil.copy(CHAIN / "keys" / "keys.json", out / "keys.json")
    shutil.copy(CHAIN / "corpus" / "corpus.json", out / "corpus.json")
    shutil.copy(CHAIN / "keys" / "synth_log.json", out / "synth_log.json")
    pj = load_pj(out, runs)
    zero = {"arm": "versionblind", "n": 0, "present": 0.0, "history": 0.0, "chain": 0.0,
            "counts": {"present": 0}, "bucket_main": {}, "bucket_main_n": {}}
    calib = pj.calibration([zero])
    ok(calib["criteria"]["c4"] is None,
       "#41d1 n=0 的臂 ⇒ ④ 判「未评」（None），不得判「过」", calib["criteria"])
    ok(calib["passed"] is False, "#41d2 passed 不得为 True", calib["passed"])
    ok("n=0" in calib["details"], "#41d3 结论行须写明原因", calib["details"][-200:])


def main():
    tmp = tempfile.mkdtemp(prefix="runsguard_")
    try:
        for fn in (t41a, t41b, t41c, t41d):
            try:
                fn(tmp)
            except Exception as e:
                ok(False, fn.__name__ + " 抛异常", repr(e))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print()
    print(f"===== SUMMARY {len(_PASS)}/{len(_PASS) + len(_FAIL)} 通过 =====")
    if _FAIL:
        for m in _FAIL:
            print("  FAILED: " + m)
        print("VERDICT=FAIL（答卷目录同源守卫未全绿）")
        sys.exit(1)
    print("VERDICT=PASS（答卷目录同源守卫全绿）")


if __name__ == '__main__':
    main()
