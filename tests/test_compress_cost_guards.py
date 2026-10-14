#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""压缩代价检查器守卫（issue #33 第六／七项 / P1-24、P1-25）。

覆盖外部检查器必须实现文档的度量，且不得在缺料时静默给出虚高读数：
  #33-24a strict／loose 两套口径分开实现，默认 strict（保留标点逐字包含）；旧实现只有
          「只留汉字＋≥n 连续公共块」一套，且 `n=min(n,len(a),len(b))` 截断使 `--n 999`
          与 `--n 8` 同效（与文档「要更严可以把 --n 调大」相反）。
  #33-24b 单列「题面之外那一侧」（远侧）——文档 §四 的读数，旧实现汇总里没有。
  #33-24c 依据轴按**单文件单自然段**定位；旧实现把所有文件拼成一个串，可跨文件跨段命中
          （实测跨文件／错版本／纯拉丁 3 条全记 100%）。
  #33-24d 过短引文（<6 汉字）进分母并单列；旧实现静默剔出分母（真引文＋两条编造记 100%）。
  #33-25a 带 qid 却缺同名检索文件时记「缺检索文件」、该题按「两侧全无」计并非零退出；
          旧实现静默退化成「全部片段并集」。
  #33-25b 检索键存在但列表为空 ⇒ 空片段；旧实现回退 `collect_texts(obj)` 把 `query.text`
          （题面）当检索片段。

用法：python -X utf8 tests/test_compress_cost_guards.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "systems" / "压缩代价.py"
PY = sys.executable
_PASS, _FAIL = [], []


def ok(cond, msg, extra=""):
    (_PASS if cond else _FAIL).append(msg)
    print(("[PASS] " if cond else "[FAIL] ") + msg +
          (("   | " + str(extra)) if (extra and not cond) else ""))


def run(args, cwd=REPO):
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    p = subprocess.run([PY, "-X", "utf8", str(SRC)] + args, cwd=str(cwd), env=env,
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=600)
    return p.returncode, p.stdout + p.stderr


def fixture(root: Path) -> dict:
    mat = root / "mat"
    mat.mkdir(parents=True)
    (mat / "a.txt").write_text("第一段：猎户项目的有效期是 600 秒。\n\n"
                               "第二段：材料写：「X不成立」（v2）。", encoding="utf-8")
    (mat / "b.txt").write_text("第三段：风神像位于摘星崖。", encoding="utf-8")
    ret = root / "ret"
    ret.mkdir()
    (ret / "q1.json").write_text(json.dumps(
        {"hits": [{"text": "第二段：材料写：「X不成立」（v2）。"}]}, ensure_ascii=False),
        encoding="utf-8")
    (ret / "q2.json").write_text(json.dumps({"query": {"text": "题面不该被当检索片段"},
                                             "hits": []}, ensure_ascii=False), encoding="utf-8")
    pairs = root / "pairs.json"
    pairs.write_text(json.dumps([
        {"qid": "q1", "a": "材料写：「X不成立」（v9）", "b": "第三段：风神像位于摘星崖。"},
        {"qid": "q2", "a": "猎户项目的有效期是 600 秒。", "b": "风神像位于摘星崖。"},
        {"qid": "q3", "a": "猎户项目的有效期是 600 秒。", "b": "风神像位于摘星崖。"},
    ], ensure_ascii=False), encoding="utf-8")
    ans = root / "ans"
    ans.mkdir()
    (ans / "ans.json").write_text(json.dumps({"quote": [
        "第三段：风神像位于摘星崖。", "猎户项目的有效期是 600 秒。第二段：材料写",
        "甲乙丙", "the quick brown fox"]}, ensure_ascii=False), encoding="utf-8")
    return dict(mat=mat, ret=ret, pairs=pairs, ans=ans)


def main() -> int:
    text = SRC.read_text(encoding="utf-8")

    # —— 源码级：旧口径的痕迹必须消失、新口径的机制必须存在 ——
    code_part = text.split('"""', 2)[2]          # 跳过模块说明，只查代码
    ok("n = min(n, len(a), len(b))" not in code_part,
       "#33-24a 去掉 n=min(...) 截断（旧实现 --n 调大不更严）")
    ok("'strict'" in text and "'loose'" in text and "norm_strict" in text,
       "#33-24a strict／loose 两套口径分开实现")
    ok("①b 远侧" in text and "far_ok" in text,
       "#33-24b 单列「题面之外那一侧」（远侧）")
    ok("split_paras" in text and "单文件单自然段" in text,
       "#33-24c 依据轴按单文件单自然段定位")
    ok("MIN_CJK" in text and "过短引文" in text,
       "#33-24d 过短引文进分母并单列")
    ok("缺检索文件" in text and "return 3" in text,
       "#33-25a 缺检索文件非零退出")
    ok("k != 'query'" in text and "检索键" in text,
       "#33-25b hits 为空不回退收题面")

    # —— 自检必须全绿 ——
    code, out = run(["--selftest"])
    ok(code == 0 and "全部通过" in out,
       "#33-24 内置 --selftest 全部通过（exit 0）", f"exit={code} {out[-200:]}")

    root = Path(tempfile.mkdtemp())
    f = fixture(root)
    base = ["--material", str(f["mat"]), "--retrieval", str(f["ret"]),
            "--pairs", str(f["pairs"]), "--answers", str(f["ans"])]

    # —— 缺检索文件：q3 ⇒ 非零退出 ＋ 该题按两侧全无 ——
    code, out = run(base)
    ok(code == 3 and "缺检索文件 1 题" in out and "q3" in out,
       "#33-25a 缺 q3 检索文件 ⇒ exit 3 且报出题号", f"exit={code} {out[-160:]}")
    ok("全部片段并集" not in out.split("q3")[-1][:40] if "q3" in out else False,
       "#33-25a 缺料题不再标「全部片段并集」")
    code2, out2 = run(base + ["--allow-missing"])
    ok(code2 == 0, "#33-25a --allow-missing ⇒ exit 0", f"exit={code2}")

    # —— ①b 远侧 ——
    far_line = [l for l in out.splitlines() if l.startswith("①b 远侧")]
    ok(bool(far_line) and far_line[0].rstrip().endswith("/3"),
       "#33-24b 汇总含 ①b 远侧 x/3", far_line)

    # —— strict vs loose：q1 的 v9 引文在 strict 下不命中、loose 下命中 ——
    line_strict = [l for l in out.splitlines() if l.startswith("q1 ")]
    code3, out3 = run(base + ["--allow-missing", "--mode", "loose"])
    line_loose = [l for l in out3.splitlines() if l.startswith("q1 ")]
    ok(bool(line_strict) and line_strict[0].split()[1] == "✗",
       "#33-24a strict 口径：v9 引文对 v2 材料不命中", line_strict)
    ok(bool(line_loose) and line_loose[0].split()[1] == "✓",
       "#33-24a loose 口径：同一对命中（两套口径真的分开）", line_loose)

    # —— 依据轴：4 条引文（1 真 ＋ 1 跨段 ＋ 2 编造），strict 下只 1 条定位、过短 2 条 ——
    ax = out.split("② 依据轴")[1][:120] if "② 依据轴" in out else ""
    ok("答卷引文 4 条" in ax and "定位 1 条" in ax,
       "#33-24c/d strict 依据轴：4 条引文、1 条定位", ax.strip()[:90])
    ok("过短引文 2 条" in ax,
       "#33-24d 过短引文进分母并单列 2 条", ax.strip()[:90])

    # —— ⑦ hits:[] 不得把题面当检索片段 ——
    ok("题面不该被当检索片段" not in out,
       "#33-25b hits:[] 时题面不被当检索片段")
    ok("为空" in out and "q2" in out,
       "#33-25b 空 hits 组被标注为「为空 ⇒ 两侧全无」")

    # —— 旧算法对照：n=min 截断 ⇒ --n 999 与 --n 8 同效（证明本项非恒真）——
    import re as _re
    CJK = _re.compile(r"[^\u4e00-\u9fff]")

    def old_common_block(a, b, n):
        a, b = CJK.sub("", a or ""), CJK.sub("", b or "")
        if not a or not b:
            return False
        if a in b or b in a:
            return True
        n = min(n, len(a), len(b))
        return any(a[i:i + n] in b for i in range(len(a) - n + 1))

    v9, v2 = "材料写：「X不成立」（v9）", "第二段：材料写：「X不成立」（v2）。"
    ok(old_common_block(v9, v2, 8) == old_common_block(v9, v2, 999) is True,
       "#33-24a 旧算法下 --n 999 与 --n 8 同效（对照证据，非恒真）")

    total = len(_PASS) + len(_FAIL)
    print("")
    print("===== SUMMARY %d/%d 通过 =====" % (len(_PASS), total))
    if _FAIL:
        print("失败项：")
        for m in _FAIL:
            print("  - " + m)
        return 1
    print("VERDICT=PASS（压缩代价检查器守卫全绿）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
