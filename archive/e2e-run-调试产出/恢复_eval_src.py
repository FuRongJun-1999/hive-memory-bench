# -*- coding: utf-8 -*-
"""恢复被误移的 _eval_src（r58 worktree 的主仓库）。"""
import shutil
from pathlib import Path

R = Path(r"D:/1_ai")
ARC = R / "_临时归档" / "2026-10-工作区整理" / "顶层清理" / "临时目录"

src = ARC / "_eval_src"
dst = R / "_eval_src"
print("归档里存在:", src.exists(), "| 原位置存在:", dst.exists())
if src.exists() and not dst.exists():
    shutil.move(str(src), str(dst))
    print("已移回:", dst)
else:
    print("无需移动")

# 检查还有哪些 worktree 依赖
print()
print("=== 检查 worktree 依赖 ===")
import subprocess
for wt in sorted((R / "_hb_lab").glob("*")):
    gitp = wt / ".git"
    if gitp.is_file():
        txt = gitp.read_text(encoding="utf-8", errors="replace").strip()
        target = txt.replace("gitdir:", "").strip()
        # 取主仓库根（去掉 /.git/worktrees/...）
        main = target.split("/.git/")[0] if "/.git/" in target else target
        print(f"  {wt.name}: 主仓库 {main} | 存在 {Path(main).exists()}")