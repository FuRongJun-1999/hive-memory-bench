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

import hashlib
import json
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


# ★ issue #44-二：臂 → 适配器模块。`probe_runner.make_adapter` 的 import 分支须与这张表一致
#   （守卫套件 `tests/test_probe_judge_guards_r44.py` 逐条比对），避免两处各写一份而漂移。
ADAPTER_MODULES = {
    'bm25': 'naive_bm25',
    'versionblind': 'naive_bm25',
    'lingshu': 'lingshu_adapter',
    'openviking': 'openviking_adapter',
    'mem0': 'mem0_adapter',
    'memos': 'memos_adapter',
    'hindsight': 'hindsight_adapter',
}


def _sha16(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()[:16]


def canon_sha(obj) -> str:
    """对象的规范化 JSON 哈希（sort_keys + 无空白）——「这份数据是哪一份」。"""
    return _sha16(json.dumps(obj, ensure_ascii=False, sort_keys=True,
                             separators=(',', ':')).encode('utf-8'))


def _read_json(p: Path, default):
    try:
        return json.loads(p.read_text(encoding='utf-8'))
    except Exception:                                        # noqa: BLE001
        return default


def data_fp(out: Path | None = None) -> dict:
    """数据指纹：**答案键 ＋ 语料 ＋ 生成日志**三份内容的规范化哈希（issue #44-二）。

    旧的 `keys_fp` 只哈希每题的 [qid, type, value, state, at_seq]：换了语料、换了
    `reconstructible`/`change_chain`/`accept` 都照样「同源」。实测 9f31b1f 重新生成数据后
    keys_fp 一位不变（bda3d94b7f29526a），而语料 93/270 段已改、23 道题的 reconstructible
    翻转——旧数据上跑出的三臂仍被判「同源且完整」进 readings。

    这里对**内容**取哈希（不取文件字节，避免缩进/行尾差异造成假不同源）。运行器写进
    manifest、判分器逐项比对；缺失或不等即判「不同源」。
    """
    o = Path(out) if out else OUT
    return {'keys': canon_sha(_read_json(o / 'keys.json', [])),
            'corpus': canon_sha(_read_json(o / 'corpus.json', [])),
            'synth_log': canon_sha(_read_json(o / 'synth_log.json', {}))}


def adapter_fp(arm: str) -> dict:
    """该臂适配器的身份：模块名 ＋ 文件路径 ＋ 源码哈希（issue #44-二）。

    PR #36 明确邀请第三方用自备适配器出读数（README §9），但 manifest 里此前没有任何
    可核对的身份——同一份答卷出自哪份适配器源码无从复核。
    """
    mod = ADAPTER_MODULES.get(arm)
    h, _kind = harness_dir()
    if not mod or h is None:
        return {}
    p = h / 'adapters' / f'{mod}.py'
    if not p.is_file():
        return {'module': mod, 'file': str(p), 'sha256': ''}
    return {'module': mod, 'file': str(p), 'sha256': _sha16(p.read_bytes())}


def harness_fp() -> dict:
    """harness 身份：`common.py` ＋ `adapters/*.py` 的源码哈希表（issue #44-二）。

    第三方照 README §9 自备适配器＝**替换 adapters/ 下的一个桩文件**，故整目录哈希即可
    覆盖「这份读数出自哪套 harness 代码」；`harness_label()` 只给「本地/仓内」标签。
    """
    h, _kind = harness_dir()
    if h is None:
        return {}
    files = {}
    for p in sorted(list((h / 'adapters').glob('*.py')) + [h / 'common.py']):
        if p.is_file():
            files[str(p.relative_to(h)).replace('\\', '/')] = _sha16(p.read_bytes())
    return files


def harness_label() -> str:
    """人读的来源标签（进读数行，读者能看出数字来自哪套 harness）。"""
    p, kind = harness_dir()
    if kind == "repo":
        return "repo:chain/harness"
    if kind == "local":
        return f"local:{p}"
    return "missing"
