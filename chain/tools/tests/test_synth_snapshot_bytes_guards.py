#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成器产物与发布快照的字节一致守卫（issue #58）。

缺陷：chain/tools/synth.py 的三处写盘走 Path.write_text(...)（文本模式、newline=None），
换行落盘时被翻译成 os.linesep ⇒ Windows 上产出 CRLF；而本仓 .gitattributes 约定
* text=auto eol=lf，发布件一律 LF。于是 README §8 宣称的「固定种子下与 synth.py 的产物
逐字节相同」在 Windows 重跑路径上不成立（实测三份各多 1621 / 88959 / 11381 字节，恰等于
各自的 CRLF 个数，CRLF→LF 归一后 sha256 才与发布件相同）。

为什么这条守卫必须**跑生成器**而不只是读源码：
  · 源码级断言只能证明「写了 newline」，证不出「产物真与发布件同字节」——中间还隔着
    json.dumps 的缩进/浮点格式，以及发布件当初是否由同一版生成器产出；
  · 更关键的是**回退敏感**：G6 变异腿把 newline 参数去掉再跑一次，要求产物立刻变成 CRLF
    且 sha256 与发布件不同。没有这条腿，把 helper 改回裸 write_text 也能「绿」。

用法：python -X utf8 chain/tools/tests/test_synth_snapshot_bytes_guards.py
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SYNTH = REPO / "chain" / "tools" / "synth.py"
PUB = {"corpus.json": REPO / "chain" / "corpus" / "corpus.json",
       "keys.json": REPO / "chain" / "keys" / "keys.json",
       "synth_log.json": REPO / "chain" / "keys" / "synth_log.json"}
OUT = REPO / "chain" / "tools" / "out"
PY = sys.executable
_PASS, _FAIL, _SKIP = [], [], []


def ok(cond, msg, extra=""):
    (_PASS if cond else _FAIL).append(msg)
    print(("[PASS] " if cond else "[FAIL] ") + msg
          + (("   | " + str(extra)) if (extra and not cond) else ""))


def skip(msg, why):
    _SKIP.append(msg)
    print("[SKIP] " + msg + "   | " + why)


def sha(b):
    return hashlib.sha256(b).hexdigest()


def run_synth(synth_path: Path, cwd: Path):
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    p = subprocess.run([PY, "-X", "utf8", str(synth_path)], cwd=str(cwd), env=env,
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=900)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


# ---------------------------------------------------------------- G1 发布件口径
def g1_published_eol():
    for name, p in PUB.items():
        b = p.read_bytes()
        ok(b.count(b"\r\n") == 0,
           "G1 发布件 %s 为 LF（.gitattributes eol=lf 的仓内事实）" % name,
           "CRLF=%d" % b.count(b"\r\n"))


# ---------------------------------------------------------------- G2/G3/G4 端到端
def g234_rerun():
    rc, out = run_synth(SYNTH, REPO)
    ok(rc == 0, "G2 生成器以 0 退出", out[-400:])
    if rc != 0:
        return
    for name, p in PUB.items():
        g = (OUT / name).read_bytes()
        pub = p.read_bytes()
        ok(g.count(b"\r\n") == 0,
           "G2 重跑产物 %s 无 CRLF（写盘固定 LF，不受平台行尾影响）" % name,
           "CRLF=%d 大小差=%d" % (g.count(b"\r\n"), len(g) - len(pub)))
        ok(sha(g) == sha(pub),
           "G3 重跑产物 %s 与发布件逐字节相同（README 的字节承诺可兑现）" % name,
           "生成 %s / 发布 %s" % (sha(g)[:16], sha(pub)[:16]))
        try:
            same_content = json.loads(g) == json.loads(pub)
        except Exception as e:
            ok(False, "G4 %s JSON 解析" % name, repr(e))
            continue
        ok(same_content, "G4 重跑产物 %s 与发布件 JSON 逻辑内容相同（内容面未漂移）" % name)


