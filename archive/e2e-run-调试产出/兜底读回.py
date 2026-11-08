# -*- coding: utf-8 -*-
import sys, os
from pathlib import Path
sys.path.insert(0, r"D:/program/dsh-memory-main")
from md_cg.tokens import verify_token
from md_cg.mdcos import MdCGSecure
TOK = "mdcg1.record.tk_7fec4e3de27a.Imk7L-ZcsYdsbY7jQbEeSuBZBdvlYpD-XoC6xqCnYng"
p = verify_token(TOK, tenant="default")
cg = MdCGSecure(r"D:/program/AEIS/data/mdcg", principal=p, autoflush=1)

nid = "issue_2nd_phase_handover_doc_2026_10_28"
print("=== 按 node_id 直接读 ===")
try:
    node = cg.get(nid)
    if node is None:
        print("  返回 None → 节点不存在")
    else:
        c = node.content if hasattr(node, "content") else str(node)
        print("  存在，内容长度:", len(c))
        print("  前 200 字:", c[:200].replace(chr(10), " "))
except Exception as e:
    print("  异常:", type(e).__name__, str(e)[:200])

print()
print("=== 按文件路径确认归档草稿 ===")
f = Path(r"D:/1_ai/_hb_lab/r58/e2e/run/归档草稿10.md")
print("  草稿存在:", f.exists(), "| 大小:", f.stat().st_size if f.exists() else 0)