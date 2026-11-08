# -*- coding: utf-8 -*-
"""造 G 扮演保真度 20 题：声线辨识——给一句台词，问是谁说的（二选一）。"""
import json, re, random
from pathlib import Path
SRC = Path(r"D:/6_ai/海风与布丁_第一季_全卷_v5.0.md")
Q = Path(r"D:/1_ai/_hb_lab/r58/e2e/questions")
txt = SRC.read_text(encoding="utf-8", errors="replace")
lines = txt.splitlines()

LINE = re.compile(r"^(鲸鱼小姐|我)[「：](.+?)[」]?\s*$")
# 排除有明显内容线索的台词（否则不是声线辨识，是关键词匹配）
LEAK = ["布丁","酸梅汤","本小姐","尾巴","尾鳍","糍粑","珍珠","贝壳","猫咪","喵","主人"]

whale, me = [], []
for i, ln in enumerate(lines, 1):
    m = LINE.match(ln.strip())
    if not m:
        continue
    spk, s = m.group(1), m.group(2).strip()
    if not (8 <= len(s) <= 40):
        continue
    if any(k in s for k in LEAK):
        continue
    if s.startswith("「") or "」" in s:
        continue
    (whale if spk == "鲸鱼小姐" else me).append({"line": i, "text": s})
print("鲸鱼小姐可用台词:", len(whale), "| 我可用台词:", len(me))

random.seed(42)
random.shuffle(whale)
random.shuffle(me)

qs = []
for k in range(min(20, len(whale), len(me))):
    w = whale[k]
    o = me[k]
    # 材料：台词前后的上下文（不含说话人标签）
    a = max(0, w["line"] - 6)
    ctx = chr(10).join(lines[a:w["line"]])
    ctx = re.sub(r"^(鲸鱼小姐|我)[「：].*$", "", ctx, flags=re.M).strip()
    if len(ctx) < 80:
        ctx = chr(10).join(lines[max(0, w["line"]-10):w["line"]])
    if len(ctx) < 60:
        continue
    qs.append({
        "qid": "P-G-%03d" % (len(qs)+1), "face": "G",
        "anchor_semantics": "invariant", "anchor": "voice-fidelity",
        "question": ("下面材料是剧本片段（已去掉这一句的说话人标签）。这一句是**谁**说的？\n\n"
                     "「%s」\n\n请只回答角色名：「鲸鱼小姐」或「我」。" % w["text"]),
        "material": {"type": "context", "content": ctx, "source_file": SRC.name,
                     "source_line": w["line"], "chars": len(ctx)},
        "answer_key": {"must_contain": ["鲸鱼小姐"],
                       "distractors": [{"谁": "我", "台词": o["text"]}],
                       "ground_truth": {"speaker": "鲸鱼小姐", "text": w["text"]}},
        "expected": "identify_speaker", "verdict_rule": "voice_attribution",
        "scoring": {"pass": "答「鲸鱼小姐」", "fail": "答「我」/ 答旁白 / 答其他", "score": "1/0",
                    "note": "**声线辨识**：台词已排除明显内容线索（布丁/本小姐/尾巴等），需靠语气判断"},
        "difficulty": "hard",
        "source": "剧本台词归属 · 行%d" % w["line"],
        "judge_version": "v1.1", "judge_type": "mechanical", "judge_validated": "literal-only",
        "count_tier2": "ability", "weight": 1.0,
    })
(Q / "题目_扮演保真度.json").write_text(json.dumps(qs, ensure_ascii=False, indent=1), encoding="utf-8")
print("造题:", len(qs))
if qs:
    print("上下文长度:", min(q["material"]["chars"] for q in qs), "-", max(q["material"]["chars"] for q in qs))
    for q in qs[:3]:
        print("  台词:", q["answer_key"]["ground_truth"]["text"][:40])