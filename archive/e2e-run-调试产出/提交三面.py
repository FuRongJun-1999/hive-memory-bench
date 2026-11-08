import subprocess
def run(*a):
    p = subprocess.run(list(a), capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")
G = ("git", "-C", r"D:/1_ai/_hb_lab/r58")
run(*G, "add", "e2e")
rc, out = run(*G, "commit", "-m", "feat(e2e): 补 I时间锚11/G声线辨识20/EMO情绪极性10 三面；判据升 v1.4；双单元四处整改")
print("commit:", rc, out[-160:])
print(run(*G, "push")[1][-100:])