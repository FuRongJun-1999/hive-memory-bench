import subprocess
def run(*a):
    p = subprocess.run(list(a), capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")
G = ("git", "-C", r"D:/1_ai/_hb_lab/r58")
run(*G, "add", "e2e")
rc, out = run(*G, "commit", "-m", "docs(e2e): 第二期清单人格一致性实测尝试——10项目9未接入、headless阻塞取证、非盲对照不可用（灵枢12/12但6维作废）")
print("commit:", rc, out[-150:])
print(run(*G, "push")[1][-100:])