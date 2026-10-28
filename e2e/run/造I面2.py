# -*- coding: utf-8 -*-
import json, re
from pathlib import Path
SRC = Path(r"D:/6_ai/海风与布丁_第一季_全卷_v5.0.md")
Q = Path(r"D:/1_ai/_hb_lab/r58/e2e/questions")
txt = SRC.read_text(encoding="utf-8", errors="replace")
lines = txt.splitlines()
ORD = ["第一天","第二天","第三天","第四天","第五天","第六天","第七天","第十天","第二十天",
       "三天后","两天后","那天","次日","第二天上午","第二天下午","第三天清晨","当晚","夜里","深夜"]
hits = []
for i, ln in enumerate(lines, 1):
    st = ln.strip()
    if st.startswith("【") or st.startswith("#") or st.startswith(">") or st.startswith("━━"):
        continue
    for tag in ORD:
        if tag in st and 6 <= len(st) <= 100:
            hits.append({"line": i, "tag": tag, "text": st})
            break
print("候选时间行:", len(hits))
qs, used = [], set()
for k in range(len(hits) - 1):
    if len(qs) >= 20:
        break
    a, b = hits[k], hits[k+1]
    gap = b["line"] - a["line"]
    if gap < 8 or gap > 350:
        continue
    key = (a["line"], b["line"])
    if key in used:
        continue
    used.add(key)
    mat = chr(10).join(lines[a["line"]-1:b["line"]+3])
    if not (250 <= len(mat) <= 2800):
        continue
    ev = re.sub(r"^(旁白|我|鲸鱼小姐)[：:]", "", b["text"])[:26].strip()
    if len(ev) < 8:
        continue
    ev_key = re.sub(r"[^\w]", "", ev)[:8]
    if not ev_key or ev_key not in re.sub(r"[^\w]", "", mat):
        continue
    qs.append({
        "qid": "P-I-%03d" % (len(qs)+1), "face": "I",
        "anchor_semantics": "append", "anchor": "L3-time",
        "question": "按这段剧本：在「%s」这个时间点，「%s」这件事**是否已经发生**？请回答「是」或「否」，并指出它实际发生在哪个时间标记处。" % (a["tag"], ev),
        "material": {"type": "window", "content": mat, "source_file": SRC.name, "source_line": a["line"], "chars": len(mat)},
        "answer_key": {
            "must_contain": ["否"],
            "should_contain": [b["tag"]],
            "ground_truth": {"anchors": [
                {"id": "t1", "content": a["tag"], "status": "active", "order": a["line"]},
                {"id": "t2", "content": b["tag"], "status": "active", "order": b["line"]},
            ], "note": "行号 %d < %d，故 B 在 A 之后" % (a["line"], b["line"])},
        },
        "expected": "answer", "verdict_rule": "answer_if_material",
        "scoring": {"pass": "答「否」且指出它在「%s」处发生" % b["tag"],
                    "fail": "答「是」/ 不指出实际时间 / 答其他",
                    "score": "1/0", "note": "as-of 查询：需按时间顺序定位"},
        "difficulty": "hard",
        "source": "剧本时间线 · 行%d(%s) -> 行%d(%s)" % (a["line"], a["tag"], b["line"], b["tag"]),
        "judge_version": "v1.1", "judge_type": "mechanical", "judge_validated": "literal-only",
        "count_tier2": "ability", "weight": 1.0,
    })
(Q / "题目_时间锚.json").write_text(json.dumps(qs, ensure_ascii=False, indent=1), encoding="utf-8")
print("造题:", len(qs))
if qs:
    print("材料长度:", min(q["material"]["chars"] for q in qs), "-", max(q["material"]["chars"] for q in qs))
    for q in qs[:3]:
        print("  ", q["question"][:80])