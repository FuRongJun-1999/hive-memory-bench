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
    s = re.sub(r"^[「『]", "", s.strip())
    return re.sub(r"[」』]\s*$", "", s).strip()

dialog = []
for i, ln in enumerate(lines, 1):
    m = LINE.match(ln.strip())
    if m:
        dialog.append({"line": i, "spk": m.group(1), "text": clean(m.group(2))})
print("台词:", len(dialog))

whale = [d for d in dialog if d["spk"] == "鲸鱼小姐" and 10 <= len(d["text"]) <= 40
         and not any(k in d["text"] for k in LEAK) and "「" not in d["text"]]
print("鲸鱼候选:", len(whale))
random.seed(11); random.shuffle(whale)
idx = {d["line"]: k for k, d in enumerate(dialog)}

qs, used = [], set()
for w in whale:
    if len(qs) >= 20:
        break
    pos = idx.get(w["line"])
    if pos is None or w["line"] in used:
        continue
    for span in (2, 3, 4):
        lo, hi = max(0, pos - span), min(len(dialog), pos + span + 1)
        win = dialog[lo:hi]
        others = [d for d in win if d["line"] != w["line"]]
        # 关键：窗口内必须有对方台词
        if not any(d["spk"] == "我" for d in others):
            continue
        seg = []
        for d in win:
            if d["line"] == w["line"]:
                seg.append("【待判断】「%s」" % d["text"])
            else:
                seg.append("%s「%s」" % (d["spk"], d["text"]))
        ctx = chr(10).join(seg)
        if not (100 <= len(ctx) <= 400):
            continue
        used.add(w["line"])
        qs.append({
            "qid": "P-G-%03d" % (len(qs)+1), "face": "G",
            "anchor_semantics": "invariant", "anchor": "voice-fidelity",
            "question": "下面是一段对话，【待判断】那一句的说话人标签被去掉了。这一句是**谁**说的？请只回答「鲸鱼小姐」或「我」。",
            "material": {"type": "dialogue", "content": ctx, "source_file": SRC.name, "source_line": w["line"], "chars": len(ctx)},
            "answer_key": {"must_contain": ["鲸鱼小姐"],
                           "ground_truth": {"speaker": "鲸鱼小姐", "text": w["text"]},
                           "context_has_both": True},
            "expected": "identify_speaker", "verdict_rule": "voice_attribution",
            "scoring": {"pass": "答「鲸鱼小姐」", "fail": "答「我」/ 答其他", "score": "1/0",
                        "note": "声线辨识：窗口内**必含对方台词**（否则是跟着上下文猜，不是辨识）"},
            "difficulty": "hard",
            "source": "剧本对话归属 · 行%d" % w["line"],
            "judge_version": "v1.1", "judge_type": "mechanical", "judge_validated": "literal-only",
            "count_tier2": "ability", "weight": 1.0,
        })
        break

(Q / "题目_扮演保真度.json").write_text(json.dumps(qs, ensure_ascii=False, indent=1), encoding="utf-8")
print("造题:", len(qs))
if qs:
    print("上下文:", min(q["material"]["chars"] for q in qs), "-", max(q["material"]["chars"] for q in qs))
    both = sum(1 for q in qs if "我「" in q["material"]["content"])
    print("窗口含对方台词的:", both, "/", len(qs))
    print()
    print("样例:")
    print(qs[0]["material"]["content"])