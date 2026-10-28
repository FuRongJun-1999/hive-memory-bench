import subprocess, os, sys, time
DSH = r"D:\dsh-home\dsh-0.2.1-rc.2\node_modules\.bin\dsh.cmd"
env = dict(os.environ)
env["PYTHONUTF8"] = "1"
env.pop("DSH_HOME", None)
t0 = time.time()
try:
    p = subprocess.run([DSH, "--profile", "lingshu-test", "headless", "说一句「测试通过」然后退出，不要调用工具。"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=env, timeout=180, shell=False)
    print("rc:", p.returncode, "| 耗时 %.0fs" % (time.time() - t0))
    print("OUT:", (p.stdout or "")[:1200])
    print("ERR:", (p.stderr or "")[:600])
except subprocess.TimeoutExpired as e:
    print("TIMEOUT %.0fs" % (time.time() - t0))
    print("partial OUT:", (e.stdout or b"")[:500] if e.stdout else "none")
    print("partial ERR:", (e.stderr or b"")[:500] if e.stderr else "none")