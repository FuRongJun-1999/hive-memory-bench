import subprocess
def run(*a):
    p = subprocess.run(list(a), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
    return p.returncode, (p.stdout or "") + (p.stderr or "")
G = ("git", "-C", r"D:/1_ai/_hb_lab/r58")
print("=== 远端分支确认 ===")
rc, out = run(*G, "ls-remote", "--heads", "origin", "feat/persona-consistency-bench")
print(out.strip())
print()
print("=== 本地文件清单 ===")
rc, out = run(*G, "ls-tree", "-r", "--name-only", "HEAD", "persona-consistency/")
files = [f for f in out.strip().split(chr(10)) if f]
print("文件数:", len(files))
for f in files:
    print(" ", f)
print()
print("=== 与远端对比（是否已同步）===")
rc, out = run(*G, "diff", "--stat", "HEAD", "origin/feat/persona-consistency-bench")
print(out.strip() if out.strip() else "无差异 → 已同步")