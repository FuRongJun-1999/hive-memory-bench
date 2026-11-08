import subprocess
def run(*a):
    p = subprocess.run(list(a), capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")
G = ("git", "-C", r"D:/1_ai/_hb_lab/r58")
rc, out = run(*G, "add", "e2e")
print("add:", rc)
rc, out = run(*G, "commit", "-m", "test(e2e): 灵枢首次实跑 25 题——15/24=62.5%；查出判据假阴性 26.5pp（同一答卷判据改三次 36%→62.5%）")
print("commit:", rc, out[-200:])
print(run(*G, "push")[1][-120:])