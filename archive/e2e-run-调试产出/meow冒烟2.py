import subprocess, os, json, time
from pathlib import Path
BIN = r"D:\dsh-home\dsh-0.2.1-rc.2\node_modules\@deepseek-ai\dsh\lib\bin.js"
NODE = r"C:\Program Files\nodejs\node.exe"
PATCH = r"D:/1_ai/_hb_lab/r58/e2e/run/patch_zhipu.yml"
cfg = json.loads(Path(r"D:/program/dsh-memory-main/hive/config.local.json").read_text(encoding="utf-8"))
env = dict(os.environ)
env["DSH_HOME"] = r"D:\dsh-home"
env["PYTHONUTF8"] = "1"
env["ZHIPU_API_KEY"] = cfg["HIVE_API_KEY"]   # 运行时注入，不落盘
print("ZHIPU_API_KEY 已注入 env（长度", len(env["ZHIPU_API_KEY"]), "）")
t0 = time.time()
print("=== 冒烟：bench-meow + 智谱 patch ===")
try:
    p = subprocess.run([NODE, BIN, "--profile", "bench-meow", "--patch", PATCH, "只回答两个字：收到"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=env, timeout=300, shell=False)
    print("rc:", p.returncode, "| %.0fs" % (time.time()-t0))
    print("OUT:", (p.stdout or "")[:1200])
    e = (p.stderr or "").strip()
    if e: print("ERR:", e[:800])
except subprocess.TimeoutExpired as ex:
    print("TIMEOUT 300s")
    print("partial OUT:", str(ex.stdout or "")[:600])
    print("partial ERR:", str(ex.stderr or "")[:600])