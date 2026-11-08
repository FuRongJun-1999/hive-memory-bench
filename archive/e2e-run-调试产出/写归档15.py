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
content = Path(r"D:/1_ai/_hb_lab/r58/e2e/run/归档草稿15.md").read_text(encoding="utf-8")
cg = MdCGSecure(r"D:/program/AEIS/data/mdcg", principal=p, autoflush=1)
got = cg.add("issue_mcq150_review_merge_2026_11_06", content, layer="knowledge",
    tags=["选择题题库", "150题", "判分环节零噪声", "语料可核47%", "单跳多跳", "PR64"],
    importance=0.88, verification_basis="test",
    non_applicable_conditions=[
        "全部单跳不覆盖因果链",
        "只测认出测不了复述(19% vs 83%)",
        "秦吏39+毛选41共80题因版权不可核",
        "干扰项语义近似无法机械判定只能LLM盲审",
        "全部单次运行无重复实验无显著性检验",
    ], consistency=False)
print("写入:", got)