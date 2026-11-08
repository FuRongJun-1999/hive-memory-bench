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
content = Path(r"D:/1_ai/_hb_lab/r58/e2e/run/归档草稿3.md").read_text(encoding="utf-8")
cg = MdCGSecure(r"D:/program/AEIS/data/mdcg", principal=p, autoflush=1)
got = cg.add("issue_playact_P1P2_judge_freeze_2026_10_27", content, layer="knowledge",
    tags=["第二期测评集", "P1题卡清洗", "P2判据冻结", "横比口径", "C面重建", "同源降权"],
    importance=0.85, verification_basis="test",
    non_applicable_conditions=[
        "156 是名义题数不是独立样本数",
        "A 级可横比仅 153 题，且 C 只测检索、L1 偏易",
        "面 D 45 题仍 conditional（人设未重造）",
        "J 面仍不可机械判",
        "空缺面 I/G/情感仍未处置",
        "独立簇用 source_card 粗代，非真正语义独立性分析",
    ], consistency=False)
print("写入:", got)