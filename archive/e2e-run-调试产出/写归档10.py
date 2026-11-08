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
content = Path(r"D:/1_ai/_hb_lab/r58/e2e/run/归档草稿10.md").read_text(encoding="utf-8")
cg = MdCGSecure(r"D:/program/AEIS/data/mdcg", principal=p, autoflush=1)
got = cg.add("issue_2nd_phase_handover_doc_2026_10_28", content, layer="knowledge",
    tags=["第二期测评集", "交接文档", "470题", "判据v1.4", "已知假读数", "自检36/36"],
    importance=0.9, verification_basis="test",
    non_applicable_conditions=[
        "所有读数为单模型单次采样，不能当能力结论",
        "无第三方插件被实测（9个未接入+headless阻塞）",
        "K面之外的12面大部分没实跑过",
        "判据每面仅1组正反例",
        "文档有效期取决于仓库状态，接手方须先跑四项确认",
    ], consistency=False)
print("写入:", got)