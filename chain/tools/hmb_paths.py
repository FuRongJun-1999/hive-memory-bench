# -*- coding: utf-8 -*-
"""状态链轨的目录解析——**唯一一处定义**（issue #41）。

`probe_runner.py`（写答卷）与 `probe_judge.py`（读答卷）必须指向同一个目录。
此前两边各写一份 `RUNS`：运行器跟 harness 走（`HMB_RUNS` 或 `chain/tools/out/runs`），
判分器写死仓外 `membench/dist/记忆系统对比_v1.0/runs`。于是第三方照 `chain/README.md` §8
跑完 bm25 全链，642 份答卷落进 `chain/tools/out/runs`，判分器读的目录不存在、
静默输出空表且 rc=0；而在「判分目录里已有旧卷」的机器上，判分器发布的还是**另一次运行**
的答卷，`keys_fp` 校验照样通过。

解析顺序（两侧共用，故不会错位）：
  HARNESS：`HMB_HARNESS=repo` ⇒ 仓内 `chain/harness/`；否则本地完整 harness 优先、仓内兜底。
  RUNS   ：`HMB_RUNS` ⇒ 用它；否则与**实际使用的 harness** 同侧——
           本地完整 harness ⇒ 它自己的 `runs/`；仓内发布版 ⇒ `chain/tools/out/runs`。
"""
from __future__ import annotations

import os
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent            # chain/tools
CHAIN_DIR = TOOLS_DIR.parent                           # chain
ROOT = CHAIN_DIR.parent                                # 仓根
OUT = TOOLS_DIR / "out"

HARNESS_REPO = CHAIN_DIR / "harness"                   # 随库发布的参考 harness
HARNESS_LOCAL = ROOT / "membench" / "dist" / "记忆系统对比_v1.0" / "harness"
RUNS_REPO = OUT / "runs"
RUNS_LOCAL = ROOT / "membench" / "dist" / "记忆系统对比_v1.0" / "runs"


def prefer_repo() -> bool:
    """`HMB_HARNESS=repo` ⇒ 强制用仓内发布版 harness（不看本机有没有完整 harness）。"""
    return os.environ.get("HMB_HARNESS", "").strip().lower() == "repo"


def harness_dir():
    """返回 `(Path|None, "repo"|"local"|None)`：实际要用的 harness 目录与来源标签。"""
    order = (((HARNESS_REPO, "repo"), (HARNESS_LOCAL, "local")) if prefer_repo()
             else ((HARNESS_LOCAL, "local"), (HARNESS_REPO, "repo")))
    for p, kind in order:
        if (p / "common.py").is_file():
            return p, kind
    return None, None


def runs_dir() -> Path:
    """答卷根目录：`HMB_RUNS` 优先，否则与 `harness_dir()` 同侧。"""
    env = os.environ.get("HMB_RUNS", "").strip()
    if env:
        return Path(env)
    _h, kind = harness_dir()
    return RUNS_LOCAL if kind == "local" else RUNS_REPO


def harness_label() -> str:
    """人读的来源标签（进读数行，读者能看出数字来自哪套 harness）。"""
    p, kind = harness_dir()
    if kind == "repo":
        return "repo:chain/harness"
    if kind == "local":
        return f"local:{p}"
    return "missing"
