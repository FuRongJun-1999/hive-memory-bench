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
content = Path(r"D:/1_ai/_hb_lab/r58/e2e/run/归档草稿8.md").read_text(encoding="utf-8")
cg = MdCGSecure(r"D:/program/AEIS/data/mdcg", principal=p, autoflush=1)
got = cg.add("issue_playact_faceK_108_2026_10_27", content, layer="knowledge",
    tags=["第二期测评集", "一致性探针108题", "12维度", "单维量表局限", "浮点容差", "重测信度"],
    importance=0.85, verification_basis="test",
    non_applicable_conditions=[
        "只测信度不测效度",
        "12维仍覆盖不全，题目自拟非公开量表",
        "K02 暴露单维量表根本局限（两样并存的人格结构测不出）",
        "单次单模型实跑，不能当能力结论",
        "T2 全过靠注入文本排除注入无效解释，非硬证据",
    ], consistency=False)
print("写入:", got)