import subprocess
def run(*a):
    p = subprocess.run(list(a), capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")
G = ("git", "-C", r"D:/1_ai/_hb_lab/r58")
run(*G, "add", "e2e")
rc, out = run(*G, "commit", "-m", "feat(e2e): 新增面K一致性探针36题——恋爱契合度/性格测验式重测信度（T1 6/6, T2 6/6, T3 5/6）")
print("commit:", rc, out[-150:])
print(run(*G, "push")[1][-100:])