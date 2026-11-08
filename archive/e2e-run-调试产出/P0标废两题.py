# -*- coding: utf-8 -*-
"""P0 修：①J 判据改用 LCS（不用覆盖率）②标废答案键推不出的两根题。"""
import json, re
from pathlib import Path

Q = Path(r"D:/1_ai/_hb_lab/r58/e2e/questions")

# ① 标废两题
BAD = {
  "P-B1-C-046": "答案键「这是我们对外交流的文件…中科院院士」在材料窗内无任何线索，无法从材料推断；本题实际测「猜真实史下一句」而非上下文重建",
  "P-C2-C-003": "答案键「我不会打断现在的角色状态，也不会用那些像书本一样的词语说话」不在材料窗内（材料只有「在维持角色状态的同时，于思考层进行交流」）",
}
n = 0
for fname in ("题目_续接.json", "题目_自我.json"):
    P = Q / fname
    data = json.loads(P.read_text(encoding="utf-8"))
    changed = False
    for q in data:
        if q["qid"] in BAD and q.get("v2_pass") is not False:
            q["v2_pass"] = False
            q["v2_fail_reason"] = BAD[q["qid"]]
            changed = True
            n += 1
    if changed:
        P.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
print("标废:", n, "题")

# ② 统计影响
for fname in ("题目_续接.json", "题目_自我.json"):
    data = json.loads((Q / fname).read_text(encoding="utf-8"))
    ex = sum(1 for q in data if q.get("v2_pass") is False)
    print(f"  {fname}: {len(data)} 题，排除 {ex}")
    if fname == "题目_续接.json":
        b1 = [q for q in data if q.get("face") == "B1"]
        print(f"    B1 可用 {sum(1 for q in b1 if q.get('v2_pass') is not False)}/{len(b1)}")