import subprocess
def run(*a):
    p = subprocess.run(list(a), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    return p.returncode, (p.stdout or "") + (p.stderr or "")
G = ("git", "-C", r"D:/1_ai/_hb_lab/r58")
print("=== 当前分支 ===")
print(run(*G, "branch", "--show-current")[1].strip())
print()
print("=== 根目录 README ===")
rc, out = run(*G, "ls-tree", "HEAD", "--name-only")
print(out.strip()[:600])
print()
print("=== main 分支的 README（前 40 行）===")
rc, out = run(*G, "show", "origin/main:README.md")
if rc == 0:
    print(out[:2000])
else:
    print("无:", out[:200])