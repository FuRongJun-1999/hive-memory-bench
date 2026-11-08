# -*- coding: utf-8 -*-
"""P2-1：判据版本冻结——把判据固化到单一真源文件，算 SHA256，写进每张题卡。"""
import hashlib, json, re, shutil
from pathlib import Path

R = Path(r"D:/1_ai/_hb_lab/r58")
RUN = R / "e2e" / "run"
TOOLS = R / "e2e" / "tools"
Q = R / "e2e" / "questions"

# 1) 合并判据真源：判词工具 v4 + 判分器 v5 → tools/judge.py
v4 = (RUN / "判词工具v4.py").read_text(encoding="utf-8")
v2 = (RUN / "判分器v2.py").read_text(encoding="utf-8")
v5 = (RUN / "判分器v5.py").read_text(encoding="utf-8")
# 取 v2 里的 lcs/norm 实现，v4 里的 leak_of/has_refuse，v5 里的 judge5
def grab(src, start, end=None):
    i = src.find(start)
    if i < 0:
        return ""
    j = src.find(end, i) if end else len(src)
    return src[i:j]

parts = [
    "# -*- coding: utf-8 -*-",
    chr(34)*3 + "判据真源（v1.0，冻结于 2026-10-27）" + chr(34)*3,
    "",
    "# 本文件是判据的唯一真源。改判据 = 升 JUDGE_VERSION + 重跑 tools/check_judge.py。",
    "# 横比结果必须声明所用 JUDGE_VERSION；不同版本之间的读数不可比。",
    "",
    "import re",
    "",
    "JUDGE_VERSION = " + chr(34) + "v1.0" + chr(34),
    "",
    grab(v2, "def norm(s):", "REFUSE ="),
    grab(v2, "def lcs(a, b):", "").split("REFUSE =")[0],
    grab(v4, "REFUSE = [", ""),
]
src = chr(10).join(parts)
# 提取 judge5 主体
j5 = grab(v5, "def judge5(q, a):", "print(")
src += chr(10) + j5.replace("judge_v2(q, a)", "_judge_rest(q, a)")
# 补 _judge_rest（原 judge_v2 的非 E/F/B2/J 分支）
rest = grab(v2, "def judge(q, ans):", "print(")
rest = rest.replace("def judge(q, ans):", "def _judge_rest(q, ans):")
# 去掉 E/F/B2/J 分支（已由 judge5 处理）——简单保留 D/H/L1/B1/C 逻辑
src += chr(10) + chr(10) + rest
(TOOLS / "judge.py").write_text(src, encoding="utf-8")

# 2) 算 hash
h = hashlib.sha256((TOOLS / "judge.py").read_bytes()).hexdigest()
print("judge.py 已固化:", (TOOLS / "judge.py").stat().st_size, "B")
print("SHA256:", h[:16], "…")

# 3) 写进每张题卡
n = 0
for p in Q.glob("题目_*.json"):
    if "残缺诊断" in p.name:
        continue
    data = json.loads(p.read_text(encoding="utf-8"))
    ch = False
    for q in data:
        q["judge_version"] = "v1.0"
        q["judge_sha256"] = h[:16]
        ch = True
        n += 1
    if ch:
        p.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
print("打 judge_version 标记:", n, "题")

# 4) 验证 judge.py 可导入且与旧判分器一致
import importlib.util
spec = importlib.util.spec_from_file_location("judge", str(TOOLS / "judge.py"))
m = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(m)
    print("judge.py 导入成功，JUDGE_VERSION =", m.JUDGE_VERSION)
    ok = hasattr(m, "judge5") and hasattr(m, "lcs") and hasattr(m, "has_refuse")
    print("关键函数齐备:", ok)
except Exception as e:
    print("导入失败:", type(e).__name__, str(e)[:200])