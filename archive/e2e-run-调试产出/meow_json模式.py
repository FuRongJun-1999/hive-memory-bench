import subprocess, os, json, time, threading
from pathlib import Path
BIN = r"D:\dsh-home\dsh-0.2.1-rc.2\node_modules\@deepseek-ai\dsh\lib\bin.js"
NODE = r"C:\Program Files\nodejs\node.exe"
PATCH = r"D:/1_ai/_hb_lab/r58/e2e/run/patch_zhipu.yml"
cfg = json.loads(Path(r"D:/program/dsh-memory-main/hive/config.local.json").read_text(encoding="utf-8"))
env = dict(os.environ)
env["DSH_HOME"] = r"D:\dsh-home"
env["PYTHONUTF8"] = "1"
env["ZHIPU_API_KEY"] = cfg["HIVE_API_KEY"]

p = subprocess.Popen([NODE, BIN, "--profile", "bench-meow", "--patch", PATCH, "--json", "只回答两个字：收到"],
                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                     encoding="utf-8", errors="replace", env=env, shell=False)
lines = []
t0 = time.time()
got_final = False
def reader():
    global got_final
    for ln in p.stdout:
        lines.append(ln.rstrip())
        # 判断是否已出最终答案
        if any(k in ln for k in ("\"final\"", "\"done\"", "\"end\"", "收到")):
            got_final = True
            break
th = threading.Thread(target=reader, daemon=True)
th.start()

# 最多等 180s，一旦 got_final 再等 2s 就杀
while time.time() - t0 < 180 and not got_final:
    time.sleep(1)
time.sleep(2)
try:
    p.kill()
except Exception:
    pass
print("耗时 %.0fs | 收到行数: %d | got_final: %s" % (time.time()-t0, len(lines), got_final))
print()
print("=== 事件流（前 25 行）===")
for ln in lines[:25]:
    print(ln[:200])