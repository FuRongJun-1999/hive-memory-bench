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
content = Path(r"D:/1_ai/_hb_lab/r58/e2e/run/归档草稿9.md").read_text(encoding="utf-8")
cg = MdCGSecure(r"D:/program/AEIS/data/mdcg", principal=p, autoflush=1)
got = cg.add("issue_2nd_phase_consistency_attempt_2026_10_28", content, layer="knowledge",
    tags=["第二期清单", "人格一致性", "headless阻塞", "非盲对照", "作废机制", "实测失败"],
    importance=0.85, verification_basis="test",
    non_applicable_conditions=[
        "非盲——同会话见过判据与对照读数，答卷不是测试",
        "有效维度仅 6 vs 5，样本量不足",
        "9 个项目未接入，无第三方插件被实测",
        "面 K 的 T2 是同会话内注入，不是跨会话记忆",
        "结论只能是探针可跑通 + 作废机制有效，不能是灵枢更强",
    ], consistency=False)
print("写入:", got)