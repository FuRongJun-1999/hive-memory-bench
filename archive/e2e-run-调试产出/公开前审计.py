# -*- coding: utf-8 -*-
"""公开前的来源审计：每面的材料来自哪里，能否公开。"""
import json
from pathlib import Path
from collections import Counter, defaultdict
R = Path(r"D:/1_ai/_hb_lab/r58")
Q = R / "e2e" / "questions"

print("=== 各面材料来源 ===")
for p in sorted(Q.glob("题目_*.json")):
    if "残缺诊断" in p.name:
        continue
    d = json.loads(p.read_text(encoding="utf-8"))
    if not d:
        continue
    face = d[0].get("face")
    srcs = Counter()
    for q in d:
        m = q.get("material") or {}
        sf = m.get("source_file")
        if sf:
            srcs[sf] += 1
        elif q.get("source"):
            srcs["(source字段)"] += 1
        else:
            srcs["(无)"] += 1
    print("  面 %-4s 题 %3d | 来源 %d 种" % (face, len(d), len(srcs)))
    for s, n in srcs.most_common(3):
        print("       %s x%d" % (s, n))

print()
print("=== e2e 目录结构 ===")
for sub in sorted(R.joinpath("e2e").iterdir()):
    if sub.is_dir():
        n = len(list(sub.glob("*")))
        print("  %-12s %3d 个文件" % (sub.name, n))

print()
print("=== corpus 是什么 ===")
corp = R / "e2e" / "corpus"
if corp.exists():
    fs = sorted(corp.glob("*.md"))
    print("  %d 个文件" % len(fs))
    for f in fs[:5]:
        print("   %-40s %8d B" % (f.name, f.stat().st_size))

print()
print("=== 题卡里是否含本地绝对路径 ===")
import re
pat = re.compile(r"[A-Za-z]:[/\\]")
bad = defaultdict(int)
for p in Q.glob("题目_*.json"):
    if "残缺诊断" in p.name:
        continue
    txt = p.read_text(encoding="utf-8")
    hits = pat.findall(txt)
    if hits:
        bad[p.name] = len(hits)
for k, v in bad.items():
    print("  %-28s %d 处本地路径" % (k, v))
if not bad:
    print("  无")