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
content = Path(r"D:/1_ai/_hb_lab/r58/e2e/run/归档草稿6.md").read_text(encoding="utf-8")
cg = MdCGSecure(r"D:/program/AEIS/data/mdcg", principal=p, autoflush=1)
got = cg.add("issue_playact_IGEMO_faces_2026_10_27", content, layer="knowledge",
    tags=["第二期测评集", "I时间锚", "G扮演保真度", "情感三式", "判据v1.4", "三面补齐"],
    importance=0.85, verification_basis="test",
    non_applicable_conditions=[
        "I 面可能仍是文本顺序比较",
        "G 面未做表面特征控制，须报相对 50% 基线的增益",
        "EMO 只测情绪正负二分类，不测角色一致性",
        "式2/式3 未做",
        "三面判据只冒烟 3-5 例",
        "三面均未实跑",
    ], consistency=False)
print("写入:", got)