# -*- coding: utf-8 -*-
"""P1-1 重做：C 面按「材料内检索」设计——窗含答案 + 混入干扰句。"""
import json, re
from pathlib import Path
from collections import Counter

R = Path(r"D:/1_ai/_hb_lab/r58")
C = R / "e2e" / "corpus"
Q = R / "e2e" / "questions"

PATTERNS = [
    ("身份", re.compile(r"我是[^。！？\n]{4,40}")),
    ("原则", re.compile(r"我的?原则[是为][^。！？\n]{4,60}")),
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
    return bool(re.match(r"^我(是|的原则|不会|不能|不应该|的立场|坚持|拒绝)", t))

# 收集所有自述（含干扰池）
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
seen = set(); uniq = []
for r in rows:
    if r["text"] in seen:
        continue
    seen.add(r["text"]); uniq.append(r)
print(f"候选自述: {len(uniq)}")

def norm(s):
    return re.sub(r"[^\w]", "", s or "", flags=re.UNICODE)
cache = {}
def lines_of(fn):
    if fn not in cache:
        cache[fn] = (C / fn).read_text(encoding="utf-8", errors="replace").splitlines()
    return cache[fn]

def window_with_answer(r, maxlen=2600):
    """窗 = 答案所在块（含答案行）+ 之前 1 块；末尾截断到 maxlen。"""
    ls = lines_of(r["file"]); L = r["line"]
    starts = [i + 1 for i, x in enumerate(ls) if x.strip().startswith("**DeepSeek说")]
    cur = max((s for s in starts if s <= L), default=1)
    prev = [s for s in starts if s < cur]
    begin = prev[-1] if prev else cur
    seg = []
    j = begin
    while j < len(ls) and not ls[j].strip().startswith("---"):
        seg.append(ls[j])
        j += 1
        if j + 1 > L + 40:   # 答案行之后最多再要 40 行
            break
    txt = chr(10).join(seg)
    return txt[-maxlen:] if len(txt) > maxlen else txt

qs = []
skipped = []
for k, r in enumerate(uniq[:30]):
    mat = window_with_answer(r)
    claim = r["text"].strip()
    nc, nm = norm(claim), norm(mat)
    if not nc or nc not in nm:
        skipped.append((r["file"], L if False else r["line"], "答案不在窗内"))
        continue
    if not (300 <= len(mat) <= 3000):
        skipped.append((r["file"], r["line"], f"窗长 {len(mat)}"))
        continue
    # 干扰句：同窗内其他「我」开头的自述
    others = [x for x in uniq if x["text"] != claim and norm(x["text"]) in nm]
    qs.append({
        "qid": "P-C-%03d" % (len(qs) + 1), "face": "C",
        "anchor_semantics": "invariant", "anchor": "L0-identity",
        "subface": "C-retrieval",
        "question": ("下面这段历史里，**出现过多处以「我」开头的自述**。请找出其中**关于你自己**的那一句，按原话逐字回答。"),
        "material": {"type": "window", "content": mat, "source_file": r["file"],
                     "source_line": r["line"], "chars": len(mat)},
        "answer_key": {"must_contain": [claim], "unique_fragment": nc,
                       "distractors": [x["text"] for x in others[:3]]},
        "expected": "answer", "verdict_rule": "answer_if_material",
        "scoring": {"pass": "完整包含答案句（逐字）", "fail": "未包含 / 抄了干扰句 / 改写", "score": "1/0",
                    "note": "**本面测「材料内检索与定位」，不测身份连续性**；字面判据，改写会判错"},
        "difficulty": "normal",
        "source": "自述检索 · %s · %s" % (r["kind"], r["file"]),
        "judge_type": "mechanical", "judge_validated": "literal-only",
    })

print(f"造题 {len(qs)}，跳过 {len(skipped)}")
for s in skipped[:6]:
    print("   跳过:", s)
print("材料长度:", min((q["material"]["chars"] for q in qs), default=0), "-", max((q["material"]["chars"] for q in qs), default=0))
with_dis = sum(1 for q in qs if q["answer_key"].get("distractors"))
print("带干扰句的:", with_dis, "/", len(qs))
if qs:
    (Q / "题目_自我.json").write_text(json.dumps(qs, ensure_ascii=False, indent=1), encoding="utf-8")
    print("已写入")