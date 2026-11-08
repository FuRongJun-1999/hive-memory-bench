import sys
sys.path.insert(0, r"D:/program/dsh-memory-main")
from md_cg.tokens import verify_token
from md_cg.mdcos import MdCGSecure
TOK = "mdcg1.record.tk_7fec4e3de27a.Imk7L-ZcsYdsbY7jQbEeSuBZBdvlYpD-XoC6xqCnYng"
p = verify_token(TOK, tenant="default")
cg = MdCGSecure(r"D:/program/AEIS/data/mdcg", principal=p, autoflush=1)
nid = "issue_persona_bench_published_main_2026_10_28"
node = cg.get(nid)
if node is None:
    print("✗ 不存在")
else:
    c = node.content if hasattr(node, "content") else str(node)
    print("✓ 存在 |", len(c), "字")
    for k in ("PR #61", "67d41ec", "MERGED", "20 个文件"):
        print("  %-10s %s" % (k, "有" if k in c else "无"))