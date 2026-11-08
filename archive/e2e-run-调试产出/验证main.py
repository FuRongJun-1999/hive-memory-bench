import subprocess
def run(*a):
    p = subprocess.run(list(a), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
    return p.returncode, (p.stdout or "") + (p.stderr or "")
G = ("git", "-C", r"D:/1_ai/_hb_lab/r58")
run(*G, "fetch", "origin", "main")
print("=== main 上的 persona-consistency/ ===")
rc, out = run(*G, "ls-tree", "-r", "--name-only", "origin/main", "persona-consistency/")
files = [f for f in out.strip().split(chr(10)) if f]
print("文件数:", len(files))
for f in files[:22]:
    print(" ", f)
print()
print("=== main README 是否含新章节 ===")
rc, out = run(*G, "show", "origin/main:README.md")
for k in ("人格一致性轨（persona-consistency）v1.0", "三级配对", "11/12"):
    print("  %-40s %s" % (k, "有" if k in out else "无"))