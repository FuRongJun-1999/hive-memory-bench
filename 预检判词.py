#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""终裁前预检：把 `semantic/out/real/` 下的判词扫一遍，报出会被 finalize **静默跳过**的件。

为什么需要：`semantic.py finalize` 对判词的容错是"不合规就跳过"——`verdict` 不在枚举里、
JSON 解析不出、`points` 为空，都会让它**当作没判**继续跑。134 份里少判几份，
计分板上看不出来（那几题会停在 review），但会污染"判官召回率"的统计。
本脚本把这类问题**提前**列出来，好补判。

检查项（逐件）：
  1. JSON 能否解析（容忍 ``` 代码块包裹）
  2. `qid` / `case` 是否与文件名一致
  3. `points` 非空、id 集合与请求文件的要点清单一致（多、少、错名都报）
  4. 非 miss 的 `span` 是否能在答卷里定位（miss 必须空串）
  5. 汇总 verdict 分布（用来发现"整批判 miss"这类异常）

用法：python 预检判词.py <工作台根目录> [--quiet]
"""
import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("root", nargs="?", default=".")
ap.add_argument("--quiet", action="store_true", help="只报问题，不列逐件摘要")
a = ap.parse_args()

ROOT = Path(a.root).resolve()
sys.path.insert(0, str(ROOT))
import judge as J  # noqa: E402

OUT = ROOT / "semantic" / "out" / "real"
REQ = ROOT / "semantic" / "req" / "real"
SUT = ROOT / "sut" / "out"


def parse_json(f):
    txt = f.read_text(encoding="utf-8")
    m = re.search(r"\{.*\}", txt, re.S)
    return (json.loads(m.group(0)) if m else None), (m is not None and "```" in txt)


def req_ids(name):
    """从请求文件里抽要点 id。

    ★ 只在「要点清单：」到下一个 `## ` 之间抽——首版对全文扫 `^- (\\w+)[（(]`，
      把六条纪律里开头的 `- strict（严格命中）…` 也当成了要点 id。
    """
    f = REQ / f"{name}.md"
    if not f.exists():
        return None
    txt = f.read_text(encoding="utf-8")
    i = txt.find("要点清单：")
    if i < 0:
        return None
    seg = txt[i:]
    j = seg.find("\n## ")
    if j > 0:
        seg = seg[:j]
    return re.findall(r"^- ([\w]+)[（(]", seg, re.M)


def answer_of(qid):
    for cand in (qid, qid[:-1] if qid.endswith("i") else None):
        if not cand:
            continue
        f = SUT / f"{cand}.json"
        if f.exists():
            o = json.loads(f.read_text(encoding="utf-8"))
            return o.get("answer") or o.get("conclusion") or ""
    return ""


files = sorted(OUT.glob("*.json")) if OUT.exists() else []
if not files:
    raise SystemExit(f"{OUT} 下没有判词")

verd = Counter()
bad_names, bad_ids, bad_span, unparsed, fenced = [], [], [], [], []
npoints = 0
for f in files:
    name = f.stem                      # 形如 `q031__q031`
    qid = name.split("__")[0]
    obj, fenced_flag = parse_json(f)
    if fenced_flag:
        fenced.append(name)
    if not isinstance(obj, dict):
        unparsed.append(name)
        continue
    if str(obj.get("qid")) != qid or str(obj.get("case")) != obj.get("qid"):
        bad_names.append(f"{name}（qid={obj.get('qid')} case={obj.get('case')}）")
    pts = obj.get("points")
    if not isinstance(pts, list) or not pts:
        unparsed.append(f"{name}（points 空）")
        continue
    want = req_ids(name)
    got = [str(p.get("id")) for p in pts]
    if want and got != want:
        bad_ids.append(f"{name}：请求 {want} ≠ 判词 {got}")
    ans = J.norm(answer_of(qid))
    for p in pts:
        npoints += 1
        v = str(p.get("verdict") or "").strip().lower()
        verd[v or "(空)"] += 1
        span = (p.get("span") or "").strip()
        if v == "miss":
            if span:
                bad_span.append(f"{name}/{p.get('id')}：miss 却给了 span")
            continue
        if v not in ("strict", "paraphrase"):
            continue
        if not span:
            bad_span.append(f"{name}/{p.get('id')}：{v} 却无 span")
        elif J.norm(span) not in ans:
            bad_span.append(f"{name}/{p.get('id')}：span 定位不到「{span[:24]}」")

print(f"=== 预检：{ROOT.name}（{len(files)} 份判词，{npoints} 个点）===")
print(f"  verdict 分布：{dict(verd)}")
if unparsed:
    print(f"\n★ 解析失败/无要点（{len(unparsed)}）：")
    for x in unparsed:
        print("   ", x)
if bad_names:
    print(f"\n★ qid/case 与文件名不符（{len(bad_names)}）：")
    for x in bad_names:
        print("   ", x)
if bad_ids:
    print(f"\n★ 要点 id 与请求文件不一致（{len(bad_ids)}）：")
    for x in bad_ids:
        print("   ", x)
if bad_span:
    print(f"\n★ span 问题（{len(bad_span)}）：")
    for x in bad_span:
        print("   ", x)
if fenced:
    print(f"\n（提示：{len(fenced)} 份带 ``` 包裹，finalize 能容错，但建议清掉）")
if not (unparsed or bad_names or bad_ids or bad_span):
    print("\n全部通过：无解析失败、id 对齐、span 全部可定位。")
print(f"\n未判的请求（{len(list(REQ.glob('*.md'))) - len(files)} 份待判/待写）：补判后重跑本预检")
