import subprocess, os, json, time, threading
from pathlib import Path
BIN = r"D:\dsh-home\dsh-0.2.1-rc.2\node_modules\@deepseek-ai\dsh\lib\bin.js"
NODE = r"C:\Program Files\nodejs\node.exe"
PATCH = r"D:/1_ai/_hb_lab/r58/e2e/run/patch_zhipu.yml"
PROMPT = Path(r"D:/1_ai/_hb_lab/r58/e2e/run/meow_K_prompt.txt").read_text(encoding="utf-8")
cfg = json.loads(Path(r"D:/program/dsh-memory-main/hive/config.local.json").read_text(encoding="utf-8"))
env = dict(os.environ)
env["DSH_HOME"] = r"D:\dsh-home"
env["PYTHONUTF8"] = "1"
env["ZHIPU_API_KEY"] = cfg["HIVE_API_KEY"]

p = subprocess.Popen([NODE, BIN, "--profile", "bench-meow", "--patch", PATCH, "--json", PROMPT],
                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                     encoding="utf-8", errors="replace", env=env, shell=False)
events, texts = [], []
t0 = time.time()
ended = False
def reader():
    global ended
    for ln in p.stdout:
        ln = ln.strip()
        if not ln:
            continue
        events.append(ln)
        try:
            ev = json.loads(ln)
        except Exception:
            continue
        t = ev.get("type")
        if t == "text":
            texts.append(ev.get("text", ""))
        if t in ("turn_end", "done", "end", "final"):
            ended = True
            break
th = threading.Thread(target=reader, daemon=True)
th.start()
while time.time() - t0 < 600 and not ended:
    time.sleep(2)
    if p.poll() is not None:
        break
time.sleep(3)
try:
    p.kill()
except Exception:
    pass
print("耗时 %.0fs | 事件 %d | 文本块 %d | ended=%s" % (time.time()-t0, len(events), len(texts), ended))
out = Path(r"D:/1_ai/_hb_lab/r58/e2e/run/meow_K_raw.jsonl")
out.write_text(chr(10).join(events), encoding="utf-8")
answer = chr(10).join(texts)
Path(r"D:/1_ai/_hb_lab/r58/e2e/run/meow_K_answer.txt").write_text(answer, encoding="utf-8")
print("答案长度:", len(answer))
print("答案前 400:", answer[:400].replace(chr(10), " "))