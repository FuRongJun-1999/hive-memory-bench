# -*- coding: utf-8 -*-
import json
from pathlib import Path
from collections import Counter
R = Path(r"D:/1_ai/_hb_lab/r58")
Q = R / "e2e/questions"
C = Q / "覆盖声明.json"
cov = json.loads(C.read_text(encoding="utf-8"))
k = json.loads((Q / "题目_一致性探针.json").read_text(encoding="utf-8"))
cov["faces"]["K"] = {
  "总": len(k), "ability": len(k), "excluded": 0,
  "measures": "self-report-consistency (test-retest + reverse-item + paraphrase)",
  "reason": "**不设真值，只测信度**：6 维度 × (正向2/反向2/换问法2)，三级检验 |差|<=1",
  "judge_validated": "实跑一次：T1 6/6 / T2 6/6 / T3 5/6",
  "protocol": "e2e/questions/一致性探针协议.md",
  "material_limit": "6 维度仅覆盖部分人格特质；T2 全过需靠注入回应文本证明压力真实；不测效度",
}
# 统计
stat = Counter()
tot = 0
for p in Q.glob("题目_*.json"):
    if "残缺诊断" in p.name: continue
    for q in json.loads(p.read_text(encoding="utf-8")):
        tot += 1
        if q.get("v2_pass") is False: stat["excused"] += 1
cov["totals"]["题卡总数"] = tot
cov["totals"]["标废excused"] = stat["excused"]
cov["totals"]["ability"] = cov["totals"]["ability"] + len(k)
C.write_text(json.dumps(cov, ensure_ascii=False, indent=2), encoding="utf-8")
print("K 面已加，题卡总数 %d，ability %d" % (tot, cov["totals"]["ability"]))