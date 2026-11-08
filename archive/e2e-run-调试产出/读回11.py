# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, r"D:/program/dsh-memory-main")
from md_cg.tokens import verify_token
from md_cg.mdcos import MdCGSecure
TOK = "mdcg1.record.tk_7fec4e3de27a.Imk7L-ZcsYdsbY7jQbEeSuBZBdvlYpD-XoC6xqCnYng"
p = verify_token(TOK, tenant="default")
cg = MdCGSecure(r"D:/program/AEIS/data/mdcg", principal=p, autoflush=1)
nid = "issue_persona_consistency_bench_public_2026_10_28"
node = cg.get(nid)
if node is None:
    print("✗ 节点不存在")
else:
    c = node.content if hasattr(node, "content") else str(node)
    print("✓ 节点存在 | 内容长度:", len(c))
    print("  含关键词检验:")
    for k in ("470", "13 面", "persona-consistency-bench", "9d76418", "未开 PR"):
        print("    %-24s %s" % (k, "有" if k in c else "无"))