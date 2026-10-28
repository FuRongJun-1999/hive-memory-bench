import subprocess
def run(*a):
    p = subprocess.run(list(a), capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")
G = ("git", "-C", r"D:/1_ai/_hb_lab/r58")
run(*G, "add", "e2e")
rc, out = run(*G, "commit", "-m", "feat(e2e): P2-4 面D重造——人设改自然自称「在下」（子代理实测3种候选均可守住），45题判据冒烟10/10，待实跑复验")
print("commit:", rc, out[-170:])
print(run(*G, "push")[1][-110:])