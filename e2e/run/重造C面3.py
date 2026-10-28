# -*- coding: utf-8 -*-
"""P1-1：C 面重造 v3——窗按「块」取（不跨 --- ），答案必在窗内。"""
import json, re
from pathlib import Path

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
print("候选:", len(uniq))

def norm(s):
    return re.sub(r"[^\w]", "", s or "", flags=re.UNICODE)
cache = {}
def lines_of(fn):
    if fn not in cache:
        cache[fn] = (C / fn).read_text(encoding="utf-8", errors="replace").splitlines()
    return cache[fn]

def block_of(r):
    """取答案行所在的整块（0-based 切片），块边界是 **DeepSeek说 或 ---。"""
    ls = lines_of(r["file"])
    L0 = r["line"] - 1  # 0-based
    # 向前找边界
    a = L0
    while a > 0:
        cur = ls[a].strip()
        prevl = ls[a - 1].strip()
        if prevl.startswith("**DeepSeek说") or prevl.startswith("---"):
            break
        a -= 1
    # 向后找边界
    b = L0
    while b < len(ls) - 1:
        if ls[b].strip().startswith("---") or ls[b + 1].strip().startswith("**DeepSeek说"):
            break
        b += 1
    return ls[a:b + 1]

qs, skipped = [], []
for k, r in enumerate(uniq[:40]):
    blk = block_of(r)
    mat = chr(10).join(blk).strip()
    if len(mat) > 2800:
        mat = mat[:2800]
    claim = r["text"].strip()
    nc, nm = norm(claim), norm(mat)
    if not nc or nc not in nm:
        skipped.append((r["file"], r["line"], "块内不含答案", len(mat)))
        continue
    if len(mat) < 120:
        skipped.append((r["file"], r["line"], "块太短", len(mat)))
        continue
    others = [x["text"] for x in uniq if x["text"] != claim and norm(x["text"]) in nm]
    qs.append({
        "qid": "P-C-%03d" % (len(qs) + 1), "face": "C",
        "anchor_semantics": "invariant", "anchor": "L0-identity",
        "subface": "C-retrieval",
        "question": "下面这段历史里出现过多处以「我」开头的自述。请找出**关于你自己**的那一句，按原话逐字回答。",
        "material": {"type": "block", "content": mat, "source_file": r["file"],
                     "source_line": r["line"], "chars": len(mat)},
        "answer_key": {"must_contain": [claim], "unique_fragment": nc,
                       "distractors": others[:3]},
        "expected": "answer", "verdict_rule": "answer_if_material",
        "scoring": {"pass": "完整包含答案句（逐字）", "fail": "未包含 / 抄了干扰句 / 改写", "score": "1/0",
                    "note": "**本面测「材料内检索与定位」，不测身份连续性**；字面判据"},
        "difficulty": "normal",
        "source": "自述检索 · %s · %s" % (r["kind"], r["file"]),
        "judge_type": "mechanical", "judge_validated": "literal-only",
    })

print(f"造题 {len(qs)}，跳过 {len(skipped)}")
for s in skipped[:8]:
    print("   ", s)
if qs:
    print("材料长度:", min(q["material"]["chars"] for q in qs), "-", max(q["material"]["chars"] for q in qs))
    print("带干扰:", sum(1 for q in qs if q["answer_key"]["distractors"]), "/", len(qs))
    (Q / "题目_自我.json").write_text(json.dumps(qs, ensure_ascii=False, indent=1), encoding="utf-8")
    print("已写入")