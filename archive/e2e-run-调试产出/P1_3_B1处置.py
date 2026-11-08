# -*- coding: utf-8 -*-
"""P1-3：B1 处置——明确它是「猜真实下文」，不计数；并处置四道超长窗。"""
import json
from pathlib import Path
Q = Path(r"D:/1_ai/_hb_lab/r58/e2e/questions")
P = Q / "题目_续接.json"
data = json.loads(P.read_text(encoding="utf-8"))

# 1) 四道超长窗
VOID = {
  "P-B1-C-041": "材料窗 16,848 字符（含思维链），且答案键「对外交流文件／中科院院士」在材料内无线索，推不出",
  "P-B1-C-095": "材料窗 9,485 字符；答案键「那么我们是否还有其他问题」在材料内无对应线索",
  "P-B1-C-116": "材料窗 70,858 字符（含 API 响应 JSON）；答案键是工具输出，非可预测的对话请求",
}
nv = 0
for q in data:
    if q["qid"] in VOID:
        q["v2_pass"] = False
        q["v2_fail_reason"] = VOID[q["qid"]]
        nv += 1
print("标废 B1（推不出/超长）:", nv)

# 2) 078 截窗到 8000（答案在窗内，可保留）
nfix = 0
for q in data:
    if q["qid"] == "P-B1-C-078":
        m = q["material"]["content"]
        mc = q["answer_key"]["must_contain"][0]
        if len(m) > 7800:
            # 从尾部保留 7800，并确认答案仍在
            newm = m[-7800:]
            if mc in newm:
                q["material"]["content"] = newm
                q["material"]["chars"] = len(newm)
                q["material"]["truncated"] = True
                q["material"]["truncate_note"] = "原 %d 字符，保留尾部 7800（答案仍在窗内）" % len(m)
                q["v2_pass"] = True
                q.pop("v2_fail_reason", None)
                nfix += 1
            else:
                q["v2_pass"] = False
                q["v2_fail_reason"] = "截窗后答案键丢失"
print("B1-078 截窗修复:", nfix)

# 3) B1 全量：明确 measures + 不计数
nb1 = 0
for q in data:
    if q.get("face") == "B1":
        q["measures"] = "guess-real-continuation"
        q["measures_note"] = ("**本面测「能否猜中真实史的下一个请求」，不测上下文重建**。"
                              "答案键是真实史原文，材料窗内通常无线索；判据为公共子串≥8。")
        q["counted"] = False
        q["counted_reason"] = "测「猜真实下文」而非可推断任务；不进横比总分，单列参考"
        nb1 += 1
P.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
print("B1 标 measures + counted=false:", nb1)

# 4) 统计可计数题
print()
from collections import Counter
cnt = Counter(); excl = Counter()
for p in Q.glob("题目_*.json"):
    if "残缺诊断" in p.name:
        continue
    for q in json.loads(p.read_text(encoding="utf-8")):
        f = q.get("face")
        if q.get("v2_pass") is False:
            excl[f] += 1
        elif q.get("counted") is False:
            cnt[f] += 1
        else:
            cnt[f] += 0
print("=== 各面：排除 / 不计数 / 可计数 ===")
for p in sorted(Q.glob("题目_*.json")):
    if "残缺诊断" in p.name:
        continue
    d = json.loads(p.read_text(encoding="utf-8"))
    if not d:
        continue
    f = d[0].get("face")
    e = sum(1 for q in d if q.get("v2_pass") is False)
    nc = sum(1 for q in d if q.get("v2_pass") is not False and q.get("counted") is False)
    c = sum(1 for q in d if q.get("v2_pass") is not False and q.get("counted") is not False)
    print(f"  {f:3s} 共{len(d):3d} | 排除{e:2d} | 不计数{nc:3d} | **可计数{c:3d}**")