import subprocess
def run(*a):
    p = subprocess.run(list(a), capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")
G = ("git", "-C", r"D:/1_ai/_hb_lab/r58")
run(*G, "add", "e2e")
rc, out = run(*G, "commit", "-m", "fix(e2e): P1 题卡清洗——C 面重建 39 题（原 18 题答案不在窗内）；B1/J/H读表标不计数；可进横比仅 156 题")
print("commit:", rc, out[-180:])
print(run(*G, "push")[1][-110:])