# ---------------------------------------------------------------- G5 源码面：写盘单点
def g5_source():
    s = SYNTH.read_text(encoding="utf-8")
    ok("def _write_json(name: str, obj)" in s,
       "G5 生成器有唯一的 JSON 写盘入口 _write_json")
    ok(re.search(r"open\([^)]*newline=", s) is not None,
       "G5 写盘用 open(..., newline=...) 显式钉死行尾（不依赖 write_text 的 3.10+ 参数）")
    ok("os.linesep" in s,
       "G5 源码注释写明 os.linesep 翻译这一根因（读者不必再猜）")
    for name in PUB:
        ok("_write_json('%s'" % name in s,
           "G5 %s 经 _write_json 落盘（不留裸文本写入）" % name)
    bare = re.findall(r"\(OUT / '[^']+'\)\.write_text\(", s)
    ok(not bare, "G5 生成器内不再有裸 Path.write_text 写产物", "命中 %d 处" % len(bare))


# ---------------------------------------------------------------- G6 变异腿：回退即红
def g6_mutation():
    """把 newline 参数去掉、在临时目录跑同一份生成器：产物必须变回 CRLF 且与发布件不同。

    只在 Windows 上有效——POSIX 的 os.linesep 本身就是 LF，去掉 newline 不会产生 CRLF。
    """
    if os.name != "nt":
        skip("G6 变异腿（回退即红）",
             "非 Windows：os.linesep 本身即 LF，变异后仍不会产生 CRLF")
        return
    src = SYNTH.read_text(encoding="utf-8")
    mut = src.replace(r'newline="\n"', '').replace(
        r', encoding="utf-8", )', r', encoding="utf-8")')
    ok(mut != src, "G6 变异腿：已去掉 newline 参数（回归到修复前写法）")
    if mut == src:
        return
    with tempfile.TemporaryDirectory(prefix="i058mut_") as td:
        t = Path(td)
        (t / "synth.py").write_text(mut, encoding="utf-8")
        rc, out = run_synth(t / "synth.py", t)
        ok(rc == 0, "G6 变异版生成器以 0 退出", out[-300:])
        if rc != 0:
            return
        got = {}
        for name, p in PUB.items():
            m = t / "out" / name
            if not m.exists():
                ok(False, "G6 变异版产物 %s 存在" % name)
                continue
            b = m.read_bytes()
            got[name] = b.count(b"\r\n")
            ok(b.count(b"\r\n") > 0,
               "G6 变异腿生效：去掉 newline 后 %s 变成 CRLF（缺陷可复现）" % name,
               "CRLF=%d" % b.count(b"\r\n"))
            ok(sha(b) != sha(p.read_bytes()),
               "G6 变异腿生效：去掉 newline 后 %s 与发布件不再逐字节相同" % name)
            ok(json.loads(b) == json.loads(p.read_bytes()),
               "G6 变异只改行尾、不改内容（%s 逻辑内容仍相同）" % name)
        ok(len(got) == 3 and all(v > 0 for v in got.values()),
           "G6 变异腿在三份产物上全部生效", got)


# ---------------------------------------------------------------- G7 确定性仍在
def g7_determinism():
    first = {n: sha((OUT / n).read_bytes()) for n in PUB if (OUT / n).exists()}
    rc, out = run_synth(SYNTH, REPO)
    ok(rc == 0, "G7 第二次生成器以 0 退出", out[-300:])
    if rc != 0:
        return
    second = {n: sha((OUT / n).read_bytes()) for n in PUB}
    ok(first == second, "G7 连跑两次产物逐字节相同（固定种子可复现仍成立）", first)


def main():
    print("仓根:", REPO)
    g1_published_eol()
    g234_rerun()
    g5_source()
    g6_mutation()
    g7_determinism()
    total = len(_PASS) + len(_FAIL)
    print("")
    print("===== SUMMARY %d/%d 通过%s =====" % (
        len(_PASS), total, ("（跳过 %d）" % len(_SKIP)) if _SKIP else ""))
    if _FAIL:
        print("失败项：")
        for m in _FAIL:
            print("  - " + m)
        return 1
    print("VERDICT=PASS（生成器产物与发布快照逐字节一致，且守卫对回退敏感）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
