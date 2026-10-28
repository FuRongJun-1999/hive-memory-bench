import subprocess
def run(*a):
    p = subprocess.run(list(a), capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")
G = ("git", "-C", r"D:/1_ai/_hb_lab/r58")
run(*G, "add", "e2e")
rc, out = run(*G, "commit", "-m", "feat(e2e): 新增覆盖声明.json；D 面整面实跑 40/45=88.9%（单特征 100% 无区分度）→ 升 counted；A级可横比 198 题")
print("commit:", rc, out[-180:])
print(run(*G, "push")[1][-110:])