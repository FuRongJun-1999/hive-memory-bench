# -*- coding: utf-8 -*-
"""守卫：issue #35 —— harness 随库发布（第三方 clone 即可跑 bm25 臂）。

背景：第三方实测报告（issue #35 §2）指出，`chain/tools/probe_runner.py` 在 import 阶段
即 `ModuleNotFoundError: No module named 'common'`，六个记忆臂全部跑不起来——仓库对外
只提供了「出题 + 判分」半侧。本守卫钉住修复：发布面（`chain/harness/`）齐备、可导入、
参考臂端到端可用、五家桩给出可读报错、且新增面不含内部标识与绝对路径。

绿树（本 PR）全绿；红树（PR #5 head `3f1748a` 与 PR #5 前的 `main` `f4509d7`：无
`chain/harness/`）大面积失败——证明判据咬得住，不是恒真断言。
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "chain" / "harness"
ENV = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")

_results = []


def check(name: str, ok, detail: str = "") -> None:
    _results.append((name, bool(ok)))
    mark = "ok" if ok else "XX"
    line = f"  [{mark}] {name}"
    if detail and not ok:
        line += f"\n        └─ {detail.strip()[:400]}"
    print(line)


def run(args, cwd=ROOT, timeout=300):
    p = subprocess.run([str(a) for a in args], cwd=str(cwd), env=ENV,
                       capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def py(code: str, cwd=ROOT, timeout=300):
    return run([sys.executable, "-X", "utf8", "-c", code], cwd=cwd, timeout=timeout)


# ---------- 1. 发布面齐备 ----------
NEED = ["__init__.py", "common.py", "requirements.txt",
        "adapters/__init__.py", "adapters/base.py", "adapters/_stub.py",
        "adapters/naive_bm25.py", "adapters/lingshu_adapter.py",
        "adapters/openviking_adapter.py", "adapters/mem0_adapter.py",
        "adapters/memos_adapter.py", "adapters/hindsight_adapter.py"]
miss = [n for n in NEED if not (HARNESS / n).is_file()]
check("发布面 chain/harness/ 文件齐备（含五家桩）", not miss, f"缺：{miss}")


# ---------- 2. issue #35 §2.2 的阻塞已解除 ----------
rc, out = run([sys.executable, "-X", "utf8", "chain/tools/probe_runner.py", "--help"])
check("probe_runner.py --help 退出 0（不再 ModuleNotFoundError）",
      rc == 0 and "usage:" in out, f"rc={rc} {out[-300:]}")


# ---------- 3. 缺 harness 时给可读报错（不是 ModuleNotFoundError） ----------
tmp = Path(tempfile.mkdtemp(prefix="hmb_noharness_"))
try:
    shutil.copytree(ROOT, tmp / "repo",
                    ignore=shutil.ignore_patterns(".git", "__pycache__", "out",
                                                  "sut", "real*", "semantic"))
    shutil.rmtree(tmp / "repo" / "chain" / "harness", ignore_errors=True)
    rc2, out2 = run([sys.executable, "-X", "utf8", "chain/tools/probe_runner.py",
                     "--help"], cwd=tmp / "repo")
    check("缺 harness 时报错可读（写明找过哪些路径、指向 chain/harness）",
          rc2 != 0 and "找不到 harness" in out2 and "ModuleNotFoundError" not in out2,
          f"rc={rc2} {out2[-300:]}")
finally:
    shutil.rmtree(tmp, ignore_errors=True)


# ---------- 4. common.py 的发布子集接口 ----------
CODE_COMMON = (
    "import sys, json; sys.path.insert(0, 'chain/harness'); import common as C; "
    "names = ['RUNS', 'GEN_MODEL', 'LLM', 'norm', 'hit', 'chunk_chapters', 'load_corpus']; "
    "print(json.dumps([n for n in names if hasattr(C, n)]))")
rc4, out4 = py(CODE_COMMON)
try:
    have = json.loads(out4.strip().splitlines()[-1]) if rc4 == 0 else []
except Exception:
    have = []
check("common.py 提供 RUNS/GEN_MODEL/LLM/norm/hit/chunk_chapters/load_corpus",
      rc4 == 0 and len(have) == 7, f"rc={rc4} 有={have} {out4[-200:]}")


# ---------- 5. 契约是 ABC（写适配器必须实现 ingest/retrieve） ----------
CODE_ABC = (
    "import sys; sys.path.insert(0, 'chain/harness'); "
    "from adapters.base import MemoryAdapter as M; "
    "print(sorted(M.__abstractmethods__))")
rc5, out5 = py(CODE_ABC)
check("adapters/base.py 的 MemoryAdapter 抽象方法 = ingest + retrieve",
      rc5 == 0 and "'ingest', 'retrieve'" in out5.replace('"', "'"),
      f"rc={rc5} {out5[-200:]}")


# ---------- 6. 参考臂端到端：写入 → 检索（零 LLM、零网络） ----------
CODE_BM25 = (
    "import sys, json; sys.path.insert(0, 'chain/harness'); "
    "import common as C; from adapters.naive_bm25 import BM25Adapter; "
    "chs = C.load_corpus(); "
    "ad = BM25Adapter(); st = ad.ingest(chs); "
    "hits = ad.retrieve(chs[0]['text'][:30], k=5); "
    "cids = {c['cid'] for c in chs}; "
    "print(json.dumps({'n_chapters': len(chs), 'chunks': st['chunks'], "
    "'n_hits': len(hits), 'cid_ok': all(h['cid'] in cids for h in hits)}))")
rc6, out6 = py(CODE_BM25)
try:
    d6 = json.loads(out6.strip().splitlines()[-1]) if rc6 == 0 else {}
except Exception:
    d6 = {}
check("bm25 参考臂：语料可载入、写入有块、检索非空且 cid 对得上",
      rc6 == 0 and d6.get("n_chapters", 0) >= 200 and d6.get("chunks", 0) > 0
      and d6.get("n_hits", 0) > 0 and d6.get("cid_ok") is True,
      f"rc={rc6} {d6} {out6[-200:]}")


# ---------- 7. 五家桩：import 成功、实例化报可读的「未随库发布」 ----------
CODE_STUB = (
    "import sys, json, importlib; sys.path.insert(0, 'chain/harness'); "
    "from adapters._stub import AdapterNotPublished; res = {}; "
    "pairs = [('lingshu_adapter','LingshuAdapter'),('openviking_adapter','OpenVikingAdapter'),"
    "('mem0_adapter','Mem0Adapter'),('memos_adapter','MemOSAdapter'),('hindsight_adapter','HindsightAdapter')]; "
    "\nfor mod, cls in pairs:\n"
    "    m = importlib.import_module('adapters.' + mod)\n"
    "    try:\n        getattr(m, cls)()\n        res[mod] = 'no-raise'\n"
    "    except AdapterNotPublished as e:\n"
    "        res[mod] = 'ok' if '未随本库发布' in str(e) else 'msg'\n"
    "    except Exception as e:\n        res[mod] = 'other:' + type(e).__name__\n"
    "print(json.dumps(res, ensure_ascii=False))")
rc7, out7 = py(CODE_STUB)
try:
    d7 = json.loads(out7.strip().splitlines()[-1]) if rc7 == 0 else {}
except Exception:
    d7 = {}
check("五家桩：import 成功且实例化抛 AdapterNotPublished（写明未随库发布）",
      rc7 == 0 and len(d7) == 5 and set(d7.values()) == {"ok"},
      f"rc={rc7} {d7} {out7[-200:]}")


# ---------- 8. 新增发布面不含内部标识 ----------
INNER = [r"mdcg", r"dsh-memory", r"MDCG_ROOT", r"AEIS", r"令牌"]
inner_hits = []
PUB_PY = sorted(HARNESS.rglob("*.py"))
for p in PUB_PY:
    t = p.read_text(encoding="utf-8")
    for pat in INNER:
        if re.search(pat, t, re.I):
            inner_hits.append(f"{p.relative_to(ROOT).as_posix()}:{pat}")
check("新增发布面（chain/harness/**）不含内部标识 mdcg/dsh-memory/MDCG_ROOT/AEIS/令牌",
      len(PUB_PY) >= 10 and not inner_hits,
      f"扫到 {len(PUB_PY)} 个 .py（<10 说明发布面根本不在）" + str(inner_hits))


# ---------- 9. 新增发布面不含绝对路径与密钥值 ----------
LEAK = [r"(?<![A-Za-z])[A-Za-z]:[\\/]", r"Users[\\/]test", r"sk-[A-Za-z0-9]{8,}"]
leak_hits = []
TEXT_SUFFIX = {".py", ".txt", ".md", ".cfg", ".toml", ".json"}
PUB_TEXT = []
for p in sorted(HARNESS.rglob("*")):
    if (not p.is_file() or p.suffix not in TEXT_SUFFIX
            or "__pycache__" in p.parts):
        continue
    PUB_TEXT.append(p)
    t = p.read_text(encoding="utf-8", errors="replace")
    for pat in LEAK:
        if re.search(pat, t):
            leak_hits.append(f"{p.relative_to(ROOT).as_posix()}:{pat}")
check("新增发布面不含本机绝对路径与密钥字面量",
      len(PUB_TEXT) >= 10 and not leak_hits,
      f"扫到 {len(PUB_TEXT)} 个文本文件（<10 说明发布面根本不在）" + str(leak_hits))
# 说明：`DEEPSEEK_API_KEY` 是**环境变量名**、不是密钥值，且是第三方自备 key 的唯一接口，
# 故不在禁止清单内——这条判断显式写在这里，避免「扫描器悄悄放水」。


# ---------- 10. 源码级反回退：多候选 harness 解析 ----------
PR = ROOT / "chain" / "tools" / "probe_runner.py"
pt = PR.read_text(encoding="utf-8") if PR.is_file() else ""
check("probe_runner 有多候选 harness 解析 + HMB_HARNESS 开关（不再硬编码单一外部路径）",
      "HARNESS_CANDIDATES" in pt and "HMB_HARNESS" in pt
      and "HARNESS_REPO" in pt and "HARNESS_LOCAL" in pt)


# ---------- 11. 文档口径 ----------
cr = (ROOT / "chain" / "README.md").read_text(encoding="utf-8")
rr = (ROOT / "README.md").read_text(encoding="utf-8")
check("chain/README 有「自备适配器」一节（接口约定）", "自备适配器" in cr)
check("chain/README 不再声称「该 harness 不在本库内」",
      "该 harness **不在本库内**" not in cr)
check("根 README 写明 bm25 臂开箱可跑", "bm25" in rr and "开箱可跑" in rr)


ok = sum(1 for _, o in _results if o)
print(f"\n守卫 {ok}/{len(_results)} 通过")
sys.exit(0 if ok == len(_results) else 1)
