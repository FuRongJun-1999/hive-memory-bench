import subprocess, os, time
DSH = r"D:\dsh-home\dsh-0.2.1-rc.2\node_modules\.bin\dsh.cmd"
env = dict(os.environ)
env["PYTHONUTF8"] = "1"
env["DSH_HOME"] = r"D:\dsh-home"
t0 = time.time()
print("=== 冒烟：bench-meow headless ===")
try:
    p = subprocess.run([DSH, "--profile", "bench-meow", "headless", "只回答两个字：收到"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=env, timeout=240, shell=False)
    print("rc:", p.returncode, "| 耗时 %.0fs" % (time.time()-t0))
    print("OUT:", (p.stdout or "")[:1500])
    print("ERR:", (p.stderr or "")[:800])
except subprocess.TimeoutExpired as e:
    print("TIMEOUT %.0fs" % (time.time()-t0))
    print("partial:", str(e.stdout)[:500] if e.stdout else "none")