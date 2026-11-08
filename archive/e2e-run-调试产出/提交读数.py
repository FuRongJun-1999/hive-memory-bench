import subprocess
def run(*a):
    p = subprocess.run(list(a), capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")
G = ("git", "-C", r"D:/1_ai/_hb_lab/r58")
run(*G, "add", "e2e")
rc, out = run(*G, "commit", "-m", "docs(e2e): 按四层口径首次完整报读数（ability 47/52=90.4%、control L1 100%、diagnostic H 100%），证明口径可执行")
print("commit:", rc, out[-160:])
print(run(*G, "push")[1][-100:])