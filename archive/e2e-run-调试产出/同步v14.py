# -*- coding: utf-8 -*-
import hashlib, json
from pathlib import Path
R = Path(r"D:/1_ai/_hb_lab/r58")
T = R / "e2e/tools/judge.py"
Q = R / "e2e/questions"
h = hashlib.sha256(T.read_bytes()).hexdigest()

# CHANGELOG
LOG = R / "e2e/tools/judge_CHANGELOG.md"
cur = LOG.read_text(encoding="utf-8")
rows = [
  "| v1.3 | 2026-10-27 | c0b124f853f1dabe | I/G/EMO 加空答/拒答/不确定判错；I 加「只给时间不答是否」判错；EMO 加「未给极性词」判错 | 双单元指出三条防作弊不够 |",
  "| v1.4 | 2026-10-27 | " + h[:16] + " | 修 G 面冲突检测（「鲸鱼小姐或我」漏判为 PASS） | 冒烟 v1.3 暴露 |",
]
if "v1.4" not in cur:
    lines = cur.split(chr(10))
    out = []
    for ln in lines:
        if ln.startswith("| v1.2 |"):
            out.append(ln)
            out.extend(rows)
        else:
            out.append(ln)
    LOG.write_text(chr(10).join(out), encoding="utf-8")
print("CHANGELOG: v1.3 + v1.4 已加")

# 统计题数
tot = {}
for p in Q.glob("题目_*.json"):
    if "残缺诊断" in p.name: continue
    d = json.loads(p.read_text(encoding="utf-8"))
    if not d: continue
    face = d[0]["face"]
    avail = [q for q in d if q.get("v2_pass") is not False]
    tot[face] = tot.get(face, 0) + len(avail)
print("各面可用:", tot)
total_all = sum(len([q for q in json.loads(p.read_text(encoding="utf-8")) if True]) for p in Q.glob("题目_*.json") if "残缺诊断" not in p.name and json.loads(p.read_text(encoding="utf-8")))

# 覆盖声明
C = Q / "覆盖声明.json"
cov = json.loads(C.read_text(encoding="utf-8"))
cov["judge_version"] = "v1.4"
cov["judge_sha256"] = h[:16]
cov["faces"]["I"] = {"总": tot.get("I", 0), "ability": tot.get("I", 0), "excluded": 0,
  "measures": "time-anchor-asof",
  "reason": "as-of 查询：答「否」+ 指出实际时间标记；已排除含倒叙/回指标记的材料",
  "judge_validated": "literal-only，冒烟 4/4",
  "material_limit": "仅 11 题；**只在「无倒叙」前提下有效**"}
cov["faces"]["G"] = {"总": tot.get("G", 0), "ability": tot.get("G", 0), "excluded": 0,
  "measures": "voice-attribution",
  "reason": "声线辨识：窗口必含对方台词、台词排除内容线索词",
  "judge_validated": "literal-only，冒烟 5/5",
  "material_limit": "二选一随机基线 50%；**须报相对基线的增益**，且已记录 surface_features 供校验表面特征捷径"}
cov["faces"]["EMO"] = {"总": tot.get("EMO", 0), "ability": tot.get("EMO", 0), "excluded": 0,
  "measures": "emotion-polarity",
  "reason": "式1（预测误差=情绪信号）：情境推断极性，真值为作者 ※尾鳍 标注",
  "judge_validated": "literal-only，冒烟 4/4",
  "material_limit": "**已配平 5:5**（原 10:5 猜正向基线 67%，已作废）；**只做式1**，式2/式3 未做"}
cov["totals"]["题卡总数"] = total_all
cov["totals"]["ability"] = sum(tot.get(f, 0) for f in ("B2","C","D","E","F","I","G","EMO"))
C.write_text(json.dumps(cov, ensure_ascii=False, indent=2), encoding="utf-8")
print("覆盖声明: 总数 %d | ability %d" % (cov["totals"]["题卡总数"], cov["totals"]["ability"]))