import subprocess
def run(*a):
    p = subprocess.run(list(a), capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")
G = ("git", "-C", r"D:/1_ai/_hb_lab/r58")
run(*G, "add", "e2e")
rc, out = run(*G, "commit", "-m", "fix(e2e): 统一四层计数口径（ability 191/control 7/diagnostic 3/excluded 111/excused 8=320）；修 README 156-198-201 三套数字冲突与 D 文档矛盾；补 review 率与 B1 8 题原因")
print("commit:", rc, out[-170:])
print(run(*G, "push")[1][-110:])