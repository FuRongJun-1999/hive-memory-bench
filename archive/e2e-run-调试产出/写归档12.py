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
content = Path(r"D:/1_ai/_hb_lab/r58/e2e/run/归档草稿12.md").read_text(encoding="utf-8")
cg = MdCGSecure(r"D:/program/AEIS/data/mdcg", principal=p, autoflush=1)
got = cg.add("issue_persona_bench_published_main_2026_10_28", content, layer="knowledge",
    tags=["公开测评集", "PR61合并", "人格一致性", "正式发布", "main分支"],
    importance=0.9, verification_basis="test",
    non_applicable_conditions=[
        "公开包内 check_all.py 未在公开包语境复测",
        "授权依据为用户口述与配套数据集README，未做法务审查",
        "主README的仓库结构与怎么用两节未同步加条目",
        "所有读数为单模型单次采样",
    ], consistency=False)
print("写入:", got)