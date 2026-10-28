import subprocess, os
DSH = r"D:\dsh-home\dsh-0.2.1-rc.2\node_modules\.bin\dsh.cmd"
base = dict(os.environ)
base["PYTHONUTF8"] = "1"
cands = [("不设 DSH_HOME", None), ("D:\\dsh-home", r"D:\dsh-home"), ("~/.dsh", os.path.expanduser("~/.dsh"))]
for name, home in cands:
    env = dict(base)
    if home is None:
        env.pop("DSH_HOME", None)
    else:
        env["DSH_HOME"] = home
    print("=" * 50)
    print("尝试:", name)
    try:
        p = subprocess.run([DSH, "--profile", "lingshu-qq", "--dump-config"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           env=env, timeout=120, shell=False)
        o = (p.stdout or "")[:300]
        e = (p.stderr or "")[:200]
        print("  rc:", p.returncode)
        if o: print("  out:", o.replace(chr(10), " ")[:200])
        if e: print("  err:", e.replace(chr(10), " ")[:160])
    except Exception as ex:
        print("  异常:", str(ex)[:120])