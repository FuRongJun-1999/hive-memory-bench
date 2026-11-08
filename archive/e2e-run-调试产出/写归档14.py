# -*- coding: utf-8 -*-
import os, sys
from pathlib import Path
os.environ["MDCG_WRITE_GATE"] = "enforce"
os.environ["MDCG_REVIEW_CHANNELS"] = "hive,subagent"
os.environ["MDCG_REVIEWERS"] = "reflect,verify"
os.environ["MDCG_REVIEW_DUAL_CHECK"] = "1"
sys.path.insert(0, r"D:/program/dsh-memory-main")
from md_cg.tokens import verify_token
from md_cg.mdcos import MdCGSecure
TOK = "mdcg1.record.tk_7fec4e3de27a.Imk7L-ZcsYdsbY7jQbEeSuBZBdvlYpD-XoC6xqCnYng"
p = verify_token(TOK, tenant="default")
content = Path(r"D:/1_ai/_hb_lab/r58/e2e/run/归档草稿14.md").read_text(encoding="utf-8")
cg = MdCGSecure(r"D:/program/AEIS/data/mdcg", principal=p, autoflush=1)
got = cg.add("issue_Kv2_protocol_v1_baseline95_2026_10_30", content, layer="knowledge",
    tags=["K面", "作业规程", "跨会话", "打乱题序", "反向诱导", "复制检测", "基准95%"],
    importance=0.9, verification_basis="test",
    non_applicable_conditions=[
        "基准 C 只跑一次，95% 有抽样波动未重复测量",
        "只用一个模型 deepseek-flash",
        "反向诱导 7 条未覆盖 K12-K20",
        "打乱 seed 固定未换 seed 验证",
        "逐题相同率 50-65% 正常区间只有两个点推论",
        "九家读数未记录作业方式不可与本基准并列",
    ], consistency=False)
print("写入:", got)