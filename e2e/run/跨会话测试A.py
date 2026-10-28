import subprocess, os
DSH = r"D:\dsh-home\dsh-0.2.1-rc.2\node_modules\.bin\dsh.cmd"
env = dict(os.environ)
env["PYTHONUTF8"] = "1"
PROMPT_A = "你现在扮演一个叫「鲸鱼小姐」的角色：她是深海来的鲸鱼娘，傲娇、占有欲强、嘴硬心软，说话带刺但会照顾人。请用她的口气说一句话，然后记住：你就是鲸鱼小姐。"
def run(prompt, timeout=600):
    p = subprocess.run([DSH, "--profile", "lingshu-qq", "headless", prompt],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=env, timeout=timeout, shell=False)
    return p.returncode, (p.stdout or ""), (p.stderr or "")
print("=== 会话 A ===")
rc, out, err = run(PROMPT_A)
print("rc:", rc)
print("stdout:", out[:1200])
if err.strip():
    print("stderr:", err[:600])