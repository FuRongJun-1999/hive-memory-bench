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
content = Path(r"D:/1_ai/_hb_lab/r58/e2e/run/归档草稿4.md").read_text(encoding="utf-8")
cg = MdCGSecure(r"D:/program/AEIS/data/mdcg", principal=p, autoflush=1)
got = cg.add("issue_playact_faceD_rebuild_2026_10_27", content, layer="knowledge",
    tags=["第二期测评集", "面D重造", "人设自然化", "在下", "根因确证"],
    importance=0.8, verification_basis="test",
    non_applicable_conditions=[
        "仍为 conditional，未升 counted——45 题只有 10 例冒烟，无整面实跑",
        "子代理实测仅 2 条回复，样本极小",
        "「在下」是否适配所有被测模型未知",
        "出戏盲区依然存在：守 5 特征 ≠ 没出戏",
    ], consistency=False)
print("写入:", got)