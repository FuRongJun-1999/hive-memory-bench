#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""卡片题面泄漏守卫（issue #45-3）。

覆盖：
  #45-3a `cards/o042.yaml` 与 o050（issue #22）同构：题干里就写着「巨子塔、风神像、指南、
         风之种」，而 p2／p3／p4 的 any_of 各收了一个**题干自带的光杆名词**（风神像／巨子／
         指南／风之种，「巨子」还是「巨子塔」的子串），p5 又收了光杆「规则／纪念」⇒
         只复述题干即得 0.6；再加一句不含任何题目事实的「它们遵循同一套规则。」命中 p5
         ⇒ 0.8 ≥ PASS_SCORE 0.7，**规则层直接 pass，不进语义层**。
         修后：E0 只复述题干 fail 0.0；E1 题干＋套话 fail 0.0。
  #45-3b `check_all.py` 新增机检 `check_question_leak`：① 题面原文当答卷的覆盖率 ≥ 该卡
         通过阈值 ⇒ 硬错误；② 采分点 any_of 的**字面项是题面子串** ⇒ 硬错误。
         按 ② 清理了 26 张卡共 32 处（o042／o039／q008… 的字面光杆名词）。

用法：python -X utf8 tests/test_card_question_leak_guard.py
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

REPO = Path(__file__).resolve().parent.parent
CHK = REPO / "check_all.py"
CARD = REPO / "cards" / "o042.yaml"
_PASS, _FAIL = [], []


def ok(cond, msg, extra=""):
    (_PASS if cond else _FAIL).append(msg)
    print(("[PASS] " if cond else "[FAIL] ") + msg +
          (("   | " + str(extra)) if (extra and not cond) else ""))


def run_check(root: Path):
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    p = subprocess.run([sys.executable, "-X", "utf8", str(root / "check_all.py")], cwd=str(root),
                       env=env, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=900)
    return p.returncode, p.stdout + p.stderr


def norm(s):
    return re.sub(r"[\s\W_]+", "", s or "", flags=re.UNICODE)


def q_coverage(card, J):
    """把**题面原文当答卷**，跑本卡自己的采分点。"""
    q = card.get("question") or ""
    return J.score_points(card, {"answer": q}, "rubric")["score"]


def main() -> int:
    sys.path.insert(0, str(REPO))
    import judge as J
    import yaml

    code, out = run_check(REPO)
    ok(code == 0 and "0 错误" in out,
       "#45-3b 干净仓库：check_all.py 0 错误、exit 0", f"exit={code} {out[-160:]}")

    # —— 行为级：o042 的题面原文不得成为通过路径 ——
    card = yaml.safe_load(CARD.read_text(encoding="utf-8"))
    cov = q_coverage(card, J)
    ok(cov == 0.0, "#45-3a o042 只复述题干的规则层覆盖率 = 0.0（旧实现 0.6）", f"cov={cov}")
    pts = [p for p in (card.get("rubric") or []) if p.get("required")]
    lit = [(p.get("id"), v) for p in pts for v in (p.get("any_of") or [])
           if not str(v).startswith("re:") and norm(str(v)) and norm(str(v)) in norm(card["question"])]
    ok(not lit, "#45-3a o042 的 any_of 里不再有题干自带的光杆名词", lit)
    ok(any(str(v).startswith("re:") for p in pts for v in (p.get("any_of") or [])),
       "#45-3a o042 保留了「名词＋功能」共现正则")

    # —— 全库：题干原文不得过门，且不得有题面子串的字面项 ——
    bad_cov, bad_lit = [], []
    for cp in sorted((REPO / "cards").glob("*.yaml")):
        c = yaml.safe_load(cp.read_text(encoding="utf-8"))
        q = c.get("question") or ""
        if not q:
            continue
        cv = q_coverage(c, J)
        if cv >= J.PASS_SCORE:
            bad_cov.append((cp.stem, cv))
        for p in (c.get("rubric") or c.get("answer_points") or []):
            for v in (p.get("any_of") or []):
                if not str(v).startswith("re:") and norm(str(v)) and norm(str(v)) in norm(q):
                    bad_lit.append((cp.stem, p.get("id"), v))
    ok(not bad_cov, "#45-3a 92 张卡：题面原文覆盖率无一 ≥ PASS_SCORE(0.7)", bad_cov)
    ok(not bad_lit, "#45-3b 92 张卡：any_of 里无题面子串的字面项", bad_lit[:6])

    # —— 定点变异：把 o042 还原成修复前的形态，两条硬错误都必须报出来 ——
    d = Path(tempfile.mkdtemp()) / "r"
    shutil.copytree(REPO, d, ignore=shutil.ignore_patterns(".git", "sut", "real", "real_*",
                                                           "semantic", "__pycache__", "out"))
    cp = d / "cards" / "o042.yaml"
    src = cp.read_text(encoding="utf-8")
    src = src.replace("  any_of:\n  - 're: (风神).{0,12}(就是|即).{0,10}(巨子|陈默)'",
                      "  any_of:\n  - 风神像\n  - 巨子\n  - 're: (风神).{0,12}(就是|即).{0,10}(巨子|陈默)'")
    src = src.replace("  any_of:\n  - 维护公民认同", "  any_of:\n  - 指南\n  - 维护公民认同")
    src = src.replace("  any_of:\n  - 协作", "  any_of:\n  - 风之种\n  - 协作")
    src = src.replace("  any_of:\n  - 供奉\n", "  any_of:\n  - 规则\n  - 纪念\n  - 供奉\n")
    assert src != cp.read_text(encoding="utf-8")
    cp.write_text(src, encoding="utf-8")
    code2, out2 = run_check(d)
    ok(code2 != 0 and "o042" in out2,
       "#45-3b 还原成修复前形态后 check_all.py 报 o042、非零退出",
       f"exit={code2}｜{[l for l in out2.splitlines() if 'o042' in l][:2]}")
    ok("字面项是题面子串" in out2, "#45-3b 硬错误 ②（字面项⊂题面）报出来了")
    c2 = yaml.safe_load(cp.read_text(encoding="utf-8"))
    cov2 = q_coverage(c2, J)
    ok(abs(cov2 - 0.6) < 1e-9, "#45-3a 变异卡复现旧读数 E0：只复述题干 0.6", f"cov={cov2}")
    e1 = c2["question"] + "它们遵循同一套规则。"
    cov_e1 = J.score_points(c2, {"answer": e1}, "rubric")["score"]
    ok(abs(cov_e1 - 0.8) < 1e-9 and cov_e1 >= J.PASS_SCORE,
       "#45-3a 变异卡复现旧读数 E1：题干＋套话 0.8 ≥ PASS_SCORE（旧实现规则层 pass）",
       f"cov={cov_e1}")

    # —— 硬错误 ①（题面原文即过门）的定点用例：题面自带 ≥70% 的采分点 ——
    import importlib.util
    spec = importlib.util.spec_from_file_location("_chk", str(REPO / "check_all.py"))
    CHK = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(CHK)
    synth_card = {
        "question": "长眠之地、维护公民认同、协作、供奉——这四样东西怎么连成一条线？",
        "rubric": [
            {"id": "p1", "required": True, "any_of": ["长眠之地"]},
            {"id": "p2", "required": True, "any_of": ["维护公民认同"]},
            {"id": "p3", "required": True, "any_of": ["协作"]},
            {"id": "p4", "required": True, "any_of": ["供奉"]},
            {"id": "p5", "required": True, "any_of": ["同一个人"]},
        ],
        "grading": {"coverage_required": 0.7},
    }
    e1, w1 = [], []
    CHK.check_question_leak(synth_card, "oSYN", "rubric", synth_card["rubric"], e1, w1)
    ok(any("题面即通过路径" in x for x in e1),
       "#45-3b 硬错误 ① 题面原文覆盖率 0.8 ≥ 0.7 时报「题面即通过路径」", e1)
    ok(any("字面项是题面子串" in x for x in e1),
       "#45-3b 硬错误 ② 字面项⊂题面时报出来", e1)
    e2, w2 = [], []
    CHK.check_question_leak(card, "o042", "rubric", card["rubric"], e2, w2)
    ok(not e2 and not w2, "#45-3b 修好的 o042 过检（0 错误 0 提醒）", e2 + w2)

    total = len(_PASS) + len(_FAIL)
    print("")
    print("===== SUMMARY %d/%d 通过 =====" % (len(_PASS), total))
    if _FAIL:
        print("失败项：")
        for m in _FAIL:
            print("  - " + m)
        return 1
    print("VERDICT=PASS（卡片题面泄漏守卫全绿）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
