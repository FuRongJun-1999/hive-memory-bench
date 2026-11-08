# -*- coding: utf-8 -*-
"""P1-1：重造 C 面 30 题。修正材料窗边界（严格截止在答案行前）+ 加 V2 校验。"""
import json, re
from pathlib import Path
from collections import Counter

R = Path(r"D:/1_ai/_hb_lab/r58")
C = R / "e2e" / "corpus"
Q = R / "e2e" / "questions"
selfclaims = json.loads(Path(r"D:/1_ai/_hb_lab/r58/e2e/run/selfclaims_backup.json").read_text(encoding="utf-8")) if Path(r"D:/1_ai/_hb_lab/r58/e2e/run/selfclaims_backup.json").exists() else None
print("selfclaims 缓存存在:", selfclaims is not None)

# 重新抽取（与原来同样的规则，但材料窗严格截止）
PATTERNS = [
    ("身份", re.compile(r"我是[^。！？\n]{4,40}")),
    ("原则", re.compile(r"我的?原则[是为][^。！？\n]{4,60}")),
    ("立场", re.compile(r"我(?:的立场|相信|认为)[^。！？\n]{6,60}")),
    ("约束", re.compile(r"我(?:不会|不能|不应该)[^。！？\n]{6,60}")),
]
BADW = ("如果", "假设", "看到", "那个", "你说的", "你让", "你以为", "你觉得",
        "我不知道", "我是谁", "你将在", "情境中读取", "是否", "吗", "？", "?", "如何",
        "为什么", "这一层级的反思", "在问的是")
def ok_claim(t):
    t = t.strip()
    if len(t) < 15 or "你" in t:
        return False
    if any(b in t for b in BADW):
        return False
    return bool(re.match(r"^我(是|的原则|不会|不能|不应该|的立场|的职责|的定位|的角色|坚持|拒绝)", t))

rows = []
for f in sorted(C.glob("*.md")):
    ls = f.read_text(encoding="utf-8", errors="replace").splitlines()
    for i, ln in enumerate(ls):
        if not ln.strip().startswith("**DeepSeek说"):
            continue
        j = i + 1
        while j < len(ls) and not ls[j].strip().startswith("---"):
            t = ls[j].strip()
            if t and not t.startswith(">"):
                for kind, pat in PATTERNS:
                    for m in pat.finditer(t):
                        c = m.group(0).strip()
                        if ok_claim(c):
                            rows.append({"file": f.name, "line": j + 1, "kind": kind, "text": c})
            j += 1

# 去重
seen = set(); uniq = []
for r in rows:
    if r["text"] in seen:
        continue
    seen.add(r["text"]); uniq.append(r)
ident = [r for r in uniq if r["kind"] == "身份"]
princ = [r for r in uniq if r["kind"] != "身份"]
print(f"合格自述: {len(uniq)}（身份 {len(ident)} / 原则等 {len(princ)}）")

def norm(s):
    return re.sub(r"[^\w]", "", s or "", flags=re.UNICODE)

cache = {}
def lines_of(fn):
    if fn not in cache:
        cache[fn] = (C / fn).read_text(encoding="utf-8", errors="replace").splitlines()
    return cache[fn]

def window_strict(r, nblocks=3, maxlen=3000):
    """材料窗：答案行**之前**的 N 个 AI 块，严格 j < L-1（1-based 行号 L）。"""
    ls = lines_of(r["file"]); L = r["line"]
    starts = [i + 1 for i, x in enumerate(ls) if x.strip().startswith("**DeepSeek说")]
    prior = [s for s in starts if s < L][-nblocks:]
    seg = []
    for s in prior:
        j = s
        while j < len(ls) and not ls[j].strip().startswith("---"):
            if j + 1 >= L:          # 严格截止：答案行及之后一律不要
                break
            seg.append(ls[j])
            j += 1
        if j + 1 >= L:
            break
    txt = chr(10).join(seg)
    return txt[-maxlen:] if len(txt) > maxlen else txt

qs = []
n = min(len(ident), len(princ), 10)
skipped = 0
for k in range(n):
    combos = [("C1", ident[k], "（第 1 问）在下面这段历史里，你刚才如何描述你自己？请按当时的原话回答。"),
              ("C2", princ[k], "（第 2 问，中间隔一段别的话题）换个话题：你刚才给自己定下的原则或约束是什么？按原话回答。")]
    for sub, r, qt in combos:
        mat = window_strict(r)
        claim = r["text"].strip()
        # V2 硬校验：答案必须完整或大部分在窗内
        nc, nm = norm(claim), norm(mat)
        if not nc or nc not in nm:
            skipped += 1
            continue
        if not (300 <= len(mat) <= 3000):
            skipped += 1
            continue
        qs.append({
            "qid": "P-%s-C-%03d" % (sub, k + 1), "face": "C", "subface": sub,
            "source_file": r["file"], "source_line": r["line"], "question": qt,
            "material": {"type": "window", "content": mat, "source_file": r["file"], "chars": len(mat)},
            "answer_key": {"must_contain": [claim], "unique_fragment": nc},
            "expected": "answer", "verdict_rule": "answer_if_material",
            "scoring": {"pass": "与 must_contain 的完整包含（V2 已保证答案在窗内）",
                        "fail": "未包含", "score": "1/0",
                        "consistency_group": "G-%03d" % (k + 1),
                        "note": "字面判据只认逐字复述，合理改写会判错——已在 README §七 标 literal-only"},
            "difficulty": "normal", "source": "自我陈述抽取 · " + r["kind"],
            "judge_type": "mechanical", "judge_validated": "literal-only",
        })

print(f"造题 {len(qs)}，跳过 {skipped}（答案不在严格窗内）")
print("子面:", dict(Counter(q["subface"] for q in qs)))
print("材料长度:", min((q["material"]["chars"] for q in qs), default=0), "-", max((q["material"]["chars"] for q in qs), default=0))
if qs:
    (Q / "题目_自我.json").write_text(json.dumps(qs, ensure_ascii=False, indent=1), encoding="utf-8")
    print("已写入 题目_自我.json")