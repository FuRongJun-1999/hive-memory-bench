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
content = Path(r"D:/1_ai/_hb_lab/r58/e2e/run/归档草稿.md").read_text(encoding="utf-8")
cg = MdCGSecure(r"D:/program/AEIS/data/mdcg", principal=p, autoflush=1)
got = cg.add("issue_playact_first_run_62_5_2026_10_27", content, layer="knowledge",
    tags=["第二期测评集", "首次实跑", "判据假阴性", "26.5pp", "面H字段bug", "清理事故"],
    importance=0.85, verification_basis="test",
    non_applicable_conditions=[
        "24 题单模型单次采样，不能当能力读数",
        "无其他插件数据，不能横比",
        "面 D 的 0/3 不能算能力弱（人设不自然）",
        "面 B1 的 0/3 不足以说明 B1 弱",
        "判据修完后仍需补诚实样本 PASS 方向的系统验证",
    ], consistency=False)
print("写入:", got)