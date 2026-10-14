#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""证据保真分档守卫（issue #33 第一项 / P1-19）。

覆盖：
  #33-1a 定位锚不再只用「12 字种子、步长 8」——引文里每 7 汉字插一个「的」（意思不变）
         时任何 12 字窗口都不逐字命中，种子全落空 ⇒ 停在初值「最相近 None」、比值 0.00，
         无害赘字引文全记 C3「无据编造」（旧实现实测 200/200）。
  #33-1b 分档不再只看 SequenceMatcher.ratio()：句中插一个「不」（极性反转）比值 0.98
         也进 C2「近似引述」，报告口径读作「零编造」（旧实现实测 200/200）。
  #33-1c 新增 --selftest：A 逐字 ⇒ C1、B 插「不」⇒ 不得进 C2、C 换主语 ⇒ 不得进 C2、
         D 插「的」⇒ 不得进 C3（证明分档不是恒真断言）。

用法：python -X utf8 tests/test_evidence_fidelity_guards.py
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "证据保真细分.py"
_PASS, _FAIL = [], []


def ok(cond, msg, extra=""):
    (_PASS if cond else _FAIL).append(msg)
    print(("[PASS] " if cond else "[FAIL] ") + msg +
          (("   | " + str(extra)) if (extra and not cond) else ""))


def main() -> int:
    text = SRC.read_text(encoding="utf-8")
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")

    # —— 源码级：旧口径的痕迹必须消失、新口径的机制必须存在 ——
    ok("SEED, STEP = 12, 8" not in text,
       "#33-1a 定位种子不再是 12/8（引文插字时种子全落空）")
    ok("find_longest_match" in text and "SHIFT_SEARCH" in text,
       "#33-1a 种子落空时有 find_longest_match 兜底 ＋ 锚点局部搜索")
    ok("C2′" in text and "改义引述" in text,
       "#33-1b 新增「C2′ 改义引述」档，改义引文不再进 C2")

    # —— 行为级：--selftest 必须跑通且四个用例全 PASS ——
    p = subprocess.run([sys.executable, "-X", "utf8", str(SRC), "--selftest"], cwd=str(REPO),
                       env=env, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=900)
    out = p.stdout + p.stderr
    ok(p.returncode == 0 and "全部通过" in out,
       "#33-1c --selftest 全部通过（exit 0）", f"exit={p.returncode} {out[-200:]}")
    for tag, want in (("A 逐字原句", "C1"), ("B 句中插一个「不」", "C2′"),
                      ("C 句首两字换「敌方」", "C2′"), ("D 每 7 汉字插一个「的」", "C2")):
        line = [l for l in out.splitlines() if l.startswith("[自检]") and tag in l]
        good = bool(line) and "PASS" in line[0] and f"⇒ {want} 60/60" in line[0]
        ok(good, f"#33-1c 自检用例「{tag}」⇒ {want} 60/60", line and line[0])

    # —— B／D 两个用例必须**真的**在旧实现下失败：用旧算法重跑同夹具 ——
    import contextlib
    import importlib.util
    import io
    import random
    import re
    sys.path.insert(0, str(REPO))
    spec = importlib.util.spec_from_file_location("_zb", str(SRC))
    mod = importlib.util.module_from_spec(spec)
    old_argv = sys.argv
    sys.argv = ["证据保真细分.py", str(REPO / "sut")] if (REPO / "sut").exists() else ["x", str(REPO)]
    try:
        with contextlib.redirect_stdout(io.StringIO()):     # 静掉模块级主循环的输出
            spec.loader.exec_module(mod)
    except SystemExit:
        pass
    finally:
        sys.argv = old_argv
    import judge as J
    random.seed(7)
    idx = J.chapter_index(J.load_units())
    normed = {c: J.norm(ch["text"]) for c, ch in idx.items()}
    sents = []
    for cid, ch in idx.items():
        for s in re.split(r"[。！？\n]+", ch["text"]):
            n = J.norm(s)
            if 24 <= len(n) <= 60 and len(set(n)) > 12:
                sents.append((cid, s.strip()))
    random.shuffle(sents)
    sents = sents[:20]

    def old_approx(quote):
        """旧实现原样：12/8 种子、±6 窗口、只看 ratio。"""
        nq = J.norm(quote)
        if len(nq) < 12:
            return 0.0, None
        best = (0.0, None)
        for cid, t in normed.items():
            for s in range(0, max(1, len(nq) - 12 + 1), 8):
                pos = t.find(nq[s:s + 12])
                if pos < 0:
                    continue
                st = pos - s
                w = t[max(0, st - 6):min(len(t), st + len(nq) + 6)]
                r = difflib_ratio(nq, w)
                if r > best[0]:
                    best = (r, cid)
                if best[0] >= 0.95:
                    break
        return best

    import difflib

    def difflib_ratio(a, b):
        return difflib.SequenceMatcher(None, a, b).ratio()

    def ins(s, k):
        out, c = [], 0
        for ch in s:
            out.append(ch)
            if "\u4e00" <= ch <= "\u9fff":
                c += 1
                if c == k:
                    out.append("不")
        return "".join(out)

    def ins_every(s, k):
        c = 0
        for ch in s:
            yield ch
            if "\u4e00" <= ch <= "\u9fff":
                c += 1
                if c % k == 0:
                    yield "的"

    b_c2 = d_c3 = 0
    for cid, s in sents:
        rb, _ = old_approx(ins(s, len(J.norm(s)) // 2))
        rd, _ = old_approx("".join(ins_every(s, 7)))
        b_c2 += 1 if rb >= 0.75 else 0                 # 旧实现：插「不」进 C2
        d_c3 += 1 if rd < 0.75 else 0                  # 旧实现：插「的」进 C3
    ok(b_c2 >= len(sents) // 2,
       "#33-1b 旧算法下「插『不』」确实进 C2（对照证据，非恒真）", f"{b_c2}/{len(sents)}")
    ok(d_c3 >= len(sents) // 2,
       "#33-1a 旧算法下「插『的』」确实进 C3（对照证据，非恒真）", f"{d_c3}/{len(sents)}")

    total = len(_PASS) + len(_FAIL)
    print("")
    print("===== SUMMARY %d/%d 通过 =====" % (len(_PASS), total))
    if _FAIL:
        print("失败项：")
        for m in _FAIL:
            print("  - " + m)
        return 1
    print("VERDICT=PASS（证据保真分档守卫全绿）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
