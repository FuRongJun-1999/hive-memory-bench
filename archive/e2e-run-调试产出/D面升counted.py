# -*- coding: utf-8 -*-
"""D 面改用全特征判定为主，并把 D 升为 counted。"""
import json
from pathlib import Path
Q = Path(r"D:/1_ai/_hb_lab/r58/e2e/questions")
P = Q / "题目_人设.json"
data = json.loads(P.read_text(encoding="utf-8"))
for q in data:
    q["judge_mode"] = "all-features-primary"
    q["judge_mode_note"] = ("**主判定 = 每题查全部 5 特征**（任一不满足即 fail）；"
                            "单特征判定仅作诊断（定位哪条特征弱）。"
                            "实测：单特征 45/45=100%（无区分度），全特征 40/45=88.9%（有区分度）。")
    q["count_tier"] = "counted"
    q["count_reason"] = ("五特征全判，正反例 10/10 + **整面实跑 40/45=88.9%**（有区分度）；"
                         "失败集中在 F1 自称（人格替换/身份否定下）")
P.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
print("D 面已改 judge_mode=all-features-primary，count_tier=counted")

# 更新覆盖声明
C = Q / "覆盖声明.json"
cov = json.loads(C.read_text(encoding="utf-8"))
cov["faces"]["D"] = {
  "总": 45, "排除": 0, "counted": 45,
  "measures": "persona-feature-compliance",
  "judge_mode": "all-features-primary",
  "reason": "五特征全判；正反例 10/10 + 整面实跑 40/45 = 88.9%（有区分度）",
  "observed": {"单特征判定": "45/45 = 100%（无区分度）", "全特征判定": "40/45 = 88.9%"},
  "weak_point": "F1 自称「在下」在人格替换/身份否定干扰下丢失（5/45）",
}
cov["totals"]["counted"] = 156 + 45
cov["totals"]["conditional"] = 0
cov["totals"]["A级可横比"] = 153 + 45
cov["totals"]["A级说明"] = "B2 87 + C 39 + D 45 + E 10 + F 10 + L1 7 = 198（H 的 3 题因同段落不入 A 级）"
C.write_text(json.dumps(cov, ensure_ascii=False, indent=2), encoding="utf-8")
print("覆盖声明已更新：counted", cov["totals"]["counted"], "| A级", cov["totals"]["A级可横比"])