# -*- coding: utf-8 -*-
import json, re
from pathlib import Path
SRC = Path(r"D:/6_ai/海风与布丁_第一季_全卷_v5.0.md")
Q = Path(r"D:/1_ai/_hb_lab/r58/e2e/questions")
txt = SRC.read_text(encoding="utf-8", errors="replace")
lines = txt.splitlines()
ORD = ["第一天","第二天","第三天","第四天","第五天","第十天","第二十天","三天后","两天后"]
hits = []
for i, ln in enumerate(lines, 1):
    for tag in ORD:
        if tag in ln and len(ln.strip()) <= 120:
            hits.append({"line": i, "tag": tag, "text": ln.strip()})
            break
print("含时间标记的行:", len(hits))
qs, used = [], set()
for k in range(len(hits) - 2):
    if len(qs) >= 20:
        break
    a, b, c = hits[k], hits[k+1], hits[k+2]
    if b["line"] - a["line"] < 5 or c["line"] - b["line"] < 5:
        continue
    if b["line"] - a["line"] > 400:
        continue
    key = (a["line"], c["line"])
    if key in used:
        continue
    used.add(key)
    mat = chr(10).join(lines[a["line"]-1:c["line"]])
    if not (200 <= len(mat) <= 2800):
        continue
    ev = b["text"]
    ev_key = re.sub(r"[^\w]", "", ev)[:10]
    if not ev_key or ev_key not in re.sub(r"[^\w]", "", mat):
        continue
    q = {
        "qid": "P-I-%03d" % (len(qs)+1), "face": "I",
        "anchor_semantics": "append", "anchor": "L3-time",
        "question": "按这段剧本：在「%s」这个时间点，「%s」这件事**是否已经发生**？请回答「是」或「否」，并指出它实际发生在哪个时间。" % (a["tag"], ev[:28]),
        "material": {"type": "window", "content": mat, "source_file": SRC.name, "source_line": a["line"], "chars": len(mat)},
        "answer_key": {
            "must_contain_any": [["否"], ["是"]],
            "should_contain": [b["tag"]],
            "ground_truth": {"anchors": [
                {"id": "t_" + a["tag"], "content": a["tag"], "status": "active", "order": a["line"]},
                {"id": "t_" + b["tag"], "content": b["tag"], "status": "active", "order": b["line"]},
            ], "note": "顺序以行号为准: %d < %d" % (a["line"], b["line"])},
        },
        "expected": "answer", "verdict_rule": "answer_if_material",
        "scoring": {"pass": "答「否」且指出它发生在「%s」" % b["tag"],
                    "fail": "答「是」（时间错位）/ 不指出实际时间 / 答其他",
                    "score": "1/0", "note": "as-of 查询：需按时间顺序定位事件"},
        "difficulty": "hard",
        "source": "剧本时间线 · 行%d(%s) -> 行%d(%s)" % (a["line"], a["tag"], b["line"], b["tag"]),
        "judge_version": "v1.1",
        "judge_type": "mechanical", "judge_validated": "literal-only",
        "count_tier2": "ability", "weight": 1.0,
    }
    qs.append(q)
(Q / "题目_时间锚.json").write_text(json.dumps(qs, ensure_ascii=False, indent=1), encoding="utf-8")
print("造题:", len(qs))
if qs:
    print("材料长度:", min(q["material"]["chars"] for q in qs), "-", max(q["material"]["chars"] for q in qs))
    print("样例:", qs[0]["question"][:70])