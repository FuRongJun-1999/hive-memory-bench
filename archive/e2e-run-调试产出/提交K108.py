import subprocess
def run(*a):
    p = subprocess.run(list(a), capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")
G = ("git", "-C", r"D:/1_ai/_hb_lab/r58")
run(*G, "add", "e2e")
rc, out = run(*G, "commit", "-m", "feat(e2e): 面K扩到108题（12维x9）——T1 11/12, T2 12/12, T3 12/12, 三级全过11/12；K02单维假设不成立为真实发现；修浮点判据bug")
print("commit:", rc, out[-150:])
print(run(*G, "push")[1][-100:])