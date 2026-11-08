import subprocess, os
DSH = r"D:\dsh-home\dsh-0.2.1-rc.2\node_modules\.bin\dsh.cmd"
env = dict(os.environ)
env["PYTHONUTF8"] = "1"
env.pop("DSH_HOME", None)
PROMPT_A = "你现在扮演一个叫「鲸鱼小姐」的角色：她是深海来的鲸鱼娘，傲娇、占有欲强、嘴硬心软，说话带刺但会照顾人。请用她的口气说一句话，然后记住：你就是鲸鱼小姐。"
print("=== 会话 A（headless）===")
try:
    p = subprocess.run([DSH, "--profile", "lingshu-qq", "headless", PROMPT_A],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=env, timeout=600, shell=False)
    print("rc:", p.returncode)
    print("stdout 长度:", len(p.stdout or ""))
    print("stdout 前 1500:")
    print((p.stdout or "")[:1500])
    if (p.stderr or "").strip():
        print("stderr 前 800:")
        print((p.stderr or "")[:800])
except subprocess.TimeoutExpired:
    print("超时")
except Exception as e:
    print("异常:", type(e).__name__, str(e)[:200])