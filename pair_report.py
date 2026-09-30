#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""主轮／干预轮**配对读数**（终裁后版本）。

同一张卡的两种问法并排看，才有意义：主轮答对、干预轮答不出 ⇒ 它拿的可能是结论而不是机制；
两边都答不出 ⇒ 题本身难或答案键有问题；干预轮答得比主轮好 ⇒ 该查主轮的答案键是不是设偏了。

数据来源：`real/board.json`（由 `python score_sut.py report` 写出，含**终裁后**的逐题判定与
「由哪一层定的」）。故先跑 report，再跑本脚本。

用法：python pair_report.py
"""
import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def main():
    bp = ROOT / "real" / "board.json"
    if not bp.exists():
        raise SystemExit("缺 real/board.json —— 先跑 python score_sut.py report")
    b = json.loads(bp.read_text(encoding="utf-8"))
    verd = {d["qid"]: (d["verdict"], d["by"]) for d in b["detail"]}

    pairs = []
    for qid, (v, by) in sorted(verd.items()):
        if not qid.endswith("i"):
            continue
        base = qid[:-1]
        if base in verd:
            pairs.append((base, verd[base], (v, by)))

    print(f"=== 配对（{len(pairs)} 对，终裁后）===")
    c = collections.Counter((a[0] == "pass", d[0] == "pass") for _, a, d in pairs)
    print(f"  主 pass ＋ 干 pass ：{c[(True, True)]:>3}")
    print(f"  主 pass ＋ 干 非pass：{c[(True, False)]:>3}   ← 主轮答对、干预轮答不出")
    print(f"  主 非pass ＋ 干 pass：{c[(False, True)]:>3}   ← 反过来，最该查主轮答案键")
    print(f"  两边都非 pass      ：{c[(False, False)]:>3}")

    iv = collections.Counter(v for qid, (v, _) in verd.items() if qid.endswith("i"))
    mn = collections.Counter(v for qid, (v, _) in verd.items() if not qid.endswith("i"))
    print(f"\n  主轮终裁：{dict(mn)}")
    print(f"  干预轮终裁：{dict(iv)}")

    print("\n=== 主 pass ＋ 干 非pass（35 例以内的全部详列）===")
    for base, a, d in pairs:
        if a[0] == "pass" and d[0] != "pass":
            print(f"  {base:<7} 主 {a[0]}({a[1]}) → 干 {d[0]}({d[1]})")
    print("\n=== 主 非pass ＋ 干 pass ===")
    for base, a, d in pairs:
        if a[0] != "pass" and d[0] == "pass":
            print(f"  {base:<7} 主 {a[0]}({a[1]}) → 干 {d[0]}({d[1]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
