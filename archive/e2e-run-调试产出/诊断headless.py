import subprocess, os, time
BIN = r"D:\dsh-home\dsh-0.2.1-rc.2\node_modules\@deepseek-ai\dsh\lib\bin.js"
NODE = r"C:\Program Files\nodejs\node.exe"
env = dict(os.environ)
env["PYTHONUTF8"] = "1"
env["DSH_HOME"] = r"D:\dsh-home"

for prof in ("bench-plain", "bench-meow"):
    print("=" * 60)
    print("profile:", prof, "— 跑最短 headless 任务")
    t0 = time.time()
    try:
        p = subprocess.run([NODE, BIN, "--profile", prof, "1+1=?只答数字"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           env=env, timeout=120, shell=False)
        print("  rc:", p.returncode, "| %.0fs" % (time.time()-t0))
        print("  OUT:", (p.stdout or "")[:600].replace(chr(10), " | "))
        e = (p.stderr or "").strip()
        if e: print("  ERR:", e[:600].replace(chr(10), " | "))
    except subprocess.TimeoutExpired as e:
        print("  TIMEOUT 120s")
        po = str(e.stdout or "")[:400]
        pe = str(e.stderr or "")[:400]
        print("  partial OUT:", po.replace(chr(10), " | "))
        print("  partial ERR:", pe.replace(chr(10), " | "))