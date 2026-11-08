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
content = Path(r"D:/1_ai/_hb_lab/r58/e2e/run/归档草稿13.md").read_text(encoding="utf-8")
cg = MdCGSecure(r"D:/program/AEIS/data/mdcg", principal=p, autoflush=1)
got = cg.add("issue_lingshu_Kv2_selftest_polluted_2026_10_30", content, layer="knowledge",
    tags=["灵枢", "K_v2复测", "逐维原始分数", "非盲污染", "headless不可用", "DSH profile瓶颈"],
    importance=0.85, verification_basis="test",
    non_applicable_conditions=[
        "数据被污染不可当真实读数——答卷者非盲，见过判据",
        "100% 与真盲测 84.2% 相差 15.8pp，差值即污染量级",
        "不能与其他系统横比，口径不同",
        "DSH headless + 灵枢插件跑不动长输出（四条实测证据）",
        "单次单模型无重复测量",
    ], consistency=False)
print("写入:", got)