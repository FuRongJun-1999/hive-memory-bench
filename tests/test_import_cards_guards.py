#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""主轨守卫：导入回收作答.py（#19）与卡片采分词（#22）。

覆盖：
  #19 ① confidence 缺省须真的生效（旧实现 rec = {k: a.get(k) …} 已把键建出来，
        setdefault 永不触发 ⇒ 缺 confidence 的答卷落盘成 null，诚实轴判 fail）
  #19 ② condition（卡片 degradation 登记过的退化条件）须随卷落盘，不得静默丢弃
  #22  任何卡片都不能「只复述题干＋1 条认可引文」就规则层 pass（旧实现 o050 白给 0.8）

用法：python -X utf8 tests/test_import_cards_guards.py
"""
from __future__ import annotations

import glob
import json
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
_PASS, _FAIL = [], []


def ok(cond, msg, extra=""):
    (_PASS if cond else _FAIL).append(msg)
    print(("[PASS] " if cond else "[FAIL] ") + msg +
          (("   | " + str(extra)) if (extra and not cond) else ""))


def sh(*args):
    return subprocess.run([sys.executable, "-X", "utf8", *args], cwd=ROOT,
                          capture_output=True, text=True, encoding="utf-8", errors="replace")


def main():
    sys.path.insert(0, str(ROOT))
    sys.dont_write_bytecode = True
    out_dir = ROOT / "sut" / "out"
    made = []

    # ---------- #19 ----------
    src = (ROOT / "导入回收作答.py").read_text(encoding="utf-8")
    live = [l.strip() for l in src.splitlines()
            if l.strip().startswith("rec.setdefault(")]
    ok(not live,
       "#19 ① 导入脚本里那行永不生效的 rec.setdefault(\"confidence\") 已移除",
       live)
    ok("condition" in src.split("KEEP = ")[1].split(")")[0],
       "#19 ② KEEP 须含 condition（否则退化条件答卷经导入后被静默改成完整条件）",
       src.split("KEEP = ")[1].split("\n")[0])

    card = yaml.safe_load((ROOT / "cards/q001.yaml").read_text(encoding="utf-8"))
    se = card["supporting_evidence"][0]
    kw = "；".join(str(p["any_of"][0]) for p in card["answer_points"] if p.get("required"))
    deg = card["degradation"][0]
    base = {"qid": "q001", "conclusion": kw, "answer": kw,
            "evidence": [{"cid": se["cid"], "quote": se["quote"]}]}
    out_dir.mkdir(parents=True, exist_ok=True)
    exp = ROOT / "_guard_export.json"
    exp.write_text(json.dumps({"answers": [dict(base)]}, ensure_ascii=False),
                   encoding="utf-8")
    p = sh("导入回收作答.py", str(exp))
    rec_f = out_dir / "q001.json"
    made.append(rec_f)
    rec = json.loads(rec_f.read_text(encoding="utf-8")) if rec_f.exists() else {}
    ok(rec.get("confidence") == "probable",
       "#19 ① 缺 confidence 的答卷经导入后落盘为 probable（与 docstring 意图一致）",
       f"confidence={rec.get('confidence')!r}, exit={p.returncode}")
    ok("probable" in p.stdout and "缺 confidence" in p.stdout,
       "#19 ① 体检须把「补了缺省 confidence」的题数报出来（不是静默补）",
       [l for l in p.stdout.splitlines() if "confidence" in l][:2])

    exp.write_text(json.dumps({"answers": [dict(base, confidence="unknown",
                                                condition=deg["given"])]},
                              ensure_ascii=False), encoding="utf-8")
    p2 = sh("导入回收作答.py", str(exp))
    rec2 = json.loads(rec_f.read_text(encoding="utf-8"))
    ok(rec2.get("condition") == deg["given"],
       "#19 ② 带 condition 的答卷经导入后条件须保留（旧实现静默丢弃、按完整条件判）",
       f"condition={rec2.get('condition')!r}")
    ok("condition" in p2.stdout,
       "#19 ② 体检须报出「带 condition 的作答」题数（旧实现静默丢弃）",
       [l for l in p2.stdout.splitlines() if "condition" in l][:2])
    exp.unlink(missing_ok=True)

    # ---------- #22 ----------
    sys.path.insert(0, str(ROOT))
    import judge as J                                            # noqa: E402
    idx = J.chapter_index(J.load_units())
    passed = []
    for f in sorted(glob.glob(str(ROOT / "cards/*.yaml"))):
        cd = yaml.safe_load(open(f, encoding="utf-8"))
        s = (cd.get("supporting_evidence") or cd.get("evidence_pool") or [{}])[0]
        resp = {"qid": cd["qid"], "answer": cd["question"], "conclusion": cd["question"],
                "evidence": ([{"cid": s.get("cid"), "quote": s.get("quote")}]
                             if s.get("quote") else []),
                "confidence": "probable"}
        res = J.judge(cd, resp, idx)
        if res["verdict"] == "pass":
            passed.append(cd["qid"])
    ok(not passed,
       "#22 任何卡片都不得「只复述题干＋1 条认可引文」就规则层 pass（旧实现 o050 pass 0.8）",
       f"pass 的卡片={passed}")

    o050 = yaml.safe_load((ROOT / "cards/o050.yaml").read_text(encoding="utf-8"))
    q = o050["question"]
    bare = [str(it) for p in o050["rubric"] for it in (p.get("any_of") or [])
            if not str(it).startswith("re:") and len(str(it)) >= 2 and str(it) in q]
    ok(not bare,
       "#22 o050 的采分词不得是题干里的光杆地名（改用地名＋功能共现正则）",
       f"光杆题干词={bare}")

    for f in made:
        f.unlink(missing_ok=True)

    total = len(_PASS) + len(_FAIL)
    print("")
    print("===== SUMMARY %d/%d 通过 =====" % (len(_PASS), total))
    if _FAIL:
        print("失败项：")
        for m in _FAIL:
            print("  - " + m)
        return 1
    print("VERDICT=PASS（导入与卡片采分词守卫全绿）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
