import subprocess, os, time
BIN = r"D:\dsh-home\dsh-0.2.1-rc.2\node_modules\@deepseek-ai\dsh\lib\bin.js"
NODE = r"C:\Program Files\nodejs\node.exe"
env = dict(os.environ)
env["PYTHONUTF8"] = "1"
env["DSH_HOME"] = r"D:\dsh-home"
print("node 存在:", os.path.exists(NODE), "| bin.js:", os.path.exists(BIN))
print()
print("=== 直调 node：--help（要挂载 app）===")
t0 = time.time()
try:
    p = subprocess.run([NODE, BIN, "--profile", "bench-meow", "--help"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=env, timeout=45, shell=False)
    print("rc:", p.returncode, "| %.0fs" % (time.time()-t0))
    print("OUT:", (p.stdout or "")[:800])
    print("ERR:", (p.stderr or "")[:1200])
except subprocess.TimeoutExpired as e:
    print("TIMEOUT 45s")
    print("partial OUT:", str(e.stdout)[:600] if e.stdout else "none")
    print("partial ERR:", str(e.stderr)[:800] if e.stderr else "none")