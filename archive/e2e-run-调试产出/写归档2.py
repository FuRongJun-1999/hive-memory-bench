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
content = Path(r"D:/1_ai/_hb_lab/r58/e2e/run/归档草稿2.md").read_text(encoding="utf-8")
cg = MdCGSecure(r"D:/program/AEIS/data/mdcg", principal=p, autoflush=1)
got = cg.add("issue_playact_judge_tiers_2026_10_27", content, layer="knowledge",
    tags=["第二期测评集", "判据分级", "正反例门禁", "九面降级", "假阴性", "双单元复核题库"],
    importance=0.85, verification_basis="test",
    non_applicable_conditions=[
        "正反例每面只 1 组，不足以为每道题背书",
        "B1/C 的 literal-only 不是 bug 是设计选择",
        "J 面非机械判，本轮只诚实标注未解决",
        "分级依据仅 18 个手写样本，不足以估真实假阴率",
        "I/G/情感三面仍无题，未执行「不计总分」",
    ], consistency=False)
print("写入:", got)