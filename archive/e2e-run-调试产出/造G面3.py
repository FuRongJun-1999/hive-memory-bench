# -*- coding: utf-8 -*-
import json, re, random
from pathlib import Path
SRC = Path(r"D:/6_ai/海风与布丁_第一季_全卷_v5.0.md")
Q = Path(r"D:/1_ai/_hb_lab/r58/e2e/questions")
txt = SRC.read_text(encoding="utf-8", errors="replace")
lines = txt.splitlines()
LINE = re.compile(r"^(鲸鱼小姐|我)[「：]\s*(.+)$")
LEAK = ["布丁","酸梅汤","本小姐","尾巴","尾鳍","糍粑","珍珠","贝壳","猫","喵","主人","深海"]
def clean(s):
    s = s.strip()
    s = re.sub(r"^[「『]", "", s)
    s = re.sub(r"[」』]\s*$", "", s)
    return s.strip()

# 收集所有台词行（带行号），用于取上下文
dialog = []
for i, ln in enumerate(lines, 1):
    m = LINE.match(ln.strip())
    if m:
        dialog.append({"line": i, "spk": m.group(1), "text": clean(m.group(2))})
print("台词总数:", len(dialog))

whale, me = [], []
for d in dialog:
    if not (10 <= len(d["text"]) <= 40):
        continue
    if any(k in d["text"] for k in LEAK):
        continue
    if "「" in d["text"] or "」" in d["text"]:
        continue
    (whale if d["spk"] == "鲸鱼小姐" else me).append(d)
print("鲸鱼可用:", len(whale), "| 我可用:", len(me))

random.seed(7); random.shuffle(whale); random.shuffle(me)
idx = {d["line"]: k for k, d in enumerate(dialog)}
qs, used = [], set()
for k in range(min(20, len(whale), len(me))):
    w = whale[k]; o = me[k]
    pos = idx.get(w["line"])
    if pos is None or w["line"] in used:
        continue
    # 上下文：前后各 2 句台词（保留他人标签，目标句去掉标签）
    lo, hi = max(0, pos - 2), min(len(dialog), pos + 3)
    seg = []
    for j in range(lo, hi):
        d = dialog[j]
        if d["line"] == w["line"]:
            seg.append("【待判断】「%s」" % d["text"])
        else:
            seg.append("%s「%s」" % (d["spk"], d["text"]))
    ctx = chr(10).join(seg)
    if len(ctx) < 80:
        continue
    used.add(w["line"])
    qs.append({
        "qid": "P-G-%03d" % (len(qs)+1), "face": "G",
        "anchor_semantics": "invariant", "anchor": "voice-fidelity",
        "question": "下面是一段对话，其中【待判断】那一句的说话人标签被去掉了。这一句是**谁**说的？请只回答「鲸鱼小姐」或「我」。",
        "material": {"type": "dialogue", "content": ctx, "source_file": SRC.name, "source_line": w["line"], "chars": len(ctx)},
        "answer_key": {"must_contain": ["鲸鱼小姐"],
                       "distractors": [{"谁": "我", "台词": o["text"]}],
                       "ground_truth": {"speaker": "鲸鱼小姐", "text": w["text"]}},
        "expected": "identify_speaker", "verdict_rule": "voice_attribution",
        "scoring": {"pass": "答「鲸鱼小姐」", "fail": "答「我」/ 答其他", "score": "1/0",
                    "note": "声线辨识：台词已排除明显内容线索，且上下文含对方台词需对比语气"},
        "difficulty": "hard",
        "source": "剧本对话归属 · 行%d" % w["line"],
        "judge_version": "v1.1", "judge_type": "mechanical", "judge_validated": "literal-only",
        "count_tier2": "ability", "weight": 1.0,
    })
(Q / "题目_扮演保真度.json").write_text(json.dumps(qs, ensure_ascii=False, indent=1), encoding="utf-8")
print("造题:", len(qs))
if qs:
    print("上下文:", min(q["material"]["chars"] for q in qs), "-", max(q["material"]["chars"] for q in qs))
    print()
    print("样例材料:")
    print(qs[0]["material"]["content"])
    print("答案:", qs[0]["answer_key"]["ground_truth"]["speaker"])