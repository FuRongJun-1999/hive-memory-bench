import subprocess
def run(*a):
    p = subprocess.run(list(a), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
    return p.returncode, (p.stdout or "") + (p.stderr or "")
G = ("git", "-C", r"D:/1_ai/_hb_lab/r58")
print("=== 调 git 配置 ===")
for k, v in [("http.postBuffer", "524288000"), ("http.lowSpeedLimit", "0"), ("http.lowSpeedTime", "600"),
             ("http.version", "HTTP/1.1")]:
    rc, out = run(*G, "config", k, v)
    print(" ", k, "=", v, "| rc", rc)
print()
print("=== 重试 push ===")
rc, out = run(*G, "push", "-u", "origin", "feat/persona-consistency-bench")
print("rc:", rc)
print(out[-800:])