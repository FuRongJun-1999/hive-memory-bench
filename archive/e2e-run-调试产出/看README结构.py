import subprocess, re
def run(*a):
    p = subprocess.run(list(a), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    return p.returncode, (p.stdout or "") + (p.stderr or "")
G = ("git", "-C", r"D:/1_ai/_hb_lab/r58")
rc, out = run(*G, "show", "HEAD:README.md")
lines = out.split(chr(10))
print("README 总行数:", len(lines))
print()
print("=== 章节结构 ===")
for i, ln in enumerate(lines, 1):
    if ln.startswith("#"):
        print("%4d  %s" % (i, ln[:70]))
print()
print("=== 尾部 15 行 ===")
for ln in lines[-15:]:
    print(ln[:90])