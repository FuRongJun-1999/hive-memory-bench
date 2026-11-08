import subprocess, os
def run(*a, cwd=None):
    p = subprocess.run(list(a), capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=cwd)
    return p.returncode, (p.stdout or "") + (p.stderr or "")
G = ("git", "-C", r"D:/1_ai/_hb_lab/r58")
print(run(*G, "checkout", "-b", "feat/persona-consistency-bench")[1][-200:])
run(*G, "add", "persona-consistency")
rc, out = run(*G, "commit", "-m", "feat: 人格一致性公开测评集 v1.0 —— 470题/13面，核心为K面108题三级配对信度检验")
print("commit rc:", rc)
print(out[-300:])
rc2, out2 = run(*G, "push", "-u", "origin", "feat/persona-consistency-bench")
print("push:", rc2, out2[-300:])