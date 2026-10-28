# -*- coding: utf-8 -*-
"""判据升版 v1.0 → v1.1（H 判据 all→any），同步所有题卡。"""
import hashlib, importlib.util, json, re
from pathlib import Path
R = Path(r"D:/1_ai/_hb_lab/r58")
T = R / "e2e" / "tools" / "judge.py"
Q = R / "e2e" / "questions"

src = T.read_text(encoding="utf-8")
src = src.replace('JUDGE_VERSION = "v1.0"', 'JUDGE_VERSION = "v1.1"')
# 在文件头加变更记录
note = "# v1.1（2026-10-27）：H 判据 must_contain_any 由「所有组全中」改为「任一组命中」（旧版过严）"
if "v1.1（2026-10-27）" not in src:
    lines = src.split(chr(10))
    lines.insert(2, note)
    src = chr(10).join(lines)
T.write_text(src, encoding="utf-8")
h = hashlib.sha256(T.read_bytes()).hexdigest()
print("新版本: v1.1 | SHA256:", h[:16])

n = 0
for p in Q.glob("题目_*.json"):
    if "残缺诊断" in p.name:
        continue
    data = json.loads(p.read_text(encoding="utf-8"))
    for q in data:
        q["judge_version"] = "v1.1"
        q["judge_sha256"] = h[:16]
        n += 1
    p.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
print("同步题卡:", n)

# 验证导入
spec = importlib.util.spec_from_file_location("judge", str(T))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
print("导入 OK，JUDGE_VERSION =", m.JUDGE_VERSION)

# 写判据变更记录
LOG = R / "e2e" / "tools" / "judge_CHANGELOG.md"
LOG.write_text(chr(10).join([
  "# 判据变更记录",
  "",
  "> 规则：**改判据 = 升版本 + 重跑 check_judge.py + 更新所有题卡的 judge_version/judge_sha256**。",
  "> 不同版本之间的读数**不可比**。",
  "",
  "| 版本 | 日期 | SHA256(16) | 改动 | 依据 |",
  "|---|---|---|---|---|",
  "| v1.0 | 2026-10-27 | 570d6ea775d9545e | 初版：合并判词工具 v4 + 判分器 v5 | 双单元 P0 要求「判据版本冻结」 |",
  "| v1.1 | 2026-10-27 | " + h[:16] + " | H 判据 must_contain_any：所有组全中 → 任一组命中 | 冒烟发现「白墙蓝顶的房子」被误判 FAIL（过严） |",
  "",
  "## 为什么必须冻结",
  "",
  "同一份作答，判据改三次，读数 36.0% → 52.0% → 58.3% → 62.5%。**判据版本主导读数达 26.5 个百分点**，",
  "不冻结则任何跨插件比较都无意义。",
].join(chr(10)), encoding="utf-8")
print("变更记录已写:", LOG.name)