import subprocess
def run(*a):
    p = subprocess.run(list(a), capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")
G = ("git", "-C", r"D:/1_ai/_hb_lab/r58")
run(*G, "rm", "-r", "--cached", "persona-consistency", "--quiet")
run(*G, "add", "persona-consistency")
rc, out = run(*G, "commit", "-m", "feat: 人格一致性公开测评集 v1.0（清理重复文件与 pycache，压缩体积）")
print("commit:", rc, out[-250:])
rc2, out2 = run(*G, "push", "-u", "origin", "feat/persona-consistency-bench")
print("push:", rc2)
print(out2[-400:])