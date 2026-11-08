import subprocess, os, sys
DSH = r"D:\dsh-home\dsh-0.2.1-rc.2\node_modules\.bin\dsh.cmd"
env = dict(os.environ)
env["PYTHONUTF8"] = "1"
env.pop("DSH_HOME", None)
prompt = "用一句话自我介绍，然后退出。不要调用任何工具。"
try:
    p = subprocess.run([DSH, "--profile", "lingshu-qq", "headless", prompt],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=env, timeout=150, shell=False)
    print("rc:", p.returncode)
    print("OUT:", (p.stdout or "")[:1500])
    print("ERR:", (p.stderr or "")[:800])
except subprocess.TimeoutExpired as e:
    print("TIMEOUT after 150s")
    print("partial OUT:", str(e.stdout)[:600] if e.stdout else "none")
    print("partial ERR:", str(e.stderr)[:600] if e.stderr else "none")