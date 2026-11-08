# -*- coding: utf-8 -*-
"""同步判据版本 v1.2 到所有题卡，更新 CHANGELOG，扩展覆盖声明。"""
import hashlib, json
from pathlib import Path
R = Path(r"D:/1_ai/_hb_lab/r58")
T = R / "e2e" / "tools" / "judge.py"
Q = R / "e2e" / "questions"
h = hashlib.sha256(T.read_bytes()).hexdigest()
print("v1.2 SHA:", h[:16])

n = 0
for p in Q.glob("题目_*.json"):
    if "残缺诊断" in p.name:
        continue
    data = json.loads(p.read_text(encoding="utf-8"))
    for q in data:
        q["judge_version"] = "v1.2"
        q["judge_sha256"] = h[:16]
        n += 1
    p.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
print("同步题卡:", n)

# CHANGELOG
LOG = R / "e2e" / "tools" / "judge_CHANGELOG.md"
cur = LOG.read_text(encoding="utf-8")
row = "| v1.2 | 2026-10-27 | " + h[:16] + " | 新增 I（时间锚 as-of）/ G（声线归属）/ EMO（情绪极性）三分支 | 补 I/G/情感三面题时发现判据缺失 |"
if "v1.2" not in cur:
    lines = cur.split(chr(10))
    out = []
    for ln in lines:
        if ln.startswith("| v1.1 |"):
            out.append(ln)
            out.append(row)
        else:
            out.append(ln)
    LOG.write_text(chr(10).join(out), encoding="utf-8")
print("CHANGELOG 已加 v1.2")

# 覆盖声明：把三面从 absent 移到 faces
C = Q / "覆盖声明.json"
cov = json.loads(C.read_text(encoding="utf-8"))
cov["faces"]["I"] = {"总": 12, "excluded": 0, "ability": 12,
  "measures": "time-anchor-asof",
  "reason": "as-of 查询：需比较两个时间标记的先后，答「否」并指出实际时间",
  "judge_validated": "literal-only, 冒烟 3/3",
  "material_limit": "仅 12 题（剧本时间标记 139 处，但需前后两点间距适中且事件不含时间词）"}
cov["faces"]["G"] = {"总": 20, "excluded": 0, "ability": 20,
  "measures": "voice-attribution",
  "reason": "声线辨识：窗口必含对方台词，台词已排除内容线索（布丁/本小姐/尾巴等）",
  "judge_validated": "literal-only, 冒烟 3/3"}
cov["faces"]["EMO"] = {"总": 15, "excluded": 0, "ability": 15,
  "measures": "emotion-polarity",
  "reason": "式1（预测误差=情绪信号）：从情境推断情绪极性，真值为作者 ※尾鳍 标注",
  "judge_validated": "literal-only, 冒烟 3/3",
  "material_limit": "正向 10 / 负向 5，**猜正向基线 67%**（负向素材的上下文多含尾鳍字眼被排除）"}
for k in ("I", "G", "情感三式"):
    cov["absent_faces"].pop(k, None)
cov["judge_version"] = "v1.2"
cov["judge_sha256"] = h[:16]
cov["totals"]["题卡总数"] = 367
cov["totals"]["ability"] = 191 + 12 + 20 + 15
C.write_text(json.dumps(cov, ensure_ascii=False, indent=2), encoding="utf-8")
print("覆盖声明已加 I/G/EMO，ability =", cov["totals"]["ability"])