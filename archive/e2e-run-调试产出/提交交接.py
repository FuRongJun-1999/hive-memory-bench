import subprocess
def run(*a):
    p = subprocess.run(list(a), capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")
G = ("git", "-C", r"D:/1_ai/_hb_lab/r58")
run(*G, "add", "docs", "e2e")
rc, out = run(*G, "commit", "-m", "docs: 第二期测评集交接文档 v1.0（470题/13面/判据v1.4；含6条已知假读数与P0-P4优先级；自检36/36）")
print("commit:", rc, out[-150:])
print(run(*G, "push")[1][-100:])