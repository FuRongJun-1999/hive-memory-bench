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
content = Path(r"D:/1_ai/_hb_lab/r58/e2e/run/归档草稿11.md").read_text(encoding="utf-8")
cg = MdCGSecure(r"D:/program/AEIS/data/mdcg", principal=p, autoflush=1)
got = cg.add("issue_persona_consistency_bench_public_2026_10_28", content, layer="knowledge",
    tags=["公开测评集", "人格一致性", "470题13面", "hive-memory-bench", "脱敏", "分支feat-persona-consistency-bench"],
    importance=0.9, verification_basis="test",
    non_applicable_conditions=[
        "未开 PR，只在分支上，main 尚不可见",
        "未在公开仓跑过 CI/门禁",
        "授权依据为用户口述与配套数据集 README，未做法务审查",
        "所有读数仍为单模型单次采样",
    ], consistency=False)
print("写入:", got